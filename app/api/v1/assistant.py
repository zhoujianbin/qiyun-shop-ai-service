"""三期智能客服接口：会话、消息、SSE 流式回答。

SSE 事件序列：meta → (ping)* → delta* → citations → done | error
- 只转发模型 content（reasoning_content 由集成层丢弃）
- 先落 USER 与占位 ASSISTANT(STREAMING)，流结束更新终态
"""
from __future__ import annotations

import json
import queue
import threading
import time
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, request_permissions, require
from app.api.v1.common import actor_of
from app.core.config import settings
from app.core.db import get_db
from app.core.errors import AppError, Conflict
from app.integrations import llm
from app.models import AppUser
from app.models.generated import Message
from app.schemas.assistant import (
    AgentMessageRequest, ConversationCreate, ConversationPage, ConversationView, FeedbackRequest,
    HandoffCloseRequest, HandoffView, IdentityRequest, MessagePage, MessageView, StreamRequest,
)
from app.services import assistant_conversation as conversation_service
from app.services import assistant_graph, assistant_handoff
from app.services import audit
from app.services.common import now

router = APIRouter(prefix="/ai", tags=["assistant"])

HEARTBEAT_SECONDS = 15.0



def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _iter_with_heartbeat(source: Iterator[str], interval: float = HEARTBEAT_SECONDS) -> Iterator[tuple[str, str]]:
    """把阻塞式生成器包装成 (kind, text) 流，空闲时按间隔产出心跳。"""
    buffer: queue.Queue = queue.Queue()
    sentinel = object()

    def worker() -> None:
        try:
            for chunk in source:
                buffer.put(chunk)
        except Exception as exc:  # noqa: BLE001 - 交给主循环转成 error 事件
            buffer.put(exc)
        finally:
            buffer.put(sentinel)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    last = time.monotonic()
    while True:
        try:
            item = buffer.get(timeout=interval)
        except queue.Empty:
            yield ("ping", "")
            last = time.monotonic()
            continue
        if item is sentinel:
            return
        if isinstance(item, Exception):
            raise item
        last = time.monotonic()
        yield ("delta", item)


def _staff(request: Request, db: Session, user: AppUser) -> bool:
    return "ai:chat:read" in request_permissions(request, db, user)


@router.post("/conversations", response_model=ConversationView)
def create_conversation(payload: ConversationCreate, request: Request, db: Session = Depends(get_db),
                        user: AppUser = Depends(get_current_user)) -> dict:
    return conversation_service.create_conversation(
        db, actor_of(request, user, db), channel_account_id=payload.channel_account_id)


@router.get("/conversations", response_model=ConversationPage)
def list_conversations(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                       request: Request = None, db: Session = Depends(get_db),
                       user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return conversation_service.list_conversations(
        db, actor=actor, staff=_staff(request, db, user), page=page, page_size=page_size)


@router.get("/conversations/{conversation_id}", response_model=ConversationView)
def get_conversation(conversation_id: int, request: Request, db: Session = Depends(get_db),
                     user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    conversation = conversation_service.ensure_visible(
        db, conversation_id, actor=actor, staff=_staff(request, db, user))
    return conversation_service.conversation_view(conversation)


@router.post("/conversations/{conversation_id}/close", response_model=ConversationView)
def close_conversation(conversation_id: int, request: Request, db: Session = Depends(get_db),
                       user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    conversation = conversation_service.ensure_visible(
        db, conversation_id, actor=actor, staff=_staff(request, db, user))
    return conversation_service.close_conversation(db, conversation, actor)


@router.get("/conversations/{conversation_id}/messages", response_model=MessagePage)
def list_messages(conversation_id: int, request: Request, after_seq: int | None = None,
                  page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                  db: Session = Depends(get_db),
                  user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    conversation_service.ensure_visible(
        db, conversation_id, actor=actor, staff=_staff(request, db, user))
    return conversation_service.list_messages(
        db, conversation_id, after_seq=after_seq, page=page, page_size=page_size)


@router.post("/conversations/{conversation_id}/messages:stream")
def stream_message(conversation_id: int, payload: StreamRequest, request: Request,
                   db: Session = Depends(get_db),
                   user: AppUser = Depends(get_current_user)) -> StreamingResponse:
    actor = actor_of(request, user, db)
    conversation = conversation_service.ensure_visible(
        db, conversation_id, actor=actor, staff=_staff(request, db, user))
    if conversation.status == "CLOSED":
        raise Conflict("CONVERSATION_CLOSED", "会话已关闭")
    if conversation.ai_paused:
        raise Conflict("AI_PAUSED", "客服已接管，请等待人工回复")

    content = payload.content.strip()
    conversation_service.check_length(content)
    conversation_service.check_rate_limit(db, user.id)

    existing = conversation_service.find_by_client_id(db, conversation_id, payload.client_msg_id)
    if existing is not None:
        return StreamingResponse(
            iter([_sse("meta", {"conversation_id": conversation_id, "message_id": existing.id,
                                "seq": existing.seq, "replayed": True}),
                  _sse("citations", {"hits": []}),
                  _sse("done", {"status": existing.status, "replayed": True})]),
            media_type="text/event-stream", headers=_stream_headers())

    user_message = conversation_service.append_message(
        db, conversation_id, role="USER", content=content, status="DONE",
        client_msg_id=payload.client_msg_id)
    answer = conversation_service.append_message(
        db, conversation_id, role="ASSISTANT", content="", status="STREAMING",
        metadata={"plan": None, "feedback": None})
    db.commit()

    history = conversation_service.context_messages(db, conversation_id)
    started = time.monotonic()
    state = assistant_graph.run(db, content, actor=actor, history=history[:-1],
                                identity_level=payload.identity_level)

    def responder() -> Iterator[str]:
        if state.decision != "ANSWER":
            text = assistant_graph.fixed_answer(state)
            for index in range(0, len(text), 8):
                yield text[index:index + 8]
            return
        yield from llm.stream_chat(state.prompt_messages)

    def events() -> Iterator[str]:
        yield _sse("meta", {"conversation_id": conversation_id, "message_id": answer.id,
                            "seq": answer.seq, "decision": state.decision,
                            "intent": state.intent})
        collected: list[str] = []
        try:
            for kind, text in _iter_with_heartbeat(responder()):
                if kind == "ping":
                    yield _sse("ping", {})
                    continue
                collected.append(text)
                yield _sse("delta", {"text": text})
        except Exception as exc:  # noqa: BLE001
            _finish(db, answer, "FAILED", "".join(collected), latency_ms=_elapsed(started), state=state)
            yield _sse("error", {"code": "ASSISTANT_GENERATION_FAILED", "message": str(exc)[:300],
                                 "details": None,
                                 "request_id": getattr(request.state, "request_id", None)})
            return
        text = "".join(collected)
        status = "REFUSED" if state.decision in ("CLARIFY", "REFUSE") else ("DONE" if text else "FAILED")
        _finish(db, answer, status, text, latency_ms=_elapsed(started), state=state)
        yield _sse("citations", {"hits": state.citations})
        yield _sse("done", {"status": status, "latency_ms": _elapsed(started),
                            "intent": state.intent, "decision": state.decision,
                            "degraded": state.degraded})

    return StreamingResponse(events(), media_type="text/event-stream", headers=_stream_headers())


def _elapsed(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _finish(db: Session, message: Message, status: str, content: str, *, latency_ms: int,
            state: "assistant_graph.State | None" = None) -> None:
    from app.models.generated import Citation, RetrievalTrace

    message.status = status
    message.content = content
    message.latency_ms = latency_ms
    message.model = getattr(llm.get_provider(), "name", None)
    if state is not None:
        meta = dict(message.metadata_json or {})
        meta["plan"] = state.plan
        meta["intent"] = state.intent
        meta["degraded"] = state.degraded
        message.metadata_json = meta
        for citation in state.citations:
            db.add(Citation(
                tenant_id=message.tenant_id,
                message_id=message.id,
                chunk_id=citation.get("chunk_id"),
                document_id=citation["document_id"],
                version=citation["version"],
                title_path=citation.get("title_path"),
                line_start=citation.get("line_start"),
                line_end=citation.get("line_end"),
                snippet=citation.get("snippet"),
                rank=citation["rank"],
                entity_tags=citation.get("entity_tags") or [],
            ))
        for observation in state.observations:
            db.add(RetrievalTrace(
                tenant_id=message.tenant_id,
                message_id=message.id,
                query=observation.get("query") or state.question,
                filters={"identity_level": None},
                intent=state.intent,
                hit_count=len(observation.get("hits") or []),
                hits=observation.get("hits") or [],
                latency_ms=observation.get("latency_ms"),
                model=getattr(llm.get_provider(), "name", None),
                tokens=None,
            ))
    db.add(message)
    audit.record(db, None, "ai.message.answer", "assistant.message", message.id,
                 after={"status": status, "chars": len(content),
                        "intent": getattr(state, "intent", None)})
    db.commit()


def _stream_headers() -> dict:
    return {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }

@router.get("/messages/{message_id}/trace")
def get_message_trace(message_id: int, request: Request, db: Session = Depends(get_db),
                      user: AppUser = Depends(get_current_user)) -> list[dict]:
    from sqlalchemy import select

    from app.core.errors import Forbidden
    from app.models.generated import Citation, Message, RetrievalTrace

    message = db.get(Message, message_id)
    if message is None or message.tenant_id != settings.tenant_id:
        raise ConversationNotFound()
    conversation = conversation_service.ensure_visible(
        db, message.conversation_id, actor=actor_of(request, user, db), staff=_staff(request, db, user))
    perms = request_permissions(request, db, user)
    if "ai:trace:read" not in perms and conversation.user_id != user.id:
        raise Forbidden("缺少权限：ai:trace:read")
    traces = db.execute(
        select(RetrievalTrace).where(RetrievalTrace.message_id == message_id)
        .order_by(RetrievalTrace.id)
    ).scalars().all()
    citations = db.execute(
        select(Citation).where(Citation.message_id == message_id).order_by(Citation.rank)
    ).scalars().all()
    return [{
        "message_id": message_id,
        "status": message.status,
        "intent": message.metadata_json.get("intent") if message.metadata_json else None,
        "plan": message.metadata_json.get("plan") if message.metadata_json else None,
        "latency_ms": message.latency_ms,
        "traces": [{
            "query": row.query, "intent": row.intent, "hit_count": row.hit_count,
            "latency_ms": row.latency_ms, "model": row.model,
        } for row in traces],
        "citations": [{
            "document_id": row.document_id, "version": row.version, "title_path": row.title_path,
            "line_start": row.line_start, "line_end": row.line_end,
            "entity_tags": row.entity_tags,
        } for row in citations],
    }]


def ConversationNotFound():
    from app.core.errors import NotFound

    return NotFound("消息不存在或不可见")

# ---------------------------------------------------------------- 身份核验 / 转人工
@router.post("/conversations/{conversation_id}/identity")
def verify_identity(conversation_id: int, payload: IdentityRequest, request: Request,
                    db: Session = Depends(get_db),
                    user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    conversation = conversation_service.ensure_visible(
        db, conversation_id, actor=actor, staff=_staff(request, db, user))
    return assistant_handoff.verify_identity(
        db, actor, conversation, order_no=payload.order_no, phone_tail=payload.phone_tail)


@router.post("/conversations/{conversation_id}/handoff")
def request_handoff(conversation_id: int, request: Request, db: Session = Depends(get_db),
                    user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    conversation = conversation_service.ensure_visible(
        db, conversation_id, actor=actor, staff=_staff(request, db, user))
    return assistant_handoff.create_handoff(db, actor, conversation, reason="USER_REQUEST")


@router.get("/handoffs", response_model=list[HandoffView])
def list_handoffs(status: str | None = None, db: Session = Depends(get_db),
                  user: AppUser = Depends(require("ai:handoff:read"))) -> list[dict]:
    return assistant_handoff.list_handoffs(db, status=status)


@router.post("/handoffs/{handoff_id}/claim", response_model=HandoffView)
def claim_handoff(handoff_id: int, request: Request, db: Session = Depends(get_db),
                  user: AppUser = Depends(require("ai:handoff:write"))) -> dict:
    return assistant_handoff.claim_handoff(db, actor_of(request, user, db), handoff_id)


@router.post("/handoffs/{handoff_id}/close", response_model=HandoffView)
def close_handoff(handoff_id: int, payload: HandoffCloseRequest, request: Request,
                  db: Session = Depends(get_db),
                  user: AppUser = Depends(require("ai:handoff:write"))) -> dict:
    return assistant_handoff.close_handoff(db, actor_of(request, user, db), handoff_id,
                                           summary=payload.summary, back_to_ai=payload.back_to_ai)


@router.post("/conversations/{conversation_id}/agent-messages", response_model=MessageView)
def agent_message(conversation_id: int, payload: AgentMessageRequest, request: Request,
                  db: Session = Depends(get_db),
                  user: AppUser = Depends(require("ai:chat:write"))) -> dict:
    conversation = conversation_service.ensure_visible(
        db, conversation_id, actor=actor_of(request, user, db), staff=True)
    return assistant_handoff.agent_message(
        db, actor_of(request, user, db), conversation, payload.content)

@router.post("/messages/{message_id}/feedback")
def submit_feedback(message_id: int, payload: FeedbackRequest, request: Request,
                    db: Session = Depends(get_db),
                    user: AppUser = Depends(get_current_user)) -> dict:
    from app.models.generated import Message
    from app.services.common import now

    message = db.get(Message, message_id)
    if message is None or message.tenant_id != settings.tenant_id:
        raise ConversationNotFound()
    conversation = conversation_service.ensure_visible(
        db, message.conversation_id, actor=actor_of(request, user, db), staff=_staff(request, db, user))
    meta = dict(message.metadata_json or {})
    meta["feedback"] = {"value": payload.value, "reason": payload.reason,
                        "at": now().isoformat(), "user_id": user.id}
    message.metadata_json = meta
    db.add(message)
    audit.record(db, {"id": user.id, "party": user.party}, "ai.message.feedback",
                 "assistant.message", message.id, after=meta["feedback"])
    db.commit()
    return meta["feedback"]
