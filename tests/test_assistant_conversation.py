"""会话与流式：可见性、关闭、SSE 事件序列、心跳、幂等、限流、清理。"""
import json
import time
import uuid
from datetime import timedelta

from sqlalchemy import select

from app.api.v1.assistant import _iter_with_heartbeat
from app.core.config import settings
from app.core.db import SessionLocal
from app.models.generated import Conversation, Message
from app.services.common import now
from tests.conftest import auth, customer_token, new_key


def _create(client, token) -> dict:
    response = client.post("/api/v1/ai/conversations", headers=auth(token, new_key()), json={})
    assert response.status_code == 200, response.text
    return response.json()


def _stream(client, token, conversation_id, content, client_msg_id=None) -> tuple[int, str]:
    body = {"content": content}
    if client_msg_id:
        body["client_msg_id"] = client_msg_id
    with client.stream("POST", f"/api/v1/ai/conversations/{conversation_id}/messages:stream",
                       headers=auth(token, new_key()), json=body) as response:
        text = "".join(response.iter_text())
        return response.status_code, text


def _events(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.strip().split("\n\n"):
        name, data = None, {}
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        if name:
            events.append((name, data))
    return events


def test_create_conversation_and_party(client):
    token = customer_token(client, "buyer_zhang")
    conversation = _create(client, token)
    assert conversation["status"] == "OPEN" and conversation["conversation_no"].startswith("CV")
    with SessionLocal() as db:
        row = db.get(Conversation, conversation["id"])
        assert row.party == "CUSTOMER"


def test_guest_conversation_party(client):
    guest = client.post("/api/v1/auth/guest-session", json={"display_name": "访客甲"})
    assert guest.status_code == 200, guest.text
    token = guest.json()["access_token"]
    conversation = _create(client, token)
    with SessionLocal() as db:
        assert db.get(Conversation, conversation["id"]).party == "GUEST"


def test_closed_conversation_rejects_stream(client):
    token = customer_token(client, "buyer_zhang")
    conversation = _create(client, token)
    closed = client.post(f"/api/v1/ai/conversations/{conversation['id']}/close",
                         headers=auth(token, new_key()))
    assert closed.status_code == 200, closed.text
    status, _ = _stream(client, token, conversation["id"], "还在吗")
    assert status == 409


def test_other_customer_cannot_see_conversation(client):
    alice = customer_token(client, "buyer_zhang")
    bob = customer_token(client, "buyer_li")
    conversation = _create(client, alice)
    response = client.get(f"/api/v1/ai/conversations/{conversation['id']}",
                          headers=auth(bob, new_key()))
    assert response.status_code == 404


def test_stream_event_order_and_message_persistence(client):
    token = customer_token(client, "buyer_zhang")
    conversation = _create(client, token)
    status, text = _stream(client, token, conversation["id"], "门锁没电了怎么办")
    assert status == 200, text
    names = [name for name, _ in _events(text)]
    assert names[0] == "meta"
    assert "delta" in names
    assert names.index("citations") < names.index("done")
    assert names[-1] == "done"

    with SessionLocal() as db:
        rows = db.execute(
            select(Message).where(Message.conversation_id == conversation["id"]).order_by(Message.seq)
        ).scalars().all()
    assert [row.role for row in rows] == ["USER", "ASSISTANT"]
    assert [row.seq for row in rows] == [1, 2]
    assert rows[1].status in ("DONE", "REFUSED")
    assert rows[1].content


def test_client_msg_id_is_idempotent(client):
    token = customer_token(client, "buyer_zhang")
    conversation = _create(client, token)
    key = uuid.uuid4().hex
    _stream(client, token, conversation["id"], "第一条问题", client_msg_id=key)
    status, text = _stream(client, token, conversation["id"], "第一条问题", client_msg_id=key)
    assert status == 200
    events = _events(text)
    assert events[0][0] == "meta" and events[0][1].get("replayed") is True
    with SessionLocal() as db:
        rows = db.execute(
            select(Message).where(Message.conversation_id == conversation["id"])
        ).scalars().all()
    assert len(rows) == 2  # 没有产生新消息


def test_heartbeat_is_emitted_while_idle():
    def slow():
        time.sleep(0.12)
        yield "片段"

    stream = _iter_with_heartbeat(slow(), interval=0.03)
    kinds = [kind for kind, _ in stream]
    assert "ping" in kinds
    assert kinds[-1] == "delta"


def test_rate_limit_and_length(client):
    token = customer_token(client, "buyer_zhang")
    conversation = _create(client, token)
    original = settings.assistant_rate_limit_per_minute
    settings.assistant_rate_limit_per_minute = 0
    try:
        status, _ = _stream(client, token, conversation["id"], "限流测试")
        assert status == 429
    finally:
        settings.assistant_rate_limit_per_minute = original

    too_long = "字" * (settings.assistant_message_max_chars + 1)
    status, _ = _stream(client, token, conversation["id"], too_long)
    assert status == 422


def test_cleanup_marks_zombie_and_purges_expired(client):
    token = customer_token(client, "buyer_zhang")
    conversation = _create(client, token)
    _stream(client, token, conversation["id"], "会被清理的会话")
    from scripts.assistant_cleanup import purge_closed_conversations, purge_stale_streaming

    with SessionLocal() as db:
        row = db.get(Conversation, conversation["id"])
        row.status = "CLOSED"
        # last_message_at 不受 touch 触发器影响，可作为"最后活动时间"回溯
        row.last_message_at = now() - timedelta(days=400)
        # 僵尸消息用 INSERT 造：UPDATE 会被 tg_touch_updated_at 触发器刷成 now()
        db.add(Message(
            tenant_id=1, conversation_id=conversation["id"], seq=99, role="ASSISTANT",
            content="", status="STREAMING", updated_at=now() - timedelta(minutes=10),
        ))
        db.commit()
        conversation_id = conversation["id"]
        assert purge_stale_streaming(db) >= 1
        db.commit()

    with SessionLocal() as db:
        assert purge_closed_conversations(db, days=90) >= 1
        db.commit()
        assert db.get(Conversation, conversation_id) is None
        remaining = db.execute(
            select(Message).where(Message.conversation_id == conversation_id)
        ).scalars().all()
    assert remaining == []  # 级联删除
