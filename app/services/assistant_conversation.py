"""会话与消息：创建、可见性、序号分配、上下文窗口、限流。"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError, Conflict, NotFound, ValidationError
from app.models.generated import Conversation, Handoff, Message
from app.services.common import now, seq

SYSTEM_TITLE_CHARS = 30


def conversation_view(conversation: Conversation) -> dict:
    return {
        "id": conversation.id,
        "conversation_no": conversation.conversation_no,
        "status": conversation.status,
        "ai_paused": conversation.ai_paused,
        "message_count": conversation.message_count,
        "title": conversation.title,
        "last_message_at": conversation.last_message_at.isoformat() if conversation.last_message_at else None,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
    }


def message_view(message: Message) -> dict:
    return {
        "id": message.id,
        "seq": message.seq,
        "role": message.role,
        "content": message.content,
        "status": message.status,
        "metadata": message.metadata_json or {},
        "model": message.model,
        "latency_ms": message.latency_ms,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


def create_conversation(db: Session, actor: dict, *, channel_account_id: int | None = None) -> dict:
    party = "GUEST" if actor.get("party") == "GUEST" else "CUSTOMER"
    conversation = Conversation(
        tenant_id=settings.tenant_id,
        conversation_no=seq("CV"),
        user_id=actor["id"],
        party=party,
        channel_account_id=channel_account_id,
        status="OPEN",
    )
    db.add(conversation)
    db.flush()
    from app.services import audit

    audit.record(db, actor, "ai.conversation.create", "assistant.conversation", conversation.id,
                 after={"party": party})
    return conversation_view(conversation)


def _is_assignee(db: Session, conversation_id: int, user_id: int | None) -> bool:
    if not user_id:
        return False
    return db.execute(
        select(Handoff.id).where(
            Handoff.conversation_id == conversation_id,
            Handoff.assignee_id == user_id,
            Handoff.status.in_(("OPEN", "CLAIMED")),
        )
    ).first() is not None


def ensure_visible(db: Session, conversation_id: int, *, actor: dict, staff: bool) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.tenant_id != settings.tenant_id:
        raise NotFound("会话不存在")
    if conversation.user_id == actor.get("id") or staff or _is_assignee(db, conversation_id, actor.get("id")):
        return conversation
    raise NotFound("会话不存在")


def list_conversations(db: Session, *, actor: dict, staff: bool, page: int, page_size: int) -> dict:
    statement = select(Conversation).where(Conversation.tenant_id == settings.tenant_id)
    if not staff:
        statement = statement.where(Conversation.user_id == actor["id"])
    total = db.execute(select(func.count()).select_from(statement.subquery())).scalar_one()
    rows = db.execute(
        statement.order_by(Conversation.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    return {
        "page": page, "page_size": page_size, "total": total,
        "items": [conversation_view(row) for row in rows],
        "meta": {"page": page, "page_size": page_size, "total": total},
    }


def close_conversation(db: Session, conversation: Conversation, actor: dict) -> dict:
    if conversation.status == "CLOSED":
        raise Conflict("CONVERSATION_CLOSED", "会话已关闭")
    conversation.status = "CLOSED"
    db.flush()
    from app.services import audit

    audit.record(db, actor, "ai.conversation.close", "assistant.conversation", conversation.id)
    return conversation_view(conversation)


def list_messages(db: Session, conversation_id: int, *, after_seq: int | None = None,
                  page: int = 1, page_size: int = 20) -> dict:
    statement = select(Message).where(Message.conversation_id == conversation_id)
    if after_seq is not None:
        statement = statement.where(Message.seq > after_seq)
        rows = db.execute(statement.order_by(Message.seq).limit(page_size)).scalars().all()
        return {"items": [message_view(row) for row in rows],
                "meta": {"after_seq": after_seq, "count": len(rows)}}
    rows = db.execute(
        statement.order_by(Message.seq.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    total = db.execute(select(func.count()).select_from(Message).where(
        Message.conversation_id == conversation_id)).scalar_one()
    return {"items": [message_view(row) for row in reversed(rows)],
            "meta": {"page": page, "page_size": page_size, "total": total}}


def find_by_client_id(db: Session, conversation_id: int, client_msg_id: str | None) -> Message | None:
    if not client_msg_id:
        return None
    return db.execute(
        select(Message).where(
            Message.conversation_id == conversation_id,
            Message.client_msg_id == client_msg_id,
        )
    ).scalar_one_or_none()


def append_message(db: Session, conversation_id: int, *, role: str, content: str,
                   status: str = "DONE", client_msg_id: str | None = None,
                   metadata: dict | None = None) -> Message:
    """分配 seq：锁会话行，保证会话内连续无空洞。"""
    conversation = db.execute(
        select(Conversation).where(Conversation.id == conversation_id).with_for_update()
    ).scalar_one()
    next_seq = int(conversation.message_count) + 1
    message = Message(
        tenant_id=settings.tenant_id,
        conversation_id=conversation_id,
        seq=next_seq,
        role=role,
        content=content,
        status=status,
        client_msg_id=client_msg_id,
        metadata_json=metadata or {},
    )
    db.add(message)
    conversation.message_count = next_seq
    conversation.last_message_at = now()
    if not conversation.title and role == "USER" and content.strip():
        conversation.title = content.strip()[:SYSTEM_TITLE_CHARS]
    db.flush()
    return message


def context_messages(db: Session, conversation_id: int, rounds: int | None = None) -> list[dict]:
    rounds = rounds or settings.assistant_context_rounds
    limit = max(rounds * 2, 2)
    rows = db.execute(
        select(Message).where(
            Message.conversation_id == conversation_id,
            Message.status.in_(("DONE", "REFUSED")),
        ).order_by(Message.seq.desc()).limit(limit)
    ).scalars().all()
    history = []
    for row in reversed(rows):
        role = "assistant" if row.role in ("ASSISTANT", "AGENT") else "user"
        history.append({"role": role, "content": row.content})
    return history


def check_rate_limit(db: Session, user_id: int) -> None:
    limit = settings.assistant_rate_limit_per_minute
    window_start = now() - timedelta(minutes=1)
    used = db.execute(
        select(func.count()).select_from(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Conversation.user_id == user_id,
            Message.role == "USER",
            Message.created_at >= window_start,
        )
    ).scalar_one()
    if used >= limit:
        raise AppError("ASSISTANT_RATE_LIMITED", f"提问过于频繁，请稍后再试（每分钟上限 {limit} 次）", 429)


def check_length(content: str) -> None:
    if len(content) > settings.assistant_message_max_chars:
        raise ValidationError(f"消息超过 {settings.assistant_message_max_chars} 字上限")
