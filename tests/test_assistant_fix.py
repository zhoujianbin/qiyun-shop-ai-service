"""三期缺陷修复回归：P0 转人工落库 / P1 意图零开销 / P2 别名覆盖 / P3 相关性闸门。"""
import uuid

import pytest
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.generated import Handoff, Rule
from app.services import assistant_graph, knowledge_retrieval
from tests.conftest import auth, customer_token, new_key

HIT_RELEVANT = {
    "source_type": "chunk", "chunk_id": 401, "document_id": "KB-PROD-QLL3P-MASTER",
    "document_pk": 1, "version": 1, "chunk_ord": 0, "title_path": "产品知识 / 智能门锁 / 电池",
    "line_start": 14, "line_end": 16, "snippet": "QL-L3P 智能门锁没电时可用机械钥匙开门。",
}
HIT_IRRELEVANT = {
    "source_type": "chunk", "chunk_id": 402, "document_id": "KB-RETURN-001",
    "document_pk": 2, "version": 1, "chunk_ord": 0, "title_path": "退货政策 / 无理由退货",
    "line_start": 3, "line_end": 5, "snippet": "七天无理由退货需在签收后 7 日内提出。",
}


def _search(hits):
    return lambda db, query, **kwargs: {"hits": hits, "debug": {"latency_ms": 2}}


def _conversation(client, token):
    return client.post("/api/v1/ai/conversations", headers=auth(token, new_key()), json={}).json()["id"]


def _stream(client, token, cid, content):
    with client.stream("POST", f"/api/v1/ai/conversations/{cid}/messages:stream",
                       headers=auth(token, new_key()), json={"content": content}) as response:
        return "".join(response.iter_text())


def _handoffs(cid):
    with SessionLocal() as db:
        return db.execute(select(Handoff).where(Handoff.conversation_id == cid)).scalars().all()


# ---------------------------------------------------------------- P0
def test_dialog_handoff_creates_record(client):
    token = customer_token(client, "buyer_zhang")
    cid = _conversation(client, token)
    _stream(client, token, cid, "我要转人工")
    rows = _handoffs(cid)
    assert rows and rows[0].reason == "USER_REQUEST"
    assert rows[0].status == "OPEN"


def test_dialog_handoff_is_idempotent(client):
    token = customer_token(client, "buyer_zhang")
    cid = _conversation(client, token)
    _stream(client, token, cid, "我要转人工")
    _stream(client, token, cid, "转人工")
    assert len(_handoffs(cid)) == 1


def test_claimed_handoff_pauses_ai(client):
    admin = client.post("/api/v1/auth/staff/login",
                        json={"username": "admin", "password": "Qiyun@2026#Dev"}).json()["access_token"]
    token = customer_token(client, "buyer_zhang")
    cid = _conversation(client, token)
    _stream(client, token, cid, "我要转人工")
    handoff_id = _handoffs(cid)[0].id
    assert client.post(f"/api/v1/ai/handoffs/{handoff_id}/claim", headers=auth(admin, new_key())).status_code == 200
    paused = client.post(f"/api/v1/ai/conversations/{cid}/messages:stream",
                         headers=auth(token, new_key()), json={"content": "还在吗"})
    assert paused.status_code == 409


# ---------------------------------------------------------------- P1
def test_classify_does_not_call_model(monkeypatch):
    monkeypatch.setattr("app.integrations.llm.complete",
                        lambda *a, **k: pytest.fail("意图识别不得调用模型"))
    assert assistant_graph.classify("门锁没电了怎么办") == ("KNOWLEDGE", False)
    assert assistant_graph.classify("我要转人工") == ("HUMAN_REQUEST", True)


def test_planner_flag_enables_model(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "assistant_use_llm_planner", True)
    monkeypatch.setattr("app.integrations.llm.complete",
                        lambda *a, **k: {"text": "REALTIME_FACT"})
    assert assistant_graph.classify("我家那个东西现在怎么样") == ("REALTIME_FACT", False)


# ---------------------------------------------------------------- P2
def test_camera_alias_covers_colloquial_phrase():
    with SessionLocal() as db:
        db.add(Rule(
            tenant_id=1, rule_id=f"ESC-CAM-{uuid.uuid4().hex[:6]}", source_kind="escalation",
            condition={"issue_type": ["unknown_camera_access"]}, action={"decision": "ESCALATE"},
            forbid=["view_customer_video"], priority=1000, status="ACTIVE",
            conflict_group="escalation",
        ))
        db.commit()
    with SessionLocal() as db:
        for phrase in ("摄像头被陌生人访问怎么办", "摄像头被偷看了", "有人偷窥我的摄像头"):
            assert assistant_graph.guard_hints(db, phrase), phrase


def test_alias_file_has_colloquial_variants():
    aliases = assistant_graph.load_escalation_aliases()
    assert "陌生人访问" in aliases["unknown_camera_access"]
    assert "漏电" in aliases["electric_shock"]
    assert "异地登录" in aliases["account_takeover"]


# ---------------------------------------------------------------- P3
def test_relevance_gate_positive_and_negative():
    assert assistant_graph.relevance_ok("门锁没电了怎么办", [HIT_RELEVANT])
    assert not assistant_graph.relevance_ok("火星移民需要什么条件", [HIT_IRRELEVANT])
    assert not assistant_graph.relevance_ok("量子计算机退相干时间", [HIT_IRRELEVANT])


def test_irrelevant_hits_are_dropped(monkeypatch):
    monkeypatch.setattr(knowledge_retrieval, "search", _search([HIT_IRRELEVANT]))
    with SessionLocal() as db:
        state = assistant_graph.run(db, "火星移民需要什么条件", actor={"id": 1}, history=[])
    assert state.citations == []
    assert state.decision in ("CLARIFY", "REFUSE")


def test_relevant_hits_still_cited(monkeypatch, client):
    monkeypatch.setattr(knowledge_retrieval, "search", _search([HIT_RELEVANT]))
    token = customer_token(client, "buyer_zhang")
    cid = _conversation(client, token)
    body = _stream(client, token, cid, "门锁没电了怎么办")
    assert "event: citations" in body and HIT_RELEVANT["document_id"] in body
    assert "event: done" in body
