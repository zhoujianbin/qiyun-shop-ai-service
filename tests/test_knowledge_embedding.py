"""向量适配器：确定性 fake、维度与归一化、查询前缀、配置错误快速失败。"""
import math

import pytest

from app.core.config import settings
from app.integrations import embedding


def test_fake_is_deterministic_and_normalized():
    provider = embedding.FakeEmbedder()
    first = provider.encode(["门锁没电了"])[0]
    second = provider.encode(["门锁没电了"])[0]
    assert first == second
    assert len(first) == settings.embedding_dim == 512
    assert math.isclose(math.sqrt(sum(x * x for x in first)), 1.0, rel_tol=1e-9)


def test_fake_differs_by_text():
    provider = embedding.FakeEmbedder()
    a = provider.encode(["门锁没电了"])[0]
    b = provider.encode(["摄像头无法连接"])[0]
    assert a != b


def test_query_side_adds_instruction_prefix():
    doc = embedding.encode_documents(["门锁没电了"])[0]
    query = embedding.encode_query("门锁没电了")
    assert doc != query
    expected = embedding.FakeEmbedder().encode(
        [settings.embedding_query_prefix + "门锁没电了"]
    )[0]
    assert query == expected


def test_empty_input_returns_empty():
    assert embedding.encode_documents([]) == []


def test_missing_offline_path_fails_fast(monkeypatch):
    monkeypatch.setattr(settings, "embedding_model_path", "/definitely/not/a/directory")
    embedder = embedding.BgeEmbedder()
    with pytest.raises(embedding.EmbeddingError, match="EMBEDDING_MODEL_PATH"):
        embedder.encode(["x"])


def test_unknown_provider_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "opennai")
    monkeypatch.setattr(embedding, "_provider", None)
    with pytest.raises(embedding.EmbeddingError, match="未知的 EMBEDDING_PROVIDER"):
        embedding.get_provider()
    embedding.reset_provider()


def test_test_env_uses_fake_provider():
    """APP_ENV=test 时 auto 解析为 fake，回归不加载 95MB 模型。"""
    assert isinstance(embedding.get_provider(), embedding.FakeEmbedder)
