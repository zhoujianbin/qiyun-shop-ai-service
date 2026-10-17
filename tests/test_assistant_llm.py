"""LLM 适配器：fake 确定性、只转发 content（丢弃 reasoning_content）、缺 key 报错。"""
import json

import httpx
import pytest

from app.core.config import settings
from app.integrations import llm

MESSAGES = [{"role": "user", "content": "门锁没电了怎么办"}]


def test_test_env_uses_fake_provider():
    assert isinstance(llm.get_provider(), llm.FakeProvider)


def test_fake_stream_is_deterministic_and_concatenates():
    first = "".join(llm.stream_chat(MESSAGES))
    second = "".join(llm.stream_chat(MESSAGES))
    assert first == second
    assert "门锁没电了怎么办" in first


def test_openai_stream_drops_reasoning_content(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "sk-test")
    chunks = [
        {"choices": [{"delta": {"role": "assistant", "reasoning_content": "我在思考"}}]},
        {"choices": [{"delta": {"content": "先用"}}]},
        {"choices": [{"delta": {"reasoning_content": "继续思考", "content": "机械钥匙"}}]},
        {"choices": [{"delta": {"content": "开门"}}]},
    ]
    body = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["stream"] is True and payload["model"] == settings.llm_model
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    provider = llm.OpenAIProvider(transport=httpx.MockTransport(handler))
    text = "".join(provider.stream(MESSAGES))
    assert text == "先用机械钥匙开门"
    assert "思考" not in text


def test_openai_complete_returns_usage(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "sk-test")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "model": "deepseek-flash",
            "choices": [{"message": {"content": '{"steps": []}'}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 8},
        })

    provider = llm.OpenAIProvider(transport=httpx.MockTransport(handler))
    result = provider.complete(MESSAGES)
    assert result["text"] == '{"steps": []}'
    assert result["usage"] == {"prompt_tokens": 12, "completion_tokens": 8}


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "")
    provider = llm.OpenAIProvider(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    with pytest.raises(llm.LLMError, match="LLM_API_KEY"):
        list(provider.stream(MESSAGES))


def test_unknown_provider_rejected(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "dev")   # 绕开"测试环境一律 fake"
    monkeypatch.setattr(settings, "llm_provider", "opennai")
    llm.reset_provider(None)
    with pytest.raises(llm.LLMError, match="未知的 LLM_PROVIDER"):
        llm.get_provider()
    llm.reset_provider(None)
