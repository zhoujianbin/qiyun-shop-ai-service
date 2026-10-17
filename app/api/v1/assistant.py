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

from app.api.deps import get_current_user, request_permissions
from app.api.v1.common import actor_of
from app.core.db import get_db
from app.core.errors import AppError, Conflict
from app.integrations import llm
from app.models import AppUser
from app.models.generated import Message
from app.schemas.assistant import (
    ConversationCreate, ConversationPage, ConversationView, MessagePage, StreamRequest,
)
from app.services import assistant_conversation as conversation_service
from app.services import audit
from app.services.common import now

router = APIRouter(prefix="/ai", tags=["assistant"])

HEARTBEAT_SECONDS = 15.0
SYSTEM_PROMPT = (
    "你是栖云智家的客服助手。只根据给出的知识作答，不编造参数、时限与金额；"
    "不确定时明确说明并建议转人工。回答简洁，控制在 300 字以内。"
)


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

    content = payload.content.strip()
    conversation_service.check_length(content)
    conversation_service.check_rate_limit(db, user.id)

    # 幂等：同一 client_msg_id 重发，不重复生成
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

    def responder() -> Iterator[str]:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history[:-1])
        messages.append({"role": "user", "content": content})
        # 三期组 3 会把这里替换成 plan-and-execute 图（含检索与引用）
        yield from llm.stream_chat(messages)

    def events() -> Iterator[str]:
        yield _sse("meta", {"conversation_id": conversation_id,
                            "message_id": answer.id, "seq": answer.seq})
        collected: list[str] = []
        try:
            for kind, text in _iter_with_heartbeat(responder()):
                if kind == "ping":
                    yield _sse("ping", {})
                    continue
                collected.append(text)
                yield _sse("delta", {"text": text})
        except Exception as exc:  # noqa: BLE001 - 统一转成 error 事件
            _finish(db, answer, "FAILED", "".join(collected), latency_ms=_elapsed(started))
            detail = str(exc)[:300]
            yield _sse("error", {"code": "ASSISTANT_GENERATION_FAILED", "message": detail,
                                 "details": None, "request_id": getattr(request.state, "request_id", None)})
            return
        text = "".join(collected)
        latency = _elapsed(started)
        _finish(db, answer, "DONE" if text else "REFUSED", text, latency_ms=latency)
        yield _sse("citations", {"hits": []})
        yield _sse("done", {"status": "DONE" if text else "REFUSED", "latency_ms": latency})

    return StreamingResponse(events(), media_type="text/event-stream", headers=_stream_headers())


def _elapsed(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _finish(db: Session, message: Message, status: str, content: str, *, latency_ms: int) -> None:
    message.status = status
    message.content = content
    message.latency_ms = latency_ms
    message.model = getattr(llm.get_provider(), "name", None)
    db.add(message)
    audit.record(db, None, "ai.message.answer", "assistant.message", message.id,
                 after={"status": status, "chars": len(content)})
    db.commit()


def _stream_headers() -> dict:
    return {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
