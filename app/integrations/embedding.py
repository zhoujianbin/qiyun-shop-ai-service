"""向量化适配器：本地 BAAI/bge-small-zh-v1.5（512 维，L2 归一化）。

设计约束（见 design.md 决策 5）：
- 进程内单例懒加载：首次调用才导入 sentence-transformers 并加载模型。
- 模型位置：默认下载到 HF_HOME（settings.hf_home，默认 ./var/models）；
  设置 EMBEDDING_MODEL_PATH 时直接使用离线目录，不联网。
- 入库文本不加指令前缀，查询文本加（bge 系列的检索用法）。
- 测试环境默认使用确定性 fake：同一文本永远得到同一向量，避免每次回归加载 95MB 模型。
"""
from __future__ import annotations

import hashlib
import math
import os
import pathlib
import random
import threading

from app.core.config import settings


class EmbeddingError(RuntimeError):
    """向量化失败（模型不可用或维度不符）。"""


def _prepare(texts: list[str], is_query: bool) -> list[str]:
    """查询侧加 bge 指令前缀，入库侧原样。两个 provider 共用，保证行为一致可测。"""
    prefix = settings.embedding_query_prefix if is_query else ""
    return [(prefix + text) if prefix else text for text in texts]


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        raise EmbeddingError("零向量无法归一化")
    return [x / norm for x in vector]


class FakeEmbedder:
    """确定性替身：同文本 -> 同向量，512 维、L2 归一化。仅用于测试与离线联调。"""

    def __init__(self, dim: int | None = None) -> None:
        self._dim = dim or settings.embedding_dim

    @property
    def dimension(self) -> int:
        return self._dim

    def encode(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        result = []
        for text in _prepare(texts, is_query):
            seed = hashlib.sha256(text.encode("utf-8")).hexdigest()
            rng = random.Random(int(seed[:16], 16))
            raw = [rng.uniform(-1.0, 1.0) for _ in range(self._dim)]
            result.append(_normalize(raw))
        return result


class BgeEmbedder:
    """真实的本地 bge 模型；模型在首次调用时加载并常驻。"""

    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()

    def _model_dir(self) -> str:
        if settings.embedding_model_path:
            path = pathlib.Path(settings.embedding_model_path).expanduser()
            if not path.is_dir():
                raise EmbeddingError(f"EMBEDDING_MODEL_PATH 不存在或不是目录：{path}")
            return str(path)
        home = pathlib.Path(settings.hf_home).expanduser().resolve()
        home.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("HF_HOME", str(home))
        return settings.embedding_model_name

    def _ensure_model(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            # 先解析路径：配置错误应快速失败，不必先付导入成本
            source = self._model_dir()
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - 依赖缺失时给出可读错误
                raise EmbeddingError("未安装 sentence-transformers，无法加载向量模型") from exc
            try:
                model = SentenceTransformer(source)
            except Exception as exc:  # noqa: BLE001 - 模型不可用时统一转成 EmbeddingError
                raise EmbeddingError(f"加载向量模型失败：{source}（{exc}）") from exc
            getter = getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension
            dim = getter()
            if dim != settings.embedding_dim:
                raise EmbeddingError(
                    f"模型维度 {dim} 与配置 embedding_dim={settings.embedding_dim} 不一致；"
                    "换模型必须同时改 knowledge.chunk.embedding 维度并重算全部向量"
                )
            self._model = model
            return model

    @property
    def dimension(self) -> int:
        return settings.embedding_dim

    def encode(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        if not texts:
            return []
        model = self._ensure_model()
        vectors = model.encode(
            _prepare(texts, is_query),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [[float(x) for x in row] for row in vectors]


_provider = None
_provider_lock = threading.Lock()


def _resolve_provider():
    configured = (settings.embedding_provider or "auto").strip().lower()
    if configured == "fake":
        return FakeEmbedder()
    if configured == "bge":
        return BgeEmbedder()
    if configured == "auto":
        # 测试环境不加载真实模型；其他环境用真实模型
        return FakeEmbedder() if settings.app_env.lower() == "test" else BgeEmbedder()
    raise EmbeddingError(f"未知的 EMBEDDING_PROVIDER：{settings.embedding_provider}")


def get_provider():
    global _provider
    if _provider is None:
        with _provider_lock:
            if _provider is None:
                _provider = _resolve_provider()
    return _provider


def reset_provider() -> None:
    """清空单例（测试与换模型时使用）。"""
    global _provider
    with _provider_lock:
        _provider = None


def dimension() -> int:
    return get_provider().dimension


def encode_documents(texts: list[str]) -> list[list[float]]:
    """入库侧：不加指令前缀。"""
    return get_provider().encode(texts, is_query=False)


def encode_query(text: str) -> list[float]:
    """检索侧：加 bge 中文检索指令前缀。"""
    vectors = get_provider().encode([text], is_query=True)
    return vectors[0]
