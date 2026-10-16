from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import Conflict, NotFound, ValidationError
from app.integrations import payment as payment_gateway
from app.models import (
    AfterSalesApplication, Order, OrderItem, OrderStatusHistory, Payment, Refund, RefundAttempt,
)
from app.services import audit
from app.services.common import get_or_404, list_payload, money, now, page_offset, seq


def _view(r: Refund) -> dict:
    return {"id": r.id, "refund_no": r.refund_no, "order_id": r.order_id, "application_id": r.application_id,
            "after_sales_id": r.application_id, "payment_id": None, "channel": r.method,
            "customer_id": r.customer_id, "method": r.method, "amount": money(r.amount), "currency": r.currency,
            "status": r.status, "reason": r.reason, "channel_refund_no": r.channel_refund_no,
            "approved_by": r.approved_by, "approved_at": r.approved_at.isoformat() if r.approved_at else None,
            "executed_at": r.executed_at.isoformat() if r.executed_at else None,
            "created_at": r.created_at.isoformat()}


def _apply_scope(stmt, actor: dict):
    if actor.get("party") in ("CUSTOMER", "GUEST"):
        return stmt.where(Refund.customer_id == actor.get("customer_id"))
    channel_ids = actor.get("channel_ids")
    if channel_ids is not None:
        if not channel_ids:
            return stmt.where(Refund.id < 0)
        return stmt.join(Order, Order.id == Refund.order_id).where(Order.channel_account_id.in_(channel_ids))
    return stmt


def list_refunds(db: Session, actor: dict, *, page: int, page_size: int, status: str | None = None,
                 keyword: str | None = None) -> dict:
    stmt = select(Refund).where(Refund.tenant_id == settings.tenant_id)
    stmt = _apply_scope(stmt, actor)
    if status:
        stmt = stmt.where(Refund.status == status)
    if keyword:
        stmt = stmt.where(Refund.refund_no.ilike(f"%{keyword}%"))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    offset, limit = page_offset(page, page_size)
    rows = db.execute(stmt.order_by(Refund.created_at.desc()).offset(offset).limit(limit)).scalars().all()
    return {"page": page, "page_size": page_size, "total": total, "meta": {"page": page, "page_size": page_size, "total": total},
            "items": [_view(r) for r in rows]}


def get_refund(db: Session, actor: dict, refund_id: int) -> dict:
    refund = get_or_404(db, Refund, refund_id, "退款单不存在")
    if actor.get("party") in ("CUSTOMER", "GUEST") and refund.customer_id != actor.get("customer_id"):
        raise NotFound("退款单不存在")
    data = _view(refund)
    attempts = db.execute(select(RefundAttempt).where(RefundAttempt.refund_id == refund.id)
                          .order_by(RefundAttempt.attempt_no)).scalars().all()
    data["attempts"] = [{"id": a.id, "refund_id": a.refund_id, "attempt_no": a.attempt_no, "status": a.status,
                         "channel": refund.method, "error_code": a.error_code, "error_message": a.error_message,
                         "request_payload": a.request_payload, "response_payload": a.response_payload,
                         "attempted_at": a.created_at.isoformat(), "created_at": a.created_at.isoformat()}
                        for a in attempts]
    return data


def _refundable_amount(db: Session, order: Order, exclude_refund_id: int | None = None) -> object:
    stmt = select(func.coalesce(func.sum(Refund.amount), 0)).where(Refund.order_id == order.id,
                                                                   Refund.status.in_(["PENDING", "APPROVED", "PROCESSING", "SUCCESS"]))
    if exclude_refund_id:
        stmt = stmt.where(Refund.id != exclude_refund_id)
    used = db.execute(stmt).scalar_one()
    return (order.paid_amount or 0) - used


METHOD_ALIAS = {"WECHAT": "WECHAT_PAY", "WECHATPAY": "WECHAT_PAY", "ALI": "ALIPAY", "UNION": "UNIONPAY"}


def normalize_method(value: str | None, default: str = "ORIGINAL") -> str:
    if not value:
        return default
    return METHOD_ALIAS.get(str(value).upper(), str(value).upper())


def list_attempts(db: Session, actor: dict, refund_id: int) -> dict:
    """退款尝试列表（前端 /refunds/{id}/attempts 需要 {items, meta}）。"""
    refund = get_or_404(db, Refund, refund_id, "退款单不存在")
    if actor.get("party") in ("CUSTOMER", "GUEST") and refund.customer_id != actor.get("customer_id"):
        raise NotFound("退款单不存在")
    rows = db.execute(select(RefundAttempt).where(RefundAttempt.refund_id == refund_id)
                      .order_by(RefundAttempt.attempt_no)).scalars().all()
    items = [{"id": a.id, "refund_id": a.refund_id, "attempt_no": a.attempt_no, "status": a.status,
              "channel": refund.method, "request_payload": a.request_payload,
              "response_payload": a.response_payload, "error_code": a.error_code,
              "error_message": a.error_message, "attempted_at": a.created_at.isoformat(),
              "created_at": a.created_at.isoformat()} for a in rows]
    return list_payload(items)


def create(db: Session, actor: dict, payload: dict) -> dict:
    order = get_or_404(db, Order, payload["order_id"], "订单不存在")
    payload.setdefault("application_id", payload.get("after_sales_id"))
    if actor.get("party") in ("CUSTOMER", "GUEST") and order.customer_id != actor.get("customer_id"):
        raise NotFound("订单不存在")
    if order.payment_status not in ("PAID", "PARTIAL", "PARTIAL_REFUNDED"):
        raise Conflict("REFUND_NOT_ALLOWED", "订单未支付或已全额退款，无法退款")
    amount = payload["amount"]
    refundable = _refundable_amount(db, order)
    if float(amount) <= 0 or float(amount) > float(refundable):
        raise ValidationError(f"退款金额需大于 0 且不超过可退金额 {money(refundable)}")
    refund = Refund(tenant_id=settings.tenant_id, refund_no=seq("REF"), order_id=order.id,
                    application_id=payload.get("application_id"), customer_id=order.customer_id,
                    method=normalize_method(payload.get("method") or payload.get("channel")), amount=amount, status="PENDING",
                    reason=payload.get("reason"), requested_by=actor.get("id"))
    db.add(refund)
    order.payment_status = "REFUNDING"
    db.flush()
    audit.record(db, actor, "refund_create", "refund", refund.id,
                 after={"refund_no": refund.refund_no, "amount": money(refund.amount)},
                 channel_account_id=order.channel_account_id)
    db.commit()
    return _view(refund)


def execute(db: Session, actor: dict, refund_id: int) -> dict:
    refund = db.execute(select(Refund).where(Refund.id == refund_id).with_for_update()).scalar_one_or_none()
    if refund is None:
        raise NotFound("退款单不存在")
    if refund.status == "SUCCESS":
        return {**_view(refund), "replay": True}
    if refund.status not in ("PENDING", "APPROVED"):
        raise Conflict("REFUND_STATE_INVALID", f"退款单状态 {refund.status} 不能执行")
    order = db.get(Order, refund.order_id)
    attempt_no = db.execute(select(func.coalesce(func.max(RefundAttempt.attempt_no), 0))
                            .where(RefundAttempt.refund_id == refund.id)).scalar_one() + 1
    refund.status = "PROCESSING"
    refund.approved_by = actor.get("id")
    refund.approved_at = refund.approved_at or now()
    db.flush()
    payment = db.execute(select(Payment).where(Payment.order_id == order.id, Payment.status == "SUCCESS")
                         .order_by(Payment.id.desc())).scalars().first()
    result = payment_gateway.refund(refund.refund_no, payment.payment_no if payment else None, money(refund.amount))
    attempt = RefundAttempt(refund_id=refund.id, attempt_no=attempt_no, status="SUCCESS",
                            request_payload={"amount": money(refund.amount), "method": refund.method},
                            response_payload=result)
    db.add(attempt)
    refund.status = "SUCCESS"
    refund.channel_refund_no = result["channel_refund_no"]
    refund.executed_at = now()
    order.refunded_amount = (order.refunded_amount or 0) + refund.amount
    if float(order.refunded_amount) >= float(order.paid_amount or 0) - 0.001:
        order.payment_status = "REFUNDED"
        if order.status not in ("CANCELLED",):
            prev = order.status
            order.status = "CLOSED"
            db.add(OrderStatusHistory(tenant_id=settings.tenant_id, order_id=order.id, field="status",
                                      from_value=prev, to_value="CLOSED", reason="全额退款完成",
                                      operator_type=actor.get("party", "SYSTEM"), operator_id=actor.get("id")))
    else:
        order.payment_status = "PARTIAL_REFUNDED"
    db.add(OrderStatusHistory(tenant_id=settings.tenant_id, order_id=order.id, field="payment_status",
                              from_value="REFUNDING", to_value=order.payment_status, reason="退款执行",
                              operator_type=actor.get("party", "SYSTEM"), operator_id=actor.get("id")))
    audit.record(db, actor, "refund_execute", "refund", refund.id,
                 after={"status": "SUCCESS", "channel_refund_no": refund.channel_refund_no},
                 channel_account_id=order.channel_account_id)
    audit.emit(db, "refund.succeeded", "refund", refund.id,
               {"refund_no": refund.refund_no, "order_no": order.order_no, "amount": money(refund.amount)},
               actor.get("request_id"))
    db.commit()
    return {**_view(refund), "order": {"id": order.id, "order_no": order.order_no, "status": order.status,
            "payment_status": order.payment_status, "refunded_amount": money(order.refunded_amount)}}


def mark_uncertain(db: Session, actor: dict, refund_id: int, error: str, error_code: str = "TIMEOUT") -> dict:
    refund = get_or_404(db, Refund, refund_id, "退款单不存在")
    attempt_no = db.execute(select(func.coalesce(func.max(RefundAttempt.attempt_no), 0))
                            .where(RefundAttempt.refund_id == refund.id)).scalar_one() + 1
    db.add(RefundAttempt(refund_id=refund.id, attempt_no=attempt_no, status=error_code,
                         error_code=error_code, error_message=error))
    audit.record(db, actor, "refund_uncertain", "refund", refund.id, after={"error": error})
    db.commit()
    return _view(refund)


def handle_callback(db: Session, payload: dict) -> dict:
    refund = db.execute(select(Refund).where(Refund.refund_no == payload["refund_no"]).with_for_update()).scalar_one_or_none()
    if refund is None:
        raise NotFound("退款单不存在")
    if refund.status == "SUCCESS":
        return {"duplicate": True, "refund_no": refund.refund_no}
    if payload.get("status") == "SUCCESS":
        return execute(db, {"party": "SYSTEM"}, refund.id)
    attempt_no = db.execute(select(func.coalesce(func.max(RefundAttempt.attempt_no), 0))
                            .where(RefundAttempt.refund_id == refund.id)).scalar_one() + 1
    db.add(RefundAttempt(refund_id=refund.id, attempt_no=attempt_no, status="FAILED",
                         error_code=payload.get("error_code"), error_message=payload.get("error_message")))
    refund.status = "FAILED"
    order = db.get(Order, refund.order_id)
    order.payment_status = "PAID"
    db.commit()
    return {"duplicate": False, "refund_no": refund.refund_no, "status": refund.status}
