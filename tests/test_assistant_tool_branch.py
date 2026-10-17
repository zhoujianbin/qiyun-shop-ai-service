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


def test_write_tool_is_not_offered_to_staff_without_permission(scripted):
    """员工没有 tool:write:* 时，写工具不在清单里，硬给也会被拒。"""
    names = [item["function"]["name"] for item in tool_registry.llm_tools(include_write=False)]
    assert "cancel_order" not in names
    scripted([{"name": "cancel_order", "arguments": {"order_no": "SO1"}}])
    with SessionLocal() as db:
        state = assistant_graph.State(question="帮我取消订单 SO1", conversation_id=None)
        assistant_graph.plan(state)
        state = assistant_graph.tool_loop(db, state,
                                          actor={"id": 1, "party": "STAFF"},
                                          identity_level="agent", history=[],
                                          permissions=set())
    assert state.tool_calls[0]["status"] == "REJECTED"
    assert state.tool_calls[0]["error_code"] == "TOOL_NOT_ALLOWED"
    assert state.facts == []


def test_customer_write_requires_conversation_context(scripted):
    """客户侧写能力靠开关放行，但没有会话上下文时仍然拒绝（不能凭空生成动作）。"""
    scripted([{"name": "cancel_order", "arguments": {"order_no": "SO1"}}])
    with SessionLocal() as db:
        state = assistant_graph.State(question="帮我取消订单 SO1", conversation_id=None)
        assistant_graph.plan(state)
        state = assistant_graph.tool_loop(db, state,
                                          actor={"id": 1, "party": "CUSTOMER",
                                                 "customer_id": 1},
                                          identity_level="public", history=[])
    assert state.tool_calls[0]["error_code"] == "IDENTITY_REQUIRED"

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

def test_knowledge_tool_results_reach_facts_and_citations(monkeypatch, scripted):
    """工具分支里查知识：命中必须进事实块，并生成服务端引用（曾因 facts=None 丢失）。"""
    from app.services import knowledge_retrieval

    fake_hits = [{"chunk_id": 1, "document_id": "KB-RETURN-001", "version": 1,
                  "title_path": "七天无理由退货", "line_start": 1, "line_end": 2,
                  "snippet": "七天无理由退货需要订单有效且在签收后 7 天内提出",
                  "chunk_ord": 1}]
    monkeypatch.setattr(knowledge_retrieval, "search",
                        lambda db, query, **kw: {"hits": fake_hits,
                                                 "debug": {"latency_ms": 1, "vector_score": {},
                                                           "text_score": {}, "fused_score": {},
                                                           "candidates": 1}})
    scripted([{"name": "search_knowledge", "arguments": {"query": "退货政策"}}])
    with SessionLocal() as db:
        state = assistant_graph.State(question="能退货么", conversation_id=None)
        assistant_graph.plan(state)
        state = assistant_graph.tool_loop(db, state,
                                          actor={"id": 1, "party": "CUSTOMER", "customer_id": 1},
                                          identity_level="public", history=[])
        state = assistant_graph.finalize(db, state, history=[])
    assert state.facts and state.facts[0]["facts"]["hits"][0]["document_id"] == "KB-RETURN-001"
    assert state.citations and state.citations[0]["document_id"] == "KB-RETURN-001"
    assert "七天无理由退货" in state.prompt_messages[0]["content"]
