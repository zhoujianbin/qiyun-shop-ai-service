"""身份核验与转人工：快照白名单、统一失败话术、失败计数、认领与 AI 暂停、关单结论。"""
import uuid

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import CustomerProfile, Order
from app.models.generated import Conversation, Handoff, IdentityVerification
from tests.conftest import auth, customer_token, new_key

PHONE = "13900001111"


def _make_order() -> tuple[int, str, int]:
    with SessionLocal() as db:
        profile = db.execute(select(CustomerProfile)).scalars().first()
        order_no = f"T{uuid.uuid4().hex[:12].upper()}"
        order = Order(
            tenant_id=1, order_no=order_no, channel_account_id=1, customer_id=profile.id,
            receiver_name="测试收货人", receiver_phone=PHONE, shipping_address={},
        )
        db.add(order)
        db.commit()
        return order.id, order_no, profile.id


def _conversation(client, token) -> dict:
    response = client.post("/api/v1/ai/conversations", headers=auth(token, new_key()), json={})
    assert response.status_code == 200, response.text
    return response.json()


def test_verify_success_returns_six_field_snapshot(client):
    token = customer_token(client, "buyer_zhang")
    conversation = _conversation(client, token)
    _, order_no, _ = _make_order()
    response = client.post(f"/api/v1/ai/conversations/{conversation['id']}/identity",
                           headers=auth(token, new_key()),
                           json={"order_no": order_no, "phone_tail": PHONE[-4:]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verified"] is True
    snapshot = body["snapshot"]
    assert set(snapshot) == {"order_no", "status", "paid_amount", "created_at",
                             "fulfillment_status", "tracking_no"}
    text = str(snapshot)
    assert PHONE not in text and "测试收货人" not in text


def test_wrong_tail_uses_unified_message(client):
    token = customer_token(client, "buyer_zhang")
    conversation = _conversation(client, token)
    _, order_no, _ = _make_order()
    response = client.post(f"/api/v1/ai/conversations/{conversation['id']}/identity",
                           headers=auth(token, new_key()),
                           json={"order_no": order_no, "phone_tail": "0000"})
    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is False
    assert body["message"] == "核验未通过，请核对订单号与下单手机号后四位。"

    missing = client.post(f"/api/v1/ai/conversations/{conversation['id']}/identity",
                          headers=auth(token, new_key()),
                          json={"order_no": "NO-SUCH-ORDER", "phone_tail": "0000"})
    assert missing.json()["message"] == body["message"]  # 不可枚举


def test_three_failures_lock_and_create_handoff(client):
    token = customer_token(client, "buyer_zhang")
    conversation = _conversation(client, token)
    for _ in range(3):
        client.post(f"/api/v1/ai/conversations/{conversation['id']}/identity",
                    headers=auth(token, new_key()),
                    json={"order_no": "NO-SUCH-ORDER", "phone_tail": "0000"})
    blocked = client.post(f"/api/v1/ai/conversations/{conversation['id']}/identity",
                          headers=auth(token, new_key()),
                          json={"order_no": "NO-SUCH-ORDER", "phone_tail": "0000"})
    assert blocked.status_code == 429
    with SessionLocal() as db:
        rows = db.execute(select(Handoff).where(
            Handoff.conversation_id == conversation["id"])).scalars().all()
    assert rows and rows[0].reason == "IDENTITY_FAILED"


def test_claim_pauses_ai_and_close_resumes(client):
    admin = client.post("/api/v1/auth/staff/login",
                        json={"username": "admin", "password": "Qiyun@2026#Dev"}).json()["access_token"]
    token = customer_token(client, "buyer_zhang")
    conversation = _conversation(client, token)
    created = client.post(f"/api/v1/ai/conversations/{conversation['id']}/handoff",
                          headers=auth(token, new_key()))
    assert created.status_code == 200, created.text
    handoff_id = created.json()["id"]

    claimed = client.post(f"/api/v1/ai/handoffs/{handoff_id}/claim",
                          headers=auth(admin, new_key()))
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["status"] == "CLAIMED"
    with SessionLocal() as db:
        assert db.get(Conversation, conversation["id"]).ai_paused is True

    paused = client.stream("POST", f"/api/v1/ai/conversations/{conversation['id']}/messages:stream",
                           headers=auth(token, new_key()), json={"content": "还在吗"})
    with paused as response:
        assert response.status_code == 409

    rejected = client.post(f"/api/v1/ai/handoffs/{handoff_id}/close",
                           headers=auth(admin, new_key()), json={"summary": ""})
    assert rejected.status_code == 422

    closed = client.post(f"/api/v1/ai/handoffs/{handoff_id}/close",
                         headers=auth(admin, new_key()),
                         json={"summary": "已电话解决", "back_to_ai": True})
    assert closed.status_code == 200, closed.text
    with SessionLocal() as db:
        assert db.get(Conversation, conversation["id"]).ai_paused is False


def test_agent_message_joins_same_timeline(client):
    admin = client.post("/api/v1/auth/staff/login",
                        json={"username": "admin", "password": "Qiyun@2026#Dev"}).json()["access_token"]
    token = customer_token(client, "buyer_zhang")
    conversation = _conversation(client, token)
    response = client.post(f"/api/v1/ai/conversations/{conversation['id']}/agent-messages",
                           headers=auth(admin, new_key()), json={"content": "我是人工客服"})
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "AGENT"
    items = client.get(f"/api/v1/ai/conversations/{conversation['id']}/messages",
                       headers=auth(token, new_key())).json()["items"]
    assert any(item["role"] == "AGENT" for item in items)


def test_customer_cannot_claim_handoff(client):
    token = customer_token(client, "buyer_zhang")
    response = client.post("/api/v1/ai/handoffs/1/claim", headers=auth(token, new_key()))
    assert response.status_code == 403
