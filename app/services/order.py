from datetime import timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import Conflict, Forbidden, NotFound, ValidationError
from app.integrations import payment as payment_gateway
from app.models import (AppUser, CustomerAddress, CustomerProfile, Order, OrderItem, OrderStatusHistory,
                       Payment, Product, Sku)
from app.services import audit, inventory
from app.services.common import get_or_404, money, now, page_offset, seq

PAY_TTL_MINUTES = 30


def _mask(value: str | None) -> str | None:
    if not value:
        return None
    digits = str(value)
    return digits[:3] + "****" + digits[-4:] if len(digits) >= 7 else "***"


def _item_view(i: OrderItem) -> dict:
    return {
        "id": i.id, "order_id": i.order_id, "product_id": i.product_id, "sku_id": i.sku_id, "warehouse_id": i.warehouse_id,
        "spu_code": i.spu_code, "sku_code": i.sku_code, "product_name": i.product_name, "sku_name": i.sku_name,
        "spec_summary": i.spec_summary, "image_url": i.image_url, "unit_price": money(i.unit_price),
        "quantity": i.quantity, "goods_amount": money(i.goods_amount), "discount_amount": money(i.discount_amount),
        "payable_amount": money(i.payable_amount), "refunded_amount": money(i.refunded_amount),
        "shipped_quantity": i.shipped_quantity, "returned_quantity": i.returned_quantity,
        "item_status": i.item_status, "after_sales_status": i.after_sales_status,
    }


def _order_view(db: Session, o: Order, with_items: bool = False) -> dict:
    data = {
        "id": o.id, "order_no": o.order_no, "channel_account_id": o.channel_account_id, "customer_id": o.customer_id,
        "source": o.source, "currency": o.currency, "goods_amount": money(o.goods_amount),
        "discount_amount": money(o.discount_amount), "shipping_amount": money(o.shipping_amount),
        "payable_amount": money(o.payable_amount), "paid_amount": money(o.paid_amount),
        "refunded_amount": money(o.refunded_amount), "status": o.status, "payment_status": o.payment_status,
        "fulfillment_status": o.fulfillment_status, "after_sales_status": o.after_sales_status,
        "receiver_name": o.receiver_name, "receiver_phone": o.receiver_phone, "shipping_address": o.shipping_address,
        "buyer_remark": o.buyer_remark, "staff_remark": o.staff_remark,
        "pay_deadline": o.pay_deadline.isoformat() if o.pay_deadline else None,
        "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        "shipped_at": o.shipped_at.isoformat() if o.shipped_at else None,
        "completed_at": o.completed_at.isoformat() if o.completed_at else None,
        "cancelled_at": o.cancelled_at.isoformat() if o.cancelled_at else None,
        "cancel_reason": o.cancel_reason, "version": o.version,
        "created_at": o.created_at.isoformat(), "updated_at": o.updated_at.isoformat(),
    }
    data["receiver_phone_masked"] = _mask(o.receiver_phone)
    if with_items:
        items = db.execute(select(OrderItem).where(OrderItem.order_id == o.id).order_by(OrderItem.id)).scalars().all()
        data["items"] = [_item_view(i) for i in items]
        payments = db.execute(select(Payment).where(Payment.order_id == o.id).order_by(Payment.id)).scalars().all()
        data["payments"] = [{"id": p.id, "payment_no": p.payment_no, "method": p.method, "amount": money(p.amount),
                            "status": p.status, "pay_url": p.pay_url, "paid_at": p.paid_at.isoformat() if p.paid_at else None}
                           for p in payments]
    return data


def _history(db: Session, order_id: int, field: str, from_value, to_value, reason: str, actor: dict) -> None:
    db.add(OrderStatusHistory(tenant_id=settings.tenant_id, order_id=order_id, field=field,
                              from_value=from_value, to_value=to_value, reason=reason,
                              operator_type=actor.get("party", "SYSTEM"), operator_id=actor.get("id")))


def _apply_scope(stmt, actor: dict):
    if actor.get("party") in ("CUSTOMER", "GUEST"):
        return stmt.where(Order.customer_id == actor.get("customer_id"))
    channel_ids = actor.get("channel_ids")
    if channel_ids is not None:
        if not channel_ids:
            return stmt.where(Order.id < 0)
        return stmt.where(Order.channel_account_id.in_(channel_ids))
    return stmt


def _items_from_cart(db: Session, customer_id: int, cart_item_ids: list[int]) -> list[dict]:
    """C 端购物车结算：以购物车条目为准构造订单行。"""
    from app.models import Cart, CartItem

    rows = db.execute(
        select(CartItem, Cart).join(Cart, Cart.id == CartItem.cart_id)
        .where(CartItem.id.in_(cart_item_ids), Cart.customer_id == customer_id)
    ).all()
    if len(rows) != len(set(cart_item_ids)):
        raise ValidationError("购物车条目不存在或不属于当前客户")
    return [{"sku_id": item.sku_id, "quantity": item.quantity} for item, _cart in rows]


def create_order(db: Session, actor: dict, payload: dict) -> dict:
    customer_id = actor.get("customer_id")
    if not customer_id:
        raise Forbidden("仅客户账号可以下单", "AUTH_WRONG_PORTAL")
    items = list(payload.get("items") or [])
    if not items and payload.get("cart_item_ids"):
        items = _items_from_cart(db, customer_id, payload["cart_item_ids"])
    if not items:
        raise ValidationError("订单至少需要一个商品")
    channel_account_id = payload.get("channel_account_id")
    if not channel_account_id:
        raise ValidationError("缺少渠道账号")
    address_id = payload.get("address_id")
    address = get_or_404(db, CustomerAddress, address_id, "收货地址不存在") if address_id else None
    if address and address.customer_id != customer_id:
        raise Forbidden("收货地址不属于当前客户", "RESOURCE_FORBIDDEN")
    if address is None and not payload.get("receiver_name"):
        raise ValidationError("请选择收货地址或填写收货信息")
    snapshot = {
        "receiver_name": (address.receiver_name if address else payload["receiver_name"]),
        "receiver_phone": (address.receiver_phone if address else payload.get("receiver_phone")),
        "province": address.province if address else payload.get("province"),
        "city": address.city if address else payload.get("city"),
        "district": address.district if address else payload.get("district"),
        "detail": address.detail if address else payload.get("detail"),
    }

    order = Order(
        tenant_id=settings.tenant_id,
        order_no=seq("QY"),
        channel_account_id=channel_account_id,
        customer_id=customer_id,
        source=payload.get("source", "OFFICIAL_MALL"),
        goods_amount=0, discount_amount=0, shipping_amount=0, payable_amount=0,
        paid_amount=0, refunded_amount=0,
        status="CREATED", payment_status="UNPAID", fulfillment_status="UNSHIPPED", after_sales_status="NONE",
        receiver_name=snapshot["receiver_name"], receiver_phone=snapshot["receiver_phone"] or "",
        shipping_address=snapshot, address_id=address.id if address else None,
        buyer_remark=payload.get("buyer_remark"),
        pay_deadline=now() + timedelta(minutes=PAY_TTL_MINUTES),
    )
    db.add(order)
    db.flush()
    _history(db, order.id, "status", None, "CREATED", "创建订单", actor)

    goods_total = 0
    for raw in items:
        sku = get_or_404(db, Sku, raw["sku_id"], "SKU 不存在")
        product = get_or_404(db, Product, sku.product_id, "商品不存在")
        if sku.status != "ON_SALE" or product.status != "ON_SALE":
            raise Conflict("SKU_UNAVAILABLE", f"商品 {product.name} 当前不可购买")
        quantity = int(raw["quantity"])
        if quantity < 1 or quantity > 999:
            raise ValidationError("购买数量需在 1 到 999 之间")
        inv = inventory.pick_warehouse(db, sku.id, quantity)
        amount = sku.price * quantity
        goods_total += amount
        item = OrderItem(
            tenant_id=settings.tenant_id, order_id=order.id, product_id=product.id, sku_id=sku.id,
            warehouse_id=inv.warehouse_id, spu_code=product.spu_code, sku_code=sku.sku_code,
            product_name=product.name, sku_name=sku.name, spec_summary=sku.spec_summary,
            unit_price=sku.price, quantity=quantity, goods_amount=amount, discount_amount=0, payable_amount=amount,
        )
        db.add(item)
        db.flush()
        inventory.reserve(db, sku_id=sku.id, warehouse_id=inv.warehouse_id, qty=quantity,
                          order_id=order.id, order_item_id=item.id, expires_at=order.pay_deadline)
    order.goods_amount = goods_total
    order.shipping_amount = 0
    order.payable_amount = goods_total - order.discount_amount + order.shipping_amount
    order.status = "PENDING_PAYMENT"
    _history(db, order.id, "status", "CREATED", "PENDING_PAYMENT", "等待支付", {"party": "SYSTEM"})

    method = payload.get("payment_method", "MOCK")
    payment = Payment(
        tenant_id=settings.tenant_id, payment_no=seq("PAY"), order_id=order.id, method=method,
        amount=order.payable_amount, status="PENDING", expires_at=order.pay_deadline,
    )
    gateway = payment_gateway.create_payment(payment.payment_no, money(payment.amount), method, f"订单 {order.order_no}")
    payment.pay_url = gateway["pay_url"]
    db.add(payment)
    db.flush()

    audit.record(db, actor, "order_create", "order", order.id,
                 after={"order_no": order.order_no, "payable_amount": money(order.payable_amount)},
                 channel_account_id=order.channel_account_id)
    audit.emit(db, "order.created", "order", order.id,
               {"order_no": order.order_no, "customer_id": order.customer_id, "payable_amount": money(order.payable_amount),
                "channel_account_id": order.channel_account_id}, actor.get("request_id"))
    audit.emit(db, "payment.created", "payment", payment.id,
               {"payment_no": payment.payment_no, "order_no": order.order_no, "amount": money(payment.amount)},
               actor.get("request_id"))
    db.commit()
    return _order_view(db, order, with_items=True)


def list_orders(db: Session, actor: dict, *, page: int, page_size: int, status: str | None = None,
                payment_status: str | None = None, fulfillment_status: str | None = None,
                keyword: str | None = None, channel_account_id: int | None = None) -> dict:
    stmt = select(Order).where(Order.tenant_id == settings.tenant_id)
    stmt = _apply_scope(stmt, actor)
    if status:
        stmt = stmt.where(Order.status == status)
    if payment_status:
        stmt = stmt.where(Order.payment_status == payment_status)
    if fulfillment_status:
        stmt = stmt.where(Order.fulfillment_status == fulfillment_status)
    if channel_account_id:
        stmt = stmt.where(Order.channel_account_id == channel_account_id)
    if keyword:
        stmt = stmt.where(or_(Order.order_no.ilike(f"%{keyword}%"), Order.receiver_name.ilike(f"%{keyword}%")))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    offset, limit = page_offset(page, page_size)
    rows = db.execute(stmt.order_by(Order.created_at.desc(), Order.id.desc()).offset(offset).limit(limit)).scalars().all()
    return {"page": page, "page_size": page_size, "total": total, "meta": {"page": page, "page_size": page_size, "total": total},
            "items": [_order_view(db, o) for o in rows]}


def get_order(db: Session, actor: dict, order_id: int) -> dict:
    order = get_or_404(db, Order, order_id, "订单不存在或不可见")
    if actor.get("party") in ("CUSTOMER", "GUEST") and order.customer_id != actor.get("customer_id"):
        raise NotFound("订单不存在或不可见")
    channel_ids = actor.get("channel_ids")
    if actor.get("party") == "STAFF" and channel_ids is not None and order.channel_account_id not in channel_ids:
        raise Forbidden("订单超出数据范围", "CHANNEL_OUT_OF_SCOPE")
    return _order_view(db, order, with_items=True)


def timeline(db: Session, actor: dict, order_id: int) -> dict:
    order = get_or_404(db, Order, order_id, "订单不存在或不可见")
    if actor.get("party") in ("CUSTOMER", "GUEST") and order.customer_id != actor.get("customer_id"):
        raise NotFound("订单不存在或不可见")
    rows = db.execute(select(OrderStatusHistory).where(OrderStatusHistory.order_id == order_id)
                      .order_by(OrderStatusHistory.created_at, OrderStatusHistory.id)).scalars().all()
    return {"order_no": order.order_no, "items": [{"field": r.field, "from_value": r.from_value, "to_value": r.to_value,
            "reason": r.reason, "operator_type": r.operator_type, "created_at": r.created_at.isoformat()} for r in rows]}


def cancel(db: Session, actor: dict, order_id: int, reason: str | None = None) -> dict:
    order = db.execute(select(Order).where(Order.id == order_id, Order.tenant_id == settings.tenant_id).with_for_update()).scalar_one_or_none()
    if order is None:
        raise NotFound("订单不存在")
    if actor.get("party") in ("CUSTOMER", "GUEST") and order.customer_id != actor.get("customer_id"):
        raise NotFound("订单不存在")
    if order.status in ("CANCELLED", "CLOSED"):
        return _order_view(db, order, with_items=True)
    if order.fulfillment_status in ("SHIPPED", "PARTIAL_SHIPPED", "DELIVERED") or order.shipped_at:
        raise Conflict("ORDER_STATE_INVALID", "订单已发货，请通过退货退款流程处理")
    if order.status not in ("CREATED", "PENDING_PAYMENT", "PAID"):
        raise Conflict("ORDER_STATE_INVALID", f"订单当前状态 {order.status} 不允许取消")

    paid = order.payment_status in ("PAID", "PARTIAL")
    released = inventory.release_order(db, order.id, reason or "订单取消", actor.get("id"))
    for p in db.execute(select(Payment).where(Payment.order_id == order.id, Payment.status == "PENDING")).scalars().all():
        p.status = "CLOSED"
        p.closed_at = now()
    order.status = "CANCELLED"
    order.cancelled_at = now()
    order.cancel_reason = reason
    order.version = (order.version or 0) + 1
    _history(db, order.id, "status", "PENDING_PAYMENT" if not paid else "PAID", "CANCELLED", reason or "订单取消", actor)
    audit.record(db, actor, "order_cancel", "order", order.id, after={"reason": reason, "released_qty": released},
                 channel_account_id=order.channel_account_id)
    audit.emit(db, "order.cancelled", "order", order.id,
               {"order_no": order.order_no, "reason": reason, "released_qty": released}, actor.get("request_id"))
    db.commit()
    result = _order_view(db, order, with_items=True)
    if paid:
        result["refund_required"] = True
        result["note"] = "订单已支付，请通过售后或退款模块发起退款"
    return result


def confirm_receipt(db: Session, actor: dict, order_id: int) -> dict:
    order = db.execute(select(Order).where(Order.id == order_id).with_for_update()).scalar_one_or_none()
    if order is None:
        raise NotFound("订单不存在")
    if actor.get("party") in ("CUSTOMER", "GUEST") and order.customer_id != actor.get("customer_id"):
        raise NotFound("订单不存在")
    if order.fulfillment_status not in ("SHIPPED", "PARTIAL_SHIPPED", "DELIVERED"):
        raise Conflict("ORDER_STATE_INVALID", "订单尚未发货，无法确认收货")
    order.fulfillment_status = "DELIVERED"
    order.status = "COMPLETED"
    order.completed_at = now()
    order.version = (order.version or 0) + 1
    _history(db, order.id, "fulfillment_status", "SHIPPED", "DELIVERED", "客户确认收货", actor)
    _history(db, order.id, "status", "SHIPPED", "COMPLETED", "订单完成", actor)
    audit.record(db, actor, "order_confirm_receipt", "order", order.id, channel_account_id=order.channel_account_id)
    audit.emit(db, "order.completed", "order", order.id, {"order_no": order.order_no}, actor.get("request_id"))
    db.commit()
    return _order_view(db, order, with_items=True)


def update_address(db: Session, actor: dict, order_id: int, payload: dict) -> dict:
    order = get_or_404(db, Order, order_id, "订单不存在")
    if actor.get("party") in ("CUSTOMER", "GUEST") and order.customer_id != actor.get("customer_id"):
        raise NotFound("订单不存在")
    if order.fulfillment_status != "UNSHIPPED" or order.shipped_at:
        raise Conflict("ORDER_STATE_INVALID", "订单已发货，不能修改收货地址")
    before = dict(order.shipping_address or {})
    snapshot = dict(order.shipping_address or {})
    for field in ("receiver_name", "receiver_phone", "province", "city", "district", "detail"):
        if payload.get(field):
            snapshot[field] = payload[field]
    order.shipping_address = snapshot
    order.receiver_name = snapshot.get("receiver_name", order.receiver_name)
    order.receiver_phone = snapshot.get("receiver_phone", order.receiver_phone)
    order.version = (order.version or 0) + 1
    audit.record(db, actor, "order_address_update", "order", order.id, before=before, after=snapshot)
    db.commit()
    return _order_view(db, order, with_items=True)


def set_remark(db: Session, actor: dict, order_id: int, payload: dict) -> dict:
    order = get_or_404(db, Order, order_id, "订单不存在")
    if payload.get("buyer_remark") is not None:
        order.buyer_remark = payload["buyer_remark"]
    if payload.get("staff_remark") is not None:
        order.staff_remark = payload["staff_remark"]
    audit.record(db, actor, "order_remark", "order", order.id, after={"buyer_remark": order.buyer_remark, "staff_remark": order.staff_remark})
    db.commit()
    return _order_view(db, order)


def close_expired_orders(db: Session, limit: int = 100) -> dict:
    rows = db.execute(
        select(Order).where(Order.status.in_(["CREATED", "PENDING_PAYMENT"]), Order.pay_deadline < now())
        .order_by(Order.pay_deadline).limit(limit).with_for_update()
    ).scalars().all()
    closed = 0
    for order in rows:
        inventory.release_order(db, order.id, "支付超时自动关单", None)
        for p in db.execute(select(Payment).where(Payment.order_id == order.id, Payment.status == "PENDING")).scalars().all():
            p.status = "CLOSED"
            p.closed_at = now()
        prev = order.status
        order.status = "CANCELLED"
        order.cancelled_at = now()
        order.cancel_reason = "支付超时"
        _history(db, order.id, "status", prev, "CANCELLED", "支付超时自动关单", {"party": "SYSTEM"})
        audit.emit(db, "order.cancelled", "order", order.id, {"order_no": order.order_no, "reason": "支付超时"})
        closed += 1
    db.commit()
    return {"closed": closed}
