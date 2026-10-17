"""四期：工具分支（事实回填、核验门禁、写工具不放行）。"""
import pytest

from app.core.db import SessionLocal
from app.integrations import llm
from app.services import assistant_graph, tool_registry


@pytest.fixture()
def scripted(monkeypatch):
    """让 fake 模型按脚本返回一次工具调用。"""
    provider = llm.get_provider()

    def _script(calls):
        provider.script(calls)
        return provider

    yield _script
    provider.script(None)


def _verified(order_no: str):
    from types import SimpleNamespace

    return lambda db, conversation_id: SimpleNamespace(order_no=order_no, status="VERIFIED")


def test_fact_branch_fills_facts_and_skips_citations(monkeypatch, scripted):
    spec = tool_registry.TOOLS["query_order"]
    monkeypatch.setattr(spec, "run", lambda db, state, args: {
        "facts": {"order_no": args["order_no"], "status": "SHIPPED"}, "order_id": 1})
    monkeypatch.setattr(assistant_graph.assistant_handoff, "active_verification",
                        _verified("SO20260101001234"))
    scripted([{"name": "query_order", "arguments": {"order_no": "SO20260101001234"}}])

    with SessionLocal() as db:
        # 已核验会话才能过门禁
        state = assistant_graph.State(question="我订单 SO20260101001234 到哪了",
                                      conversation_id=1)
        assistant_graph.plan(state)
        assistant_graph.tool_loop(db, state, actor={"id": 1, "party": "CUSTOMER", "customer_id": 1},
                                  identity_level="customer", history=[])
        state = assistant_graph.finalize(db, state, history=[])

    assert state.facts and state.facts[0]["tool"] == "query_order"
    assert state.decision == "ANSWER"
    assert state.citations == []
    assert "事实" in state.prompt_messages[0]["content"]
    assert "SHIPPED" in state.prompt_messages[0]["content"]


def test_identity_gate_blocks_unverified_tool(monkeypatch, scripted):
    calls = []
    spec = tool_registry.TOOLS["query_order"]
    monkeypatch.setattr(spec, "run", lambda db, state, args: calls.append(args) or {"facts": {}})
    scripted([{"name": "query_order", "arguments": {"order_no": "SO20260101001234"}}])

    with SessionLocal() as db:
        state = assistant_graph.State(question="我订单 SO20260101001234 到哪了",
                                      conversation_id=999999)
        assistant_graph.plan(state)
        state = assistant_graph.tool_loop(
            db, state, actor={"id": 1, "party": "CUSTOMER", "customer_id": 1},
            identity_level="public", history=[])
        state = assistant_graph.finalize(db, state, history=[])

    assert state.decision == "IDENTITY_REQUEST"
    assert calls == []                      # 门禁挡住：工具零执行
    assert state.tool_calls[0]["error_code"] == "IDENTITY_REQUIRED"
    assert assistant_graph.fixed_answer(state) == assistant_graph.IDENTITY_REQUEST_TEXT


def test_write_tool_is_not_offered_and_rejected(scripted):
    # 只读清单里没有写工具，因此即使脚本硬给一个也会被拒
    names = [item["function"]["name"] for item in tool_registry.llm_tools(include_write=False)]
    assert "cancel_order" not in names
    scripted([{"name": "cancel_order", "arguments": {"order_no": "SO1"}}])
    with SessionLocal() as db:
        state = assistant_graph.State(question="帮我取消订单 SO1", conversation_id=None)
        assistant_graph.plan(state)
        state = assistant_graph.tool_loop(db, state, actor={"id": 1, "party": "CUSTOMER"},
                                          identity_level="public", history=[])
    assert state.tool_calls[0]["status"] == "REJECTED"
    assert state.tool_calls[0]["error_code"] == "TOOL_NOT_ALLOWED"
    assert state.facts == []

def test_stream_emits_tool_event_before_delta_and_hides_tool_calls(client, monkeypatch):
    """B2 回归：工具事件先于文本增量；tool_calls 原始结构永不出现在事件流里。"""
    import json as _json

    from tests.conftest import auth, customer_token, new_key

    spec = tool_registry.TOOLS["query_product"]
    monkeypatch.setattr(spec, "run", lambda db, state, args: {
        "facts": {"products": [{"name": "栖云智能门锁 L3 Pro"}]}})
    llm.get_provider().script([{"name": "query_product", "arguments": {"keyword": "门锁"}}])
    token = customer_token(client)
    conversation = client.post("/api/v1/ai/conversations", headers=auth(token, new_key()),
                               json={}).json()
    with client.stream("POST",
                       f"/api/v1/ai/conversations/{conversation['id']}/messages:stream",
                       headers=auth(token, new_key()),
                       json={"content": "我订单到哪了"}) as response:
        raw = "".join(response.iter_text())

    names = [line[7:] for line in raw.splitlines() if line.startswith("event: ")]
    assert "tool" in names, names
    assert names.index("tool") < names.index("delta")
    assert "tool_calls" not in raw and "arguments" not in raw
    # 工具的事实最终进入消息
    assert "正在查询" not in raw  # 我们不发这个占位文本，只发事件
    llm.get_provider().script(None)
