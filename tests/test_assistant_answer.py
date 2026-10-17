"""RAG 编排：意图、检索、引用、拒答、护栏、改写、留痕。"""
import uuid

import pytest
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.generated import RetrievalTrace, Rule
from app.services import assistant_graph, knowledge_retrieval
from tests.conftest import auth, customer_token, new_key

HIT = {
    "source_type": "chunk",
    "chunk_id": 101,
    "document_id": "KB-PROD-QLL3P-MASTER",
    "document_pk": 1,
    "version": 1,
    "chunk_ord": 0,
    "title_path": "产品知识 / 智能门锁 / 电池续航",
    "line_start": 14,
    "line_end": 16,
    "snippet": "QL-L3P 门锁使用 8 节 5 号电池，正常使用约 12 个月。",
}


def _fake_search(hits, counter=None):
    def _search(db, query, **kwargs):
        if counter is not None:
            counter.append(query)
        return {"hits": hits, "debug": {"latency_ms": 5, "candidates": len(hits)}}
    return _search


def test_intent_rules_cover_four_classes():
    assert assistant_graph.classify_rule("我要转人工") == "HUMAN_REQUEST"
    assert assistant_graph.classify_rule("快递到哪了") == "REALTIME_FACT"
    assert assistant_graph.classify_rule("我的订单退款进度") == "IDENTITY_REQUEST"
    assert assistant_graph.classify_rule("门锁没电了怎么办") is None


def test_no_hit_refuses_without_calling_model(monkeypatch):
    monkeypatch.setattr(knowledge_retrieval, "search", _fake_search([]))
    monkeypatch.setattr(assistant_graph, "rewrite_query", lambda q: q)

    def boom(*args, **kwargs):
        raise AssertionError("无命中时不得调用生成模型")

    monkeypatch.setattr("app.integrations.llm.stream_chat", boom)
    with SessionLocal() as db:
        state = assistant_graph.run(db, "门锁没电了怎么办", actor={"id": 1}, history=[])
    assert state.decision in ("CLARIFY", "REFUSE")
    assert state.citations == []
    assert assistant_graph.fixed_answer(state)


def test_hits_build_citations_with_entity_tags(monkeypatch):
    monkeypatch.setattr(knowledge_retrieval, "search", _fake_search([HIT]))
    with SessionLocal() as db:
        state = assistant_graph.run(db, "门锁电池能用多久", actor={"id": 1}, history=[])
    assert state.decision == "ANSWER"
    assert state.citations and state.citations[0]["document_id"] == HIT["document_id"]
    tags = state.citations[0]["entity_tags"]
    assert any(tag["type"] == "product_line" and tag["value"].startswith("QL-L3P") for tag in tags)
    assert state.prompt_messages and HIT["snippet"] in state.prompt_messages[0]["content"]


def test_zero_hit_rewrites_once(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(knowledge_retrieval, "search", _fake_search([], calls))
    with SessionLocal() as db:
        state = assistant_graph.run(db, "这个情况要怎么办才好呢", actor={"id": 1}, history=[])
    assert len(calls) == 2, calls            # 首次 + 改写一次
    assert calls[0] != calls[1]
    assert state.replans == 1


def test_guard_hint_from_escalation_rule(monkeypatch):
    suffix = uuid.uuid4().hex[:6]
    with SessionLocal() as db:
        db.add(Rule(
            tenant_id=1, rule_id=f"ESC-TEST-{suffix}", source_kind="escalation",
            condition={"issue_type": ["remote_unlock"]},
            action={"decision": "ESCALATE"}, forbid=["remote_unlock_promise"],
            priority=1000, status="ACTIVE", conflict_group="escalation",
        ))
        db.commit()
    remote_hit = dict(HIT, snippet="远程开锁属于高风险操作，客服不能远程开门，需上门核验身份。",
                      title_path="智能门锁 / 远程开锁")
    monkeypatch.setattr(knowledge_retrieval, "search", _fake_search([remote_hit]))
    with SessionLocal() as db:
        state = assistant_graph.run(db, "能帮我远程开锁吗", actor={"id": 1}, history=[])
    assert state.guard_hints, "命中禁止项时必须给出安全提示"
    assert "安全" in state.guard_hints[0]


def test_order_number_routes_to_tool_branch():
    """四期：带单号的问题必须确定性进工具分支（QY 与 SO 两种前缀都认）。"""
    assert assistant_graph.classify_rule("帮我取消订单 QY20261017182948162180") == "REALTIME_FACT"
    assert assistant_graph.classify_rule("查下 SO20260101001234 的状态") == "REALTIME_FACT"
    assert assistant_graph.classify_rule("门锁没电了怎么办") is None


def test_retrieval_trace_is_persisted(client, monkeypatch):
    monkeypatch.setattr(knowledge_retrieval, "search", _fake_search([HIT]))
    token = customer_token(client, "buyer_zhang")
    conversation = client.post("/api/v1/ai/conversations",
                               headers=auth(token, new_key()), json={}).json()
    with client.stream("POST", f"/api/v1/ai/conversations/{conversation['id']}/messages:stream",
                       headers=auth(token, new_key()), json={"content": "门锁电池能用多久"}) as response:
        body = "".join(response.iter_text())
    assert "event: citations" in body
    with SessionLocal() as db:
        rows = db.execute(select(RetrievalTrace)).scalars().all()
    assert rows and rows[-1].hit_count == 1
    assert rows[-1].intent == "KNOWLEDGE"


def test_refusal_text_has_no_hard_numbers(monkeypatch):
    monkeypatch.setattr(knowledge_retrieval, "search", _fake_search([]))
    with SessionLocal() as db:
        state = assistant_graph.run(db, "完全不相关的问题 xyzzy", actor={"id": 1}, history=[])
    text = assistant_graph.fixed_answer(state)
    assert not any(char.isdigit() for char in text), text

def test_trace_endpoint_returns_plan_and_citations(client, monkeypatch):
    monkeypatch.setattr(knowledge_retrieval, "search", _fake_search([HIT]))
    token = customer_token(client, "buyer_zhang")
    conversation = client.post("/api/v1/ai/conversations",
                               headers=auth(token, new_key()), json={}).json()
    with client.stream("POST", f"/api/v1/ai/conversations/{conversation['id']}/messages:stream",
                       headers=auth(token, new_key()), json={"content": "门锁电池能用多久"}) as response:
        "".join(response.iter_text())
    messages = client.get(f"/api/v1/ai/conversations/{conversation['id']}/messages",
                          headers=auth(token, new_key())).json()["items"]
    answer_id = [m for m in messages if m["role"] == "ASSISTANT"][-1]["id"]
    trace = client.get(f"/api/v1/ai/messages/{answer_id}/trace",
                       headers=auth(token, new_key()))
    assert trace.status_code == 200, trace.text
    body = trace.json()[0]
    assert body["intent"] == "KNOWLEDGE"
    assert body["traces"] and body["traces"][0]["hit_count"] == 1
    assert body["citations"][0]["document_id"] == HIT["document_id"]


def test_model_failure_emits_error_and_marks_failed(client, monkeypatch):
    monkeypatch.setattr(knowledge_retrieval, "search", _fake_search([HIT]))

    def boom(*args, **kwargs):
        raise RuntimeError("模型超时")

    monkeypatch.setattr("app.integrations.llm.stream_chat", boom)
    token = customer_token(client, "buyer_zhang")
    conversation = client.post("/api/v1/ai/conversations",
                               headers=auth(token, new_key()), json={}).json()
    with client.stream("POST", f"/api/v1/ai/conversations/{conversation['id']}/messages:stream",
                       headers=auth(token, new_key()), json={"content": "门锁电池能用多久"}) as response:
        body = "".join(response.iter_text())
    assert "event: error" in body and "ASSISTANT_GENERATION_FAILED" in body
    messages = client.get(f"/api/v1/ai/conversations/{conversation['id']}/messages",
                          headers=auth(token, new_key())).json()["items"]
    answer = [m for m in messages if m["role"] == "ASSISTANT"][-1]
    assert answer["status"] == "FAILED"
