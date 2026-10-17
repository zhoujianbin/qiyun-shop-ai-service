"""四期写操作：待确认动作的生成、确认幂等、过期与取消。"""
from datetime import timedelta

import pytest
from sqlalchemy import select, text

from app.core.db import SessionLocal
from app.core.errors import Conflict
from app.models.generated import AppUser, AuditLog, CustomerProfile, PendingAction
from app.services import action, assistant_conversation as conversation_service, assistant_handoff
from app.services.common import now
from tests.conftest import customer_token  # noqa: F401 - 复用既有夹具
from tests.helpers import create_order, first_purchasable_sku


def _customer(db):
    user = db.execute(select(AppUser).where(AppUser.username == "buyer_zhang")).scalar_one()
    profile = db.execute(select(CustomerProfile).where(
        CustomerProfile.user_id == user.id)).scalar_one_or_none()
    customer_id = profile.id if profile is not None else user.id
    return {"id": user.id, "party": "CUSTOMER", "customer_id": customer_id,
            "label": user.display_name}


def _conversation_with_message(db, actor):
    conv = conversation_service.create_conversation(db, actor)
    msg = conversation_service.append_message(
        db, conv["id"], role="ASSISTANT", content="", status="STREAMING")
    return conv, msg


def _order(client, token):
    picked = first_purchasable_sku(client)
    return create_order(client, token, sku_id=picked["sku"]["id"], quantity=1)


def test_propose_does_not_change_order_and_confirm_executes_once(client):
    token = customer_token(client)
    order = _order(client, token)
    with SessionLocal() as db:
        actor = _customer(db)
        conv, msg = _conversation_with_message(db, actor)
        # 绕过真实核验，直接造一条 VERIFIED 记录（核验逻辑本身另一组用例覆盖）
        db.execute(text("insert into assistant.identity_verification"
                        " (tenant_id, conversation_id, order_no, phone_tail, status, attempts, expires_at)"
                        " values (1, :cid, :order_no, '0000', 'VERIFIED', 1, :exp)"),
                   {"cid": conv["id"], "order_no": order["order_no"],
                    "exp": now() + timedelta(minutes=30)})
        db.commit()

        proposed = action.propose(db, actor, conversation=_conv(db, conv["id"]), message_id=msg.id,
                                  tool_name="cancel_order",
                                  args={"order_no": order["order_no"], "reason": "不想要了"})
        assert proposed["status"] == "PROPOSED"
        # 生成动作本身不改业务数据
        row = db.execute(text("select status from commerce.orders where order_no=:no"),
                         {"no": order["order_no"]}).scalar_one()
        assert row != "CANCELLED"

        first = action.confirm(db, actor, proposed["id"])
        assert first["status"] == "EXECUTED"
        row = db.execute(text("select status from commerce.orders where order_no=:no"),
                         {"no": order["order_no"]}).scalar_one()
        assert row == "CANCELLED"

        again = action.confirm(db, actor, proposed["id"])
        assert again["status"] == "EXECUTED"
        assert again["result"] == first["result"]

        actions_logged = db.execute(select(AuditLog).where(
            AuditLog.action.in_(["ai.action.propose", "ai.action.confirm", "ai.action.executed"]))
        ).scalars().all()
        assert {row.action for row in actions_logged} >= {
            "ai.action.propose", "ai.action.confirm", "ai.action.executed"}


def _conv(db, conversation_id):
    from app.models.generated import Conversation

    return db.get(Conversation, conversation_id)


def test_expired_action_cannot_be_confirmed(client):
    token = customer_token(client)
    order = _order(client, token)
    with SessionLocal() as db:
        actor = _customer(db)
        conv, msg = _conversation_with_message(db, actor)
        db.execute(text("insert into assistant.identity_verification"
                        " (tenant_id, conversation_id, order_no, phone_tail, status, attempts, expires_at)"
                        " values (1, :cid, :order_no, '0000', 'VERIFIED', 1, :exp)"),
                   {"cid": conv["id"], "order_no": order["order_no"],
                    "exp": now() + timedelta(minutes=30)})
        db.commit()
        proposed = action.propose(db, actor, conversation=_conv(db, conv["id"]), message_id=msg.id,
                                  tool_name="cancel_order", args={"order_no": order["order_no"]})
        db.execute(text("update assistant.pending_action set expires_at = :t where id = :i"),
                   {"t": now() - timedelta(minutes=1), "i": proposed["id"]})
        db.commit()
        with pytest.raises(Conflict) as exc:
            action.confirm(db, actor, proposed["id"])
        assert exc.value.code == "ACTION_EXPIRED"
        row = db.execute(text("select status from commerce.orders where order_no=:no"),
                         {"no": order["order_no"]}).scalar_one()
        assert row != "CANCELLED"


def test_cancel_action_marks_cancelled(client):
    token = customer_token(client)
    order = _order(client, token)
    with SessionLocal() as db:
        actor = _customer(db)
        conv, msg = _conversation_with_message(db, actor)
        proposed = action.propose(db, actor, conversation=_conv(db, conv["id"]), message_id=msg.id,
                                  tool_name="cancel_order", args={"order_no": order["order_no"]})
        cancelled = action.cancel(db, actor, proposed["id"])
        assert cancelled["status"] == "CANCELLED"
        with pytest.raises(Conflict):
            action.confirm(db, actor, proposed["id"])


def test_action_key_is_stable_and_propose_is_idempotent(client):
    token = customer_token(client)
    order = _order(client, token)
    with SessionLocal() as db:
        actor = _customer(db)
        conv, msg = _conversation_with_message(db, actor)
        args = {"order_no": order["order_no"], "reason": "不想要了"}
        first = action.propose(db, actor, conversation=_conv(db, conv["id"]), message_id=msg.id,
                              tool_name="cancel_order", args=args)
        second = action.propose(db, actor, conversation=_conv(db, conv["id"]), message_id=msg.id,
                               tool_name="cancel_order", args=args)
        assert first["id"] == second["id"]
        rows = db.execute(select(PendingAction).where(
            PendingAction.conversation_id == conv["id"])).scalars().all()
        assert len(rows) == 1
        assert action.action_key("cancel_order", args) == action.action_key("cancel_order", args)
