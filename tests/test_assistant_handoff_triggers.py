"""自动转人工三类触发：HIGH_RISK_RULE / NO_HIT / MODEL_ERROR，以及幂等。"""
import uuid

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.generated import Handoff, Rule
from app.services import knowledge_retrieval
from tests.conftest import auth, customer_token, new_key

HIT = {
    "source_type": "chunk", "chunk_id": 301, "document_id": "KB-PROD-QLL3P-MASTER",
    "document_pk": 1, "version": 1, "chunk_ord": 0, "title_path": "产品知识 / 智能门锁",
    "line_start": 14, "line_end": 16, "snippet": "QL-L3P 使用 8 节 5 号电池。",
}

HIT_REMOTE = {
    "source_type": "chunk", "chunk_id": 302, "document_id": "KB-RISK-REMOTE-UNLOCK",
    "document_pk": 2, "version": 1, "chunk_ord": 0, "title_path": "智能门锁 / 远程开锁",
    "line_start": 3, "line_end": 6,
    "snippet": "远程开锁属于高风险操作，客服不得远程开门，需上门核验身份。",
}


def _stream(client, token, cid, content):
    with client.stream("POST", f"/api/v1/ai/conversations/{cid}/messages:stream",
                       headers=auth(token, new_key()), json={"content": content}) as response:
        return response.status_code, "".join(response.iter_text())


def _conversation(client, token):
    return client.post("/api/v1/ai/conversations", headers=auth(token, new_key()), json={}).json()["id"]


def _open_handoffs(cid):
    with SessionLocal() as db:
        return db.execute(select(Handoff).where(
            Handoff.conversation_id == cid, Handoff.status.in_(("OPEN", "CLAIMED")))).scalars().all()


def _escalation_rule():
    with SessionLocal() as db:
        db.add(Rule(
            tenant_id=1, rule_id=f"ESC-TRIG-{uuid.uuid4().hex[:6]}", source_kind="escalation",
            condition={"issue_type": ["remote_unlock"]}, action={"decision": "ESCALATE"},
            forbid=["remote_unlock_promise"], priority=1000, status="ACTIVE",
            conflict_group="escalation",
        ))
        db.commit()


def test_high_risk_rule_creates_handoff(client, monkeypatch):
    _escalation_rule()
    monkeypatch.setattr(knowledge_retrieval, "search",
                        lambda db, q, **k: {"hits": [HIT_REMOTE], "debug": {"latency_ms": 3}})
    token = customer_token(client, "buyer_zhang")
    cid = _conversation(client, token)
    _stream(client, token, cid, "能帮我远程开锁吗")  # 命中 HIT_REMOTE 后触发护栏
    rows = _open_handoffs(cid)
    assert rows and rows[0].reason == "HIGH_RISK_RULE"


def test_no_hit_second_time_creates_handoff(client, monkeypatch):
    monkeypatch.setattr(knowledge_retrieval, "search",
                        lambda db, q, **k: {"hits": [], "debug": {"latency_ms": 3}})
    token = customer_token(client, "buyer_zhang")
    cid = _conversation(client, token)
    _stream(client, token, cid, "完全查不到的问题甲 abcdefg")
    assert _open_handoffs(cid) == [], "首次拒答不应转人工"
    _stream(client, token, cid, "完全查不到的问题乙 abcdefg")
    rows = _open_handoffs(cid)
    assert rows and rows[0].reason == "NO_HIT"


def test_model_error_creates_handoff(client, monkeypatch):
    monkeypatch.setattr(knowledge_retrieval, "search",
                        lambda db, q, **k: {"hits": [HIT], "debug": {"latency_ms": 3}})

    def boom(*args, **kwargs):
        raise RuntimeError("模型超时")

    monkeypatch.setattr("app.integrations.llm.stream_chat", boom)
    token = customer_token(client, "buyer_zhang")
    cid = _conversation(client, token)
    _stream(client, token, cid, "门锁电池能用多久")
    rows = _open_handoffs(cid)
    assert rows and rows[0].reason == "MODEL_ERROR"


def test_handoff_is_idempotent_per_conversation(client, monkeypatch):
    _escalation_rule()
    monkeypatch.setattr(knowledge_retrieval, "search",
                        lambda db, q, **k: {"hits": [HIT_REMOTE], "debug": {"latency_ms": 3}})
    token = customer_token(client, "buyer_zhang")
    cid = _conversation(client, token)
    for _ in range(3):
        _stream(client, token, cid, "帮我远程开门")
    assert len(_open_handoffs(cid)) == 1, "同一会话只能有一个未决转人工"
