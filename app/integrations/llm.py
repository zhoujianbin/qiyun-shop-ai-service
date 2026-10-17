"""大模型适配器：OpenAI 兼容端点（DeepSeek）+ 确定性 fake。

设计约束（见 design.md 决策 2）：
- 只实现两个动作：`stream_chat()`（流式，供 SSE）与 `complete()`（一次性，供 planner 出 JSON）。
- **只转发 `delta.content`**，丢弃 `reasoning_content`：推理内容不落库、不下发、不进 SSE。
- `APP_ENV=test` 或 `LLM_PROVIDER=fake` 时用 fake，测试不联网。
- 换厂商只改 `LLM_BASE_URL` / `LLM_MODEL`。
"""
from __future__ import annotations

import json
import threading
from collections.abc import Iterator

import httpx

from app.core.config import settings


class LLMError(RuntimeError):
    """模型不可用或返回异常。"""


def _prepare_messages(messages: list[dict]) -> list[dict]:
    return [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages]


class FakeProvider:
    """确定性替身：同输入同输出，供测试与离线联调。"""

    name = "fake"

    def stream(self, messages: list[dict], **opts) -> Iterator[str]:
        text = self._render(messages)
        step = 6
        for index in range(0, len(text), step):
            yield text[index:index + step]

    def complete(self, messages: list[dict], **opts) -> dict:
        return {"text": self._render(messages), "model": self.name,
                "usage": {"prompt_tokens": 0, "completion_tokens": 0}}

    @staticmethod
    def _render(messages: list[dict]) -> str:
        last = ""
        for message in reversed(messages):
            if message.get("role") == "user":
                last = str(message.get("content", ""))
                break
        return f"（测试回答）关于「{last[:20]}」，请以知识库引用为准。"


class OpenAIProvider:
    """OpenAI 兼容的 /chat/completions；DeepSeek 默认走这里。"""

    name = "openai"

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport
        self._lock = threading.Lock()

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=settings.llm_base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            timeout=settings.llm_timeout_seconds,
            transport=self._transport,
        )

    def _payload(self, messages: list[dict], stream: bool, **opts) -> dict:
        if not settings.llm_api_key:
            raise LLMError("缺少 LLM_API_KEY，无法调用真实模型（可设 LLM_PROVIDER=fake）")
        return {
            "model": opts.get("model") or settings.llm_model,
            "messages": _prepare_messages(messages),
            "stream": stream,
            "temperature": opts.get("temperature", settings.llm_temperature),
            "max_tokens": opts.get("max_tokens", settings.llm_max_tokens),
        }

    def stream(self, messages: list[dict], **opts) -> Iterator[str]:
        payload = self._payload(messages, True, **opts)
        with self._client() as client:
            try:
                with client.stream("POST", "/chat/completions", json=payload) as response:
                    if response.status_code >= 400:
                        detail = response.read().decode("utf-8", "ignore")[:300]
                        raise LLMError(f"模型返回 {response.status_code}：{detail}")
                    for line in response.iter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data = line[6:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        # 关键：只取 content；reasoning_content 丢弃
                        text = delta.get("content")
                        if text:
                            yield text
            except httpx.HTTPError as exc:
                raise LLMError(f"模型请求失败：{exc}") from exc

    def complete(self, messages: list[dict], **opts) -> dict:
        payload = self._payload(messages, False, **opts)
        with self._client() as client:
            try:
                response = client.post("/chat/completions", json=payload)
            except httpx.HTTPError as exc:
                raise LLMError(f"模型请求失败：{exc}") from exc
        if response.status_code >= 400:
            raise LLMError(f"模型返回 {response.status_code}：{response.text[:300]}")
        body = response.json()
        choices = body.get("choices") or []
        if not choices:
            raise LLMError("模型返回空 choices")
        usage = body.get("usage") or {}
        return {
            "text": (choices[0].get("message") or {}).get("content") or "",
            "model": body.get("model") or settings.llm_model,
            "usage": {
                "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                "completion_tokens": int(usage.get("completion_tokens") or 0),
            },
        }


_provider = None
_provider_lock = threading.Lock()


def _resolve_provider():
    # 测试环境一律 fake：即使 .env 里写了 openai，也不能让回归测试联网
    if settings.app_env.lower() == "test":
        return FakeProvider()
    configured = (settings.llm_provider or "auto").strip().lower()
    if configured == "fake":
        return FakeProvider()
    if configured == "openai":
        return OpenAIProvider()
    if configured == "auto":
        return OpenAIProvider()
    raise LLMError(f"未知的 LLM_PROVIDER：{settings.llm_provider}")


def get_provider():
    global _provider
    if _provider is None:
        with _provider_lock:
            if _provider is None:
                _provider = _resolve_provider()
    return _provider


def reset_provider(provider=None) -> None:
    """清空或注入单例（测试使用）。"""
    global _provider
    with _provider_lock:
        _provider = provider


def stream_chat(messages: list[dict], **opts) -> Iterator[str]:
    return get_provider().stream(messages, **opts)


def complete(messages: list[dict], **opts) -> dict:
    return get_provider().complete(messages, **opts)
