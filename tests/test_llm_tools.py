"""四期：工具通道（tools 透传、tool_calls 解析、流式拼接、fake 脚本化）。"""
import json

import httpx

from app.core.config import settings
from app.integrations import llm

MESSAGES = [{"role": "user", "content": "我订单 SO20260101001234 到哪了？"}]
TOOLS = [{"type": "function", "function": {
    "name": "query_shipment",
    "description": "当用户给出订单号并询问物流时使用；未给订单号时不要调用",
    "parameters": {"type": "object", "properties": {"order_no": {"type": "string"}},
                   "required": ["order_no"], "additionalProperties": False}}}]


def _stream_body(chunks: list[dict]) -> str:
    return "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"


def test_payload_passes_tools(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "sk-test")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": ""},
                                                      "finish_reason": "stop"}],
                                         "usage": {}})

    provider = llm.OpenAIProvider(transport=httpx.MockTransport(handler))
    provider.complete(MESSAGES, tools=TOOLS)
    assert seen["tools"] == TOOLS
    assert seen["tool_choice"] == "auto"


def test_complete_returns_tool_calls(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "sk-test")
    body = {"choices": [{"finish_reason": "tool_calls", "message": {
        "content": None, "tool_calls": [{"id": "call_1", "type": "function",
                                         "function": {"name": "query_shipment",
                                                      "arguments": "{\"order_no\": \"SO1\"}"}}]}}],
        "usage": {}}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    result = llm.OpenAIProvider(transport=httpx.MockTransport(handler)).complete(
        MESSAGES, tools=TOOLS)
    assert result["text"] == ""
    assert result["finish_reason"] == "tool_calls"
    call = result["tool_calls"][0]
    assert call["function"]["name"] == "query_shipment"
    assert json.loads(call["function"]["arguments"]) == {"order_no": "SO1"}


def test_stream_accumulates_fragmented_tool_arguments(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "sk-test")
    chunks = [
        {"choices": [{"delta": {"content": "我先帮您查一下。"}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_x", "type": "function",
                                                "function": {"name": "query_shipment",
                                                             "arguments": ""}}]}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "{\"order_no\""}}]}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": ": \"SO1\"}"}}]}}]},
        {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_stream_body(chunks),
                              headers={"content-type": "text/event-stream"})

    events = list(llm.OpenAIProvider(transport=httpx.MockTransport(handler)).stream(
        MESSAGES, tools=TOOLS))
    kinds = [kind for kind, _ in events]
    assert "content" in kinds and "tool_call" in kinds
    call = next(payload for kind, payload in events if kind == "tool_call")
    assert call["id"] == "call_x" and call["name"] == "query_shipment"
    assert json.loads(call["arguments"]) == {"order_no": "SO1"}
    # 文本与工具决策是分开的事件，调用结构不会混进文本
    text = "".join(payload["text"] for kind, payload in events if kind == "content")
    assert text == "我先帮您查一下。"


def test_fake_provider_script_emits_single_tool_call():
    provider = llm.FakeProvider()
    provider.script([{"name": "query_shipment", "arguments": {"order_no": "SO1"}}])
    events = list(provider.stream(MESSAGES))
    assert [kind for kind, _ in events] == ["tool_call"]
    assert json.loads(events[0][1]["arguments"]) == {"order_no": "SO1"}
    # 脚本只生效一次，之后回到确定性文本
    assert any(kind == "content" for kind, _ in provider.stream(MESSAGES))
