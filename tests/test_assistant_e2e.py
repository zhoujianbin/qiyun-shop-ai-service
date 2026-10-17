"""三期端到端演练：知识问答 → 引用 → 核验 → 转人工 → 接单 → 人工回话 → 关单。"""
import json

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import CustomerProfile, Order
from app.models.generated import Conversation, Handoff, Message
from app.services import knowledge_retrieval
from tests.conftest import auth, customer_token, new_key

HIT = {
    "source_type": "chunk", "chunk_id": 201, "document_id": "KB-PROD-QLL3P-MASTER",
    "document_pk": 1, "version": 1, "chunk_ord": 0, "title_path": "产品知识 / 智能门锁",
    "line_start": 14, "line_end": 16, "snippet": "QL-L3P 使用 8 节 5 号电池，约 12 个月。",
}


def test_full_journey(client, monkeypatch):
    monkeypatch.setattr(
        knowledge_retrieval, "search",
        lambda db, q, **kw: {"hits": [HIT], "debug": {"latency_ms": 4, "candidates": 1}},
    )
    customer = customer_token(client, "buyer_zhang")
    admin = client.post("/api/v1/auth/staff/login",
                        json={"username": "admin", "password": "Qiyun@2026#Dev"}).json()["access_token"]

    conversation = client.post("/api/v1/ai/conversations",
                               headers=auth(customer, new_key()), json={}).json()
    cid = conversation["id"]

    with client.stream("POST", f"/api/v1/ai/conversations/{cid}/messages:stream",
                       headers=auth(customer, new_key()),
                       json={"content": "门锁电池能用多久"}) as response:
        body = "".join(response.iter_text())
    assert "event: citations" in body and "KB-PROD-QLL3P-MASTER" in body
    assert "event: done" in body
    with SessionLocal() as db:
        answer = db.execute(select(Message).where(Message.conversation_id == cid,
                                                  Message.role == "ASSISTANT")).scalars().first()
        assert answer.status in ("DONE", "REFUSED")

    with SessionLocal() as db:
        profile = db.execute(select(CustomerProfile)).scalars().first()
        order_no = f"E2E{cid}"
        db.add(Order(tenant_id=1, order_no=order_no, channel_account_id=1, customer_id=profile.id,
                     receiver_name="演练", receiver_phone="13800002222", shipping_address={}))
        db.commit()
    verified = client.post(f"/api/v1/ai/conversations/{cid}/identity",
                           headers=auth(customer, new_key()),
                           json={"order_no": order_no, "phone_tail": "2222"})
    assert verified.status_code == 200 and verified.json()["verified"] is True
    assert "13800002222" not in json.dumps(verified.json(), ensure_ascii=False)

    handoff = client.post(f"/api/v1/ai/conversations/{cid}/handoff",
                          headers=auth(customer, new_key())).json()
    claimed = client.post(f"/api/v1/ai/handoffs/{handoff['id']}/claim",
                          headers=auth(admin, new_key()))
    assert claimed.status_code == 200
    with SessionLocal() as db:
        assert db.get(Conversation, cid).ai_paused is True
    paused = client.post(f"/api/v1/ai/conversations/{cid}/messages:stream",
                         headers=auth(customer, new_key()), json={"content": "还有人吗"})
    assert paused.status_code == 409

    reply = client.post(f"/api/v1/ai/conversations/{cid}/agent-messages",
                        headers=auth(admin, new_key()), json={"content": "我是人工客服，请讲"})
    assert reply.json()["role"] == "AGENT"

    closed = client.post(f"/api/v1/ai/handoffs/{handoff['id']}/close",
                         headers=auth(admin, new_key()),
                         json={"summary": "已电话解决", "back_to_ai": True})
    assert closed.status_code == 200
    with SessionLocal() as db:
        assert db.get(Conversation, cid).ai_paused is False
        assert db.get(Handoff, handoff["id"]).status == "CLOSED"
    print("E2E OK: 会话/问答/引用/核验/转人工/接单/回话/关单 全链路通过")
