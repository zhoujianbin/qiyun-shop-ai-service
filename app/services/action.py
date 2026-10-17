"""四期写操作：待确认动作的生成、确认、取消与执行。

设计要点（见 design D4/D5）：
- 写工具只生成 PROPOSED，不改业务数据；确认走独立请求，不恢复图。
- 幂等键 = sha256(tool + 归一化参数)，UNIQUE(conversation_id, action_key)。
- 状态迁移一律 CAS（UPDATE ... WHERE status = 期望值），不做读改写。
- 执行必然第二段事务：一期服务内部自带 commit。
"""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError, Conflict, NotFound, ValidationError
from app.models.generated import Conversation, PendingAction
from app.services import aftersales, audit, order, tool_registry
from app.services.common import list_payload, money, now

ACTION_TTL_MINUTES = 10
MAX_WRITE_ACTIONS_PER_CONVERSATION = 3
MAX_CANCEL_PER_ORDER_PER_DAY = 1

WRITE_TOOL_PERMISSION = {
    "cancel_order": "tool:write:order",
    "create_after_sales": "tool:write:aftersales",
}

# 仅这两个写工具允许执行；其余写工具一律拒绝
EXECUTORS = {
    "cancel_order": lambda db, actor, args: order.cancel(
        db, actor, tool_registry.resolve_order(db, actor, args["order_no"]).id,
        args.get("reason") or "客户在会话中取消"),
    "create_after_sales": None,  # 见 _execute_after_sales
}


def _execute_create_after_sales(db: Session, actor: dict, args: dict) -> dict:
    found = tool_registry.resolve_order(db, actor, args["order_no"])
    payload = {
        "order_id": found.id,
        "type": args["type"],
        "reason_code": args["reason_code"],
        "description": args.get("description") or "",
        "quantity": int(args.get("quantity") or 1),
    }
    return aftersales.create(db, actor, payload)


EXECUTORS["create_after_sales"] = _execute_create_after_sales


def action_key(tool_name: str, args: dict) -> str:
    normalized = json.dumps({"tool": tool_name, "args": args}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:64]


def _summary_of(tool_name: str, args: dict, order_view: dict | None) -> tuple[str, str, bool]:
    if tool_name == "cancel_order":
        view = order_view or {}
        summary = f"取消订单 {args.get('order_no')}（当前状态 {view.get('status') or '未知'}）"
        impact = "取消后订单关闭并释放库存；已支付订单需另行退款"
        return summary, impact, True
    view = order_view or {}
    summary = f"为订单 {args.get('order_no')} 提交售后申请（{args.get('type')}）"
    impact = "提交后进入人工审核流程，审核完成前可在售后页撤销"
    return summary, impact, False


def propose(db: Session, actor: dict, *, conversation: Conversation, message_id: int,
            tool_name: str, args: dict, facts: dict | None = None) -> dict:
    """生成待确认动作；同参数重复触发返回同一行（幂等）。"""
    if tool_name not in EXECUTORS:
        raise Conflict("ACTION_NOT_ALLOWED", f"不支持的写操作：{tool_name}")
    existing_count = db.execute(select(func.count()).select_from(PendingAction).where(
        PendingAction.conversation_id == conversation.id)).scalar_one()
    if existing_count >= MAX_WRITE_ACTIONS_PER_CONVERSATION:
        raise Conflict("ACTION_RATE_LIMITED", "本次会话的写操作次数已达上限，请转人工处理")

    key = action_key(tool_name, args)
    found = db.execute(select(PendingAction).where(
        PendingAction.conversation_id == conversation.id,
        PendingAction.action_key == key)).scalar_one_or_none()
    if found is not None:
        return view(found)

    summary, impact, irreversible = _summary_of(tool_name, args, facts)
    row = PendingAction(
        tenant_id=settings.tenant_id, conversation_id=conversation.id, message_id=message_id,
        action_key=key, tool_name=tool_name, args=args, summary=summary, impact=impact,
        irreversible=irreversible, status="PROPOSED",
        expires_at=now() + timedelta(minutes=ACTION_TTL_MINUTES),
    )
    db.add(row)
    db.flush()
    audit.record(db, actor, "ai.action.propose", "assistant.pending_action", row.id,
                 after={"tool": tool_name, "summary": summary})
    audit.emit(db, "ai.action.proposed", "conversation", conversation.id,
               {"action_id": row.id, "tool": tool_name})
    db.commit()
    return view(row)


def view(row: PendingAction) -> dict:
    return {
        "id": row.id, "conversation_id": row.conversation_id, "message_id": row.message_id,
        "tool": row.tool_name, "args": row.args or {}, "summary": row.summary,
        "impact": row.impact, "irreversible": row.irreversible, "status": row.status,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "executed_at": row.executed_at.isoformat() if row.executed_at else None,
        "result": row.result, "error_code": row.error_code,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _load(db: Session, action_id: int) -> PendingAction:
    row = db.get(PendingAction, action_id)
    if row is None or row.tenant_id != settings.tenant_id:
        raise NotFound("待确认动作不存在")
    return row


def get_action(db: Session, action_id: int) -> dict:
    return view(_load(db, action_id))


def list_actions(db: Session, conversation_id: int) -> dict:
    rows = db.execute(select(PendingAction).where(
        PendingAction.conversation_id == conversation_id).order_by(PendingAction.id.desc())
    ).scalars().all()
    return list_payload([view(row) for row in rows])


def _cas(db: Session, action_id: int, from_status: str, to_status: str, **fields) -> int:
    """状态迁移用 CAS；返回受影响行数（0 表示别人先改了）。"""
    stmt = text("UPDATE assistant.pending_action SET status = :to, updated_at = now()"
                + "".join(f", {key} = :{key}" for key in fields)
                + " WHERE id = :id AND status = :frm")
    params = {"to": to_status, "frm": from_status, "id": action_id, **fields}
    return db.execute(stmt, params).rowcount


def cancel(db: Session, actor: dict, action_id: int) -> dict:
    row = _load(db, action_id)
    if row.status == "CANCELLED":
        return view(row)
    if row.status not in ("PROPOSED",):
        raise Conflict("ACTION_STATE_INVALID", f"当前状态 {row.status} 不可取消")
    if _cas(db, action_id, "PROPOSED", "CANCELLED") == 0:
        db.rollback()
        raise Conflict("ACTION_STATE_INVALID", "动作状态已变化，请刷新")
    audit.record(db, actor, "ai.action.cancel", "assistant.pending_action", action_id)
    audit.emit(db, "ai.action.cancelled", "conversation", row.conversation_id, {"action_id": action_id})
    db.commit()
    db.refresh(row)
    return view(row)


def confirm(db: Session, actor: dict, action_id: int) -> dict:
    """确认并执行；重复确认返回同一结果（幂等）。"""
    row = _load(db, action_id)
    if row.status in ("EXECUTED", "FAILED", "EXPIRED"):
        return view(row)
    if row.status == "CANCELLED":
        raise Conflict("ACTION_STATE_INVALID", "动作已被取消")
    if row.status != "PROPOSED":
        raise Conflict("ACTION_STATE_INVALID", f"当前状态 {row.status} 不可确认")
    if row.expires_at is not None and row.expires_at <= now():
        _cas(db, action_id, "PROPOSED", "EXPIRED")
        db.commit()
        raise Conflict("ACTION_EXPIRED", "动作已过期，请重新发起")

    # 写操作要求核验仍有效（过期后不许执行）
    from app.services import assistant_handoff

    verified = assistant_handoff.active_verification(db, row.conversation_id)
    if verified is None or verified.order_no != (row.args or {}).get("order_no"):
        raise Conflict("IDENTITY_REQUIRED", "身份核验已失效，请重新核验后再确认")

    if _cas(db, action_id, "PROPOSED", "CONFIRMED", **{"confirmed_at": now()}) == 0:
        db.rollback()
        raise Conflict("ACTION_STATE_INVALID", "动作状态已变化，请刷新")
    audit.record(db, actor, "ai.action.confirm", "assistant.pending_action", action_id)
    audit.emit(db, "ai.action.confirmed", "conversation", row.conversation_id, {"action_id": action_id})
    db.commit()
    db.refresh(row)

    executor = EXECUTORS.get(row.tool_name)
    if executor is None:
        _mark_failed(db, row, "ACTION_NOT_ALLOWED")
        raise Conflict("ACTION_NOT_ALLOWED", "该动作不可执行")
    try:
        result = executor(db, actor, dict(row.args or {}))
    except AppError as exc:
        _mark_failed(db, row, exc.code)
        raise
    _finish(db, row, result)
    db.refresh(row)
    return view(row)


def _mark_failed(db: Session, row: PendingAction, error_code: str) -> None:
    db.rollback()
    _cas(db, row.id, "CONFIRMED", "FAILED", **{"error_code": error_code})
    audit.record(db, None, "ai.action.execute_failed", "assistant.pending_action", row.id,
                 after={"error_code": error_code})
    audit.emit(db, "ai.action.failed", "conversation", row.conversation_id,
               {"action_id": row.id, "error_code": error_code})
    db.commit()


def _finish(db: Session, row: PendingAction, result: dict) -> None:
    payload = {"status": result.get("status"), "order_no": result.get("order_no"),
               "application_no": result.get("application_no")}
    _cas(db, row.id, "CONFIRMED", "EXECUTED",
         **{"executed_at": now(), "result": json.dumps(payload, ensure_ascii=False)})
    audit.record(db, None, "ai.action.executed", "assistant.pending_action", row.id, after=payload)
    audit.emit(db, "ai.action.executed", "conversation", row.conversation_id,
               {"action_id": row.id, **payload})
    db.commit()


def expire_stale(db: Session, limit: int = 100) -> dict:
    rows = db.execute(select(PendingAction.id).where(
        PendingAction.status == "PROPOSED", PendingAction.expires_at <= now()).limit(limit)
    ).scalars().all()
    changed = 0
    for action_id in rows:
        changed += _cas(db, action_id, "PROPOSED", "EXPIRED")
    db.commit()
    return {"expired": changed}
