from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import Conflict, NotFound, ValidationError
from app.integrations import payment as payment_gateway
from app.models import (
    CustomerProfile, Order, OrderStatusHistory, Payment, PaymentCallbackLog,
)
from app.services import audit
from app.services.common import get_or_404, money, now, page_offset, seq


def _payment_view(p: Payment) -> dict:
    return {"id": p.id, "payment_no": p.payment_no, "order_id": p.order_id, "method": p.method,
            "amount": money(p.amount), "currency": p.currency, "status": p.status,
            "channel_txn_no": p.channel_txn_no, "pay_url": p.pay_url,
            "expires_at": p.expires_at.isoformat() if p.expires_at else None,
            "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            "created_at": p.created_at.isoformat()}


def _apply_scope(stmt, actor: dict):
    if actor.get("party") in ("CUSTOMER", "GUEST"):
        return stmt.join(Order, Order.id == Payment.order_id).where(Order.customer_id == actor.get("customer_id"))
    channel_ids = actor.get("channel_ids")
    if channel_ids is not None:
        if not channel_ids:
            return stmt.where(Payment.id < 0)
        return stmt.join(Order, Order.id == Payment.order_id).where(Order.channel_account_id.in_(channel_ids))
    return stmt


def list_payments(db: Session, actor: dict, *, page: int, page_size: int, status: str | None = None,
                  keyword: str | None = None) -> dict:
    stmt = select(Payment).where(Payment.tenant_id == settings.tenant_id)
    stmt = _apply_scope(stmt, actor)
    if status:
        stmt = stmt.where(Payment.status == status)
    if keyword:
        stmt = stmt.where(Payment.payment_no.ilike(f"%{keyword}%"))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    offset, limit = page_offset(page, page_size)
    rows = db.execute(stmt.order_by(Payment.created_at.desc()).offset(offset).limit(limit)).scalars().all()
    return {"page": page, "page_size": page_size, "total": total, "meta": {"page": page, "page_size": page_size, "total": total},
            "items": [_payment_view(p) for p in rows]}


def get_payment(db: Session, actor: dict, payment_id: int) -> dict:
    payment = get_or_404(db, Payment, payment_id, "支付单不存在")
    if actor.get("party") in ("CUSTOMER", "GUEST"):
        order = db.get(Order, payment.order_id)
        if order is None or order.customer_id != actor.get("customer_id"):
        # 客户只能查看自己的支付单
            raise NotFound("支付单不存在")
    return _payment_view(payment)


def _mark_paid(db: Session, order: Order, payment: Payment, actor: dict, channel_txn_no: str | None) -> None:
    payment.status = "SUCCESS"
    payment.channel_txn_no = channel_txn_no
    payment.paid_at = now()
    order.paid_amount = payment.amount
    order.paid_at = payment.paid_at
    order.payment_status = "PAID"
    prev = order.status
    if order.status in ("CREATED", "PENDING_PAYMENT"):
        order.status = "PAID"
    order.version = (order.version or 0) + 1
    db.add(OrderStatusHistory(tenant_id=settings.tenant_id, order_id=order.id, field="payment_status",
                              from_value="UNPAID", to_value="PAID", reason="支付成功",
                              operator_type=actor.get("party", "SYSTEM"), operator_id=actor.get("id")))
    db.add(OrderStatusHistory(tenant_id=settings.tenant_id, order_id=order.id, field="status",
                              from_value=prev, to_value=order.status, reason="支付成功",
                              operator_type=actor.get("party", "SYSTEM"), operator_id=actor.get("id")))
    profile = db.get(CustomerProfile, order.customer_id)
    if profile is not None:
        profile.total_order_count = (profile.total_order_count or 0) + 1
        profile.total_paid_amount = (profile.total_paid_amount or 0) + (order.paid_amount or 0)
        profile.last_order_at = now()
    audit.emit(db, "payment.succeeded", "order", order.id,
               {"order_no": order.order_no, "payment_no": payment.payment_no, "amount": money(payment.amount)},
               actor.get("request_id"))


def create_payment(db: Session, actor: dict, order_id: int, method: str = "MOCK") -> dict:
    order = get_or_404(db, Order, order_id, "订单不存在")
    if actor.get("party") in ("CUSTOMER", "GUEST") and order.customer_id != actor.get("customer_id"):
        raise NotFound("订单不存在")
    if order.status not in ("CREATED", "PENDING_PAYMENT"):
        raise Conflict("ORDER_STATE_INVALID", f"订单状态 {order.status} 不能发起支付")
    outstanding = (order.payable_amount or 0) - (order.paid_amount or 0)
    if outstanding <= 0:
        raise Conflict("ORDER_STATE_INVALID", "订单无需支付")
    payment = Payment(tenant_id=settings.tenant_id, payment_no=seq("PAY"), order_id=order.id, method=method,
                      amount=outstanding, status="PENDING", expires_at=order.pay_deadline)
    gateway = payment_gateway.create_payment(payment.payment_no, money(payment.amount), method, f"订单 {order.order_no}")
    payment.pay_url = gateway["pay_url"]
    db.add(payment)
    db.flush()
    audit.record(db, actor, "payment_create", "payment", payment.id, after={"payment_no": payment.payment_no}, channel_account_id=order.channel_account_id)
    db.commit()
    return _payment_view(payment)


def mock_succeed(db: Session, actor: dict, payment_id: int) -> dict:
    if settings.is_prod:
        raise Conflict("DEMO_DISABLED", "生产环境不允许模拟支付")
    payment = db.execute(select(Payment).where(Payment.id == payment_id).with_for_update()).scalar_one_or_none()
    if payment is None:
        raise NotFound("支付单不存在")
    order = db.get(Order, payment.order_id)
    if payment.status == "SUCCESS":
        return {"payment": _payment_view(payment), "order_no": order.order_no, "replay": True}
    if payment.status != "PENDING":
        raise Conflict("PAYMENT_STATE_INVALID", f"支付单状态 {payment.status} 不能标记成功")
    _mark_paid(db, order, payment, actor, "MOCK-TXN-" + payment.payment_no[-8:])
    audit.record(db, actor, "payment_mock_succeed", "payment", payment.id, after={"status": "SUCCESS"}, channel_account_id=order.channel_account_id)
    db.commit()
    return {"payment": _payment_view(payment), "order": {"id": order.id, "order_no": order.order_no,
            "status": order.status, "payment_status": order.payment_status, "paid_amount": money(order.paid_amount)}}


def handle_callback(db: Session, method: str, payload: dict) -> dict:
    event_id = str(payload.get("event_id") or "")
    payment_no = payload.get("payment_no")
    amount = payload.get("amount")
    signature = payload.get("signature")
    if not event_id or not payment_no or amount is None:
        raise ValidationError("回调缺少 event_id/payment_no/amount")
    raw = f"{event_id}|{payment_no}|{amount}|{payload.get('paid_at') or ''}"
    if settings.payment_provider != "mock" and not payment_gateway.verify_signature(raw, signature):
        db.add(PaymentCallbackLog(tenant_id=settings.tenant_id, method=method, event_id=event_id,
                                  payment_no=payment_no, signature_valid=False, processed=False,
                                  process_result="SIGNATURE_INVALID", payload=payload))
        db.commit()
        raise Conflict("SIGNATURE_INVALID", "回调验签失败")
    existing = db.execute(select(PaymentCallbackLog).where(PaymentCallbackLog.method == method,
                                                          PaymentCallbackLog.event_id == event_id)).scalar_one_or_none()
    if existing is not None:
        return {"code": "PAYMENT_DUPLICATE_CALLBACK", "duplicate": True, "payment_no": payment_no}
    log = PaymentCallbackLog(tenant_id=settings.tenant_id, method=method, event_id=event_id, payment_no=payment_no,
                             signature_valid=True, payload=payload)
    db.add(log)
    payment = db.execute(select(Payment).where(Payment.payment_no == payment_no).with_for_update()).scalar_one_or_none()
    if payment is None:
        log.process_result = "PAYMENT_NOT_FOUND"
        db.commit()
        raise NotFound("支付单不存在")
    if abs(float(payment.amount) - float(amount)) > 0.001:
        log.process_result = "AMOUNT_MISMATCH"
        db.commit()
        raise Conflict("PAYMENT_AMOUNT_MISMATCH", "回调金额与支付单不一致",
                       {"expected": money(payment.amount), "actual": money(amount)})
    if payment.status == "SUCCESS":
        log.processed = True
        log.process_result = "ALREADY_SUCCESS"
        db.commit()
        return {"code": "PAYMENT_DUPLICATE_CALLBACK", "duplicate": True, "payment_no": payment_no}
    order = db.get(Order, payment.order_id)
    _mark_paid(db, order, payment, {"party": "SYSTEM"}, payload.get("channel_txn_no"))
    log.processed = True
    log.process_result = "OK"
    db.commit()
    return {"code": "OK", "duplicate": False, "payment_no": payment_no, "order_no": order.order_no,
            "order_status": order.status, "payment_status": order.payment_status}
