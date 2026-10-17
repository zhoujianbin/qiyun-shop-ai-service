"""客户端断流：占位消息必须落终态，不能留下永远 STREAMING 的空消息。"""
from sqlalchemy import select

from app.api.v1 import assistant as assistant_api
from app.core.db import SessionLocal
from app.models.generated import Conversation, Message
from tests.conftest import auth, customer_token, new_key


def _new_conversation(client, token):
    return client.post("/api/v1/ai/conversations", headers=auth(token, new_key()), json={}).json()


def test_finalize_abort_marks_message_failed(client):
    """直接验证断流兜底函数（TestClient 会读完流，无法真实模拟断开）。"""
    token = customer_token(client)
    conv = _new_conversation(client, token)
    with SessionLocal() as db:
        from app.services import assistant_conversation as conversation_service

        message = conversation_service.append_message(
            db, conv["id"], role="ASSISTANT", content="", status="STREAMING")
        db.commit()
        assistant_api._LIVE[message.id] = "半截内容"
        assistant_api._finalize_abort(db, message, ["半截", "内容"], __import__("time").monotonic(), None)
        db.commit()
        row = db.get(Message, message.id)
        assert row.status == "FAILED"
        assert row.content == "半截内容"
        assert (row.metadata_json or {}).get("error_code") == "CLIENT_ABORTED"
        assert message.id not in assistant_api._LIVE


def test_conversation_title_comes_from_first_question(client):
    token = customer_token(client)
    conv = _new_conversation(client, token)
    with client.stream("POST", f"/api/v1/ai/conversations/{conv['id']}/messages:stream",
                       headers=auth(token), json={"content": "门锁电池能用多久"}) as response:
        "".join(response.iter_text())
    with SessionLocal() as db:
        row = db.get(Conversation, conv["id"])
        assert row.title and "门锁" in row.title
