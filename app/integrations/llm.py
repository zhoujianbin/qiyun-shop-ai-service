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


TOOL_MESSAGE_KEYS = ("role", "content", "name", "tool_call_id", "tool_calls")


def _prepare_messages(messages: list[dict]) -> list[dict]:
    """只保留协议需要的字段；工具回填消息必须带 tool_call_id / tool_calls，否则模型看不懂第二轮。"""
    prepared = []
    for message in messages:
        item = {key: message[key] for key in TOOL_MESSAGE_KEYS if key in message}
        item.setdefault("role", "user")
        item.setdefault("content", "")
        prepared.append(item)
    return prepared


class FakeProvider:
    """确定性替身：同输入同输出，供测试与离线联调。

    脚本模式（四期）：`script()` 注入一次工具调用，下一次 stream/complete 直接返回它。
    这让工具类用例能在无网络、无真实模型的条件下跑通服务端链路。
    """

    name = "fake"

    def __init__(self) -> None:
        self._scripted: list[dict] | None = None

    def script(self, tool_calls: list[dict] | None) -> None:
        """注入一次性工具调用脚本：[{"name": ..., "arguments": {...}}]。"""
        self._scripted = tool_calls

    def _take_script(self) -> list[dict] | None:
        calls, self._scripted = self._scripted, None
        return calls

    def stream(self, messages: list[dict], **opts) -> Iterator[tuple[str, dict]]:
        scripted = self._take_script()
        if scripted:
            for index, call in enumerate(scripted):
                arguments = call.get("arguments") or {}
                text = arguments if isinstance(arguments, str) else json.dumps(arguments, ensure_ascii=False)
                yield ("tool_call", {"index": index, "id": call.get("id") or f"call_fake_{index}",
                                     "name": call["name"], "arguments": text})
            return
        text = self._render(messages)
        step = 6
        for index in range(0, len(text), step):
            yield ("content", {"text": text[index:index + step]})
        yield ("finish", {"reason": "stop"})

    def complete(self, messages: list[dict], **opts) -> dict:
        scripted = self._take_script()
        if scripted:
            calls = []
            for index, call in enumerate(scripted):
                arguments = call.get("arguments") or {}
                text = arguments if isinstance(arguments, str) else json.dumps(arguments, ensure_ascii=False)
                calls.append({"id": call.get("id") or f"call_fake_{index}", "type": "function",
                              "function": {"name": call["name"], "arguments": text}})
            return {"text": "", "tool_calls": calls, "model": self.name,
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0}}
        return {"text": self._render(messages), "tool_calls": [], "model": self.name,
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
        payload = {
            "model": opts.get("model") or settings.llm_model,
            "messages": _prepare_messages(messages),
            "stream": stream,
            "temperature": opts.get("temperature", settings.llm_temperature),
            "max_tokens": opts.get("max_tokens", settings.llm_max_tokens),
        }
        if opts.get("tools"):
            payload["tools"] = opts["tools"]
            payload["tool_choice"] = opts.get("tool_choice", "auto")
        return payload

    def stream(self, messages: list[dict], **opts) -> Iterator[tuple[str, dict]]:
        payload = self._payload(messages, True, **opts)
        # index -> {"id","name","arguments"}；id/name 只在首块出现，arguments 逐片拼接
        buffer: dict[int, dict] = {}
        finish_reason = None
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
                        choice = choices[0]
                        delta = choice.get("delta") or {}
                        # 关键：只取 content；reasoning_content 丢弃
                        text = delta.get("content")
                        if text:
                            yield ("content", {"text": text})
                        for call in delta.get("tool_calls") or []:
                            slot = buffer.setdefault(int(call.get("index") or 0),
                                                     {"id": None, "name": None, "arguments": ""})
                            if call.get("id"):
                                slot["id"] = call["id"]
                            function = call.get("function") or {}
                            if function.get("name"):
                                slot["name"] = function["name"]
                            slot["arguments"] += function.get("arguments") or ""
                        if choice.get("finish_reason"):
                            finish_reason = choice["finish_reason"]
            except httpx.HTTPError as exc:
                raise LLMError(f"模型请求失败：{exc}") from exc
        # 参数只有在 finish_reason 到达后才完整，统一在收口时吐出
        if finish_reason == "tool_calls" or (buffer and not finish_reason):
            for index in sorted(buffer):
                slot = buffer[index]
                if not slot["name"]:
                    continue
                yield ("tool_call", {"index": index, "id": slot["id"], "name": slot["name"],
                                     "arguments": slot["arguments"]})
        elif buffer:
            for index in sorted(buffer):
                slot = buffer[index]
                if slot["name"]:
                    yield ("tool_call", {"index": index, "id": slot["id"], "name": slot["name"],
                                         "arguments": slot["arguments"]})
        yield ("finish", {"reason": finish_reason})

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
            "tool_calls": (choices[0].get("message") or {}).get("tool_calls") or [],
            "finish_reason": choices[0].get("finish_reason"),
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


def stream_events(messages: list[dict], **opts) -> Iterator[tuple[str, dict]]:
    """结构化流：("content", {...}) / ("tool_call", {...}) / ("finish", {...})。"""
    return get_provider().stream(messages, **opts)


def stream_chat(messages: list[dict], **opts) -> Iterator[str]:
    """兼容入口：只要文本增量（既有调用方继续用这个）。"""
    for kind, payload in get_provider().stream(messages, **opts):
        if kind == "content":
            yield payload.get("text") or ""


def complete(messages: list[dict], **opts) -> dict:
    return get_provider().complete(messages, **opts)
