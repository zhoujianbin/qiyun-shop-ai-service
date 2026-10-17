"""身份核验与转人工：订单号 + 收货手机后四位、固定事实快照、认领制交接。"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError, Conflict, NotFound, ValidationError
from app.models.generated import Conversation, Handoff, IdentityVerification
from app.services import audit
from app.services.common import now

VERIFY_TTL_MINUTES = 30
MAX_ATTEMPTS = 3
UNIFIED_FAIL_MESSAGE = "核验未通过，请核对订单号与下单手机号后四位。"
SNAPSHOT_FIELDS = ("order_no", "status", "paid_amount", "created_at",
                   "fulfillment_status", "tracking_no")


def _order(db: Session, order_no: str):
    from app.models import Order

    return db.execute(
        select(Order).where(Order.tenant_id == settings.tenant_id, Order.order_no == order_no)
    ).scalar_one_or_none()


def _attempts(db: Session, conversation_id: int) -> int:
    return len(db.execute(
        select(IdentityVerification.id).where(
            IdentityVerification.conversation_id == conversation_id,
            IdentityVerification.status == "FAILED",
        )
    ).scalars().all())


def active_verification(db: Session, conversation_id: int) -> IdentityVerification | None:
    row = db.execute(
        select(IdentityVerification).where(
            IdentityVerification.conversation_id == conversation_id,
            IdentityVerification.status == "VERIFIED",
        ).order_by(IdentityVerification.id.desc())
    ).scalars().first()
    if row is None or row.expires_at is None or row.expires_at <= now():
        return None
    return row


def verify_identity(db: Session, actor: dict, conversation: Conversation, *, order_no: str,
                    phone_tail: str) -> dict:
    if conversation.status == "CLOSED":
        raise Conflict("CONVERSATION_CLOSED", "会话已关闭")
    order_no = (order_no or "").strip()
    phone_tail = (phone_tail or "").strip()
    if not order_no or len(phone_tail) != 4 or not phone_tail.isdigit():
        raise ValidationError("需要订单号与手机号后四位（4 位数字）")

    if _attempts(db, conversation.id) >= MAX_ATTEMPTS:
        create_handoff(db, actor, conversation, reason="IDENTITY_FAILED")
        raise AppError("IDENTITY_LOCKED", "核验次数已用尽，已转人工处理", 429)

    order = _order(db, order_no)
    phone = (order.receiver_phone or "").strip() if order is not None else ""
    ok = order is not None and phone[-4:] == phone_tail
    row = IdentityVerification(
        tenant_id=settings.tenant_id,
        conversation_id=conversation.id,
        order_no=order_no,
        phone_tail=phone_tail,
        order_id=order.id if (ok and order is not None) else None,
        customer_id=order.customer_id if (ok and order is not None) else None,
        status="VERIFIED" if ok else "FAILED",
        attempts=_attempts(db, conversation.id) + 1,
        expires_at=now() + timedelta(minutes=VERIFY_TTL_MINUTES) if ok else None,
    )
    db.add(row)
    db.flush()
    audit.record(db, actor, "ai.identity.verify", "assistant.identity_verification", row.id,
                 after={"status": row.status})
    if not ok:
        if _attempts(db, conversation.id) >= MAX_ATTEMPTS:
            create_handoff(db, actor, conversation, reason="IDENTITY_FAILED")
        return {"verified": False, "message": UNIFIED_FAIL_MESSAGE, "attempts": row.attempts,
                "max_attempts": MAX_ATTEMPTS}
    return {"verified": True, "expires_at": row.expires_at.isoformat(),
            "snapshot": order_fact_snapshot(db, order)}


def order_fact_snapshot(db: Session, order) -> dict:
    """固定事实快照：只返回 6 字段白名单，永不返回手机号/地址/卡号。"""
    from app.models import Shipment

    shipment = db.execute(
        select(Shipment).where(Shipment.order_id == order.id).order_by(Shipment.id.desc())
    ).scalars().first()
    return {
        "order_no": order.order_no,
        "status": order.status,
        "paid_amount": str(order.paid_amount),
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "fulfillment_status": order.fulfillment_status,
        "tracking_no": (shipment.tracking_no if shipment is not None else None),
    }


def handoff_view(row: Handoff, conversation: Conversation | None = None) -> dict:
    return {
        "id": row.id,
        "conversation_id": row.conversation_id,
        "conversation_no": conversation.conversation_no if conversation is not None else None,
        "title": conversation.title if conversation is not None else None,
        "message_count": conversation.message_count if conversation is not None else None,
        "reason": row.reason,
        "status": row.status,
        "assignee_id": row.assignee_id,
        "summary": row.summary,
        "claimed_at": row.claimed_at.isoformat() if row.claimed_at else None,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def create_handoff(db: Session, actor: dict, conversation: Conversation, *, reason: str,
                   summary: str | None = None) -> dict:
    existing = db.execute(
        select(Handoff).where(
            Handoff.conversation_id == conversation.id,
            Handoff.status.in_(("OPEN", "CLAIMED")),
        )
    ).scalar_one_or_none()
    if existing is not None:
        return handoff_view(existing, conversation)
    row = Handoff(
        tenant_id=settings.tenant_id,
        conversation_id=conversation.id,
        reason=reason,
        status="OPEN",
        summary=summary,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:  # 并发创建，返回已存在的
        db.rollback()
        existing = db.execute(
            select(Handoff).where(Handoff.conversation_id == conversation.id,
                                  Handoff.status.in_(("OPEN", "CLAIMED")))
        ).scalar_one()
        return handoff_view(existing, conversation)
    audit.record(db, actor, "ai.handoff.create", "assistant.handoff", row.id, after={"reason": reason})
    audit.emit(db, "ai.handoff.created", "conversation", conversation.id, {"reason": reason})
    return handoff_view(row, conversation)


def list_handoffs(db: Session, *, status: str | None = None) -> list[dict]:
    statement = select(Handoff).where(Handoff.tenant_id == settings.tenant_id)
    if status:
        statement = statement.where(Handoff.status == status.upper())
    rows = db.execute(statement.order_by(Handoff.id)).scalars().all()
    conversations = {
        item.id: item for item in db.execute(
            select(Conversation).where(Conversation.id.in_({row.conversation_id for row in rows}))
        ).scalars().all()
    } if rows else {}
    return [handoff_view(row, conversations.get(row.conversation_id)) for row in rows]


def _load(db: Session, handoff_id: int) -> Handoff:
    row = db.get(Handoff, handoff_id)
    if row is None or row.tenant_id != settings.tenant_id:
        raise NotFound("转人工记录不存在")
    return row


def claim_handoff(db: Session, actor: dict, handoff_id: int) -> dict:
    row = _load(db, handoff_id)
    if row.status == "CLOSED":
        raise Conflict("HANDOFF_CLOSED", "记录已关闭")
    if row.status == "CLAIMED" and row.assignee_id != actor.get("id"):
        raise Conflict("ALREADY_CLAIMED", "已被他人认领")
    row.status = "CLAIMED"
    row.assignee_id = actor.get("id")
    row.claimed_at = row.claimed_at or now()
    conversation = db.get(Conversation, row.conversation_id)
    if conversation is not None:
        conversation.ai_paused = True
    audit.record(db, actor, "ai.handoff.claim", "assistant.handoff", row.id)
    audit.emit(db, "ai.handoff.claimed", "conversation", row.conversation_id, {"handoff_id": row.id})
    db.flush()
    return handoff_view(row, conversation)


def close_handoff(db: Session, actor: dict, handoff_id: int, *, summary: str | None,
                  back_to_ai: bool = False) -> dict:
    row = _load(db, handoff_id)
    if row.status == "CLOSED":
        raise Conflict("HANDOFF_CLOSED", "记录已关闭")
    if not (summary or "").strip():
        raise ValidationError("关闭转人工必须填写结论")
    row.status = "CLOSED"
    row.summary = summary.strip()
    row.closed_at = now()
    conversation = db.get(Conversation, row.conversation_id)
    if conversation is not None and back_to_ai:
        conversation.ai_paused = False
    audit.record(db, actor, "ai.handoff.close", "assistant.handoff", row.id,
                 after={"back_to_ai": back_to_ai})
    audit.emit(db, "ai.handoff.closed", "conversation", row.conversation_id, {"handoff_id": row.id})
    db.flush()
    return handoff_view(row, conversation)


def agent_message(db: Session, actor: dict, conversation: Conversation, content: str) -> dict:
    from app.services import assistant_conversation as conversation_service

    if not (content or "").strip():
        raise ValidationError("回复内容不能为空")
    message = conversation_service.append_message(
        db, conversation.id, role="AGENT", content=content.strip(), status="DONE")
    audit.record(db, actor, "ai.conversation.agent_reply", "assistant.message", message.id)
    return conversation_service.message_view(message)
