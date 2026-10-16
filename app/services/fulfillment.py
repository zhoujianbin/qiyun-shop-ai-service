from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import Conflict, NotFound, ValidationError
from app.integrations import logistics
from app.models import (
    Carrier, Order, OrderItem, OrderStatusHistory, Shipment, ShipmentItem, TrackingEvent, Warehouse,
)
from app.services import audit, inventory
from app.services.common import get_or_404, list_payload, now, page_offset, parse_dt, seq


def _mask(value: str | None) -> str | None:
    if not value:
        return None
    digits = str(value)
    return digits[:3] + "****" + digits[-4:] if len(digits) >= 7 else "***"


def _shipment_view(db: Session, s: Shipment, with_items: bool = False) -> dict:
    carrier = db.get(Carrier, s.carrier_id)
    data = {"id": s.id, "shipment_no": s.shipment_no, "order_id": s.order_id, "warehouse_id": s.warehouse_id,
            "carrier_id": s.carrier_id, "carrier_code": carrier.code if carrier else None,
            "carrier_name": carrier.name if carrier else None, "tracking_no": s.tracking_no, "status": s.status,
            "package_count": s.package_count, "receiver_name": s.receiver_name, "receiver_phone": s.receiver_phone,
            "receiver_phone_masked": _mask(s.receiver_phone), "exception_note": s.exception_note,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            "address_text": s.address_text,
            "tracking_url": logistics.tracking_url(carrier.tracking_url_template if carrier else None, s.tracking_no),
            "shipped_at": s.shipped_at.isoformat() if s.shipped_at else None,
            "delivered_at": s.delivered_at.isoformat() if s.delivered_at else None,
            "created_at": s.created_at.isoformat()}
    if with_items:
        rows = db.execute(select(ShipmentItem, OrderItem).join(OrderItem, OrderItem.id == ShipmentItem.order_item_id)
                          .where(ShipmentItem.shipment_id == s.id)).all()
        data["items"] = [{"id": item.id, "shipment_id": item.shipment_id, "order_item_id": item.order_item_id,
                          "sku_id": order_item.sku_id, "product_name": order_item.product_name,
                          "sku_name": order_item.sku_name, "quantity": item.quantity}
                         for item, order_item in rows]
        events = db.execute(select(TrackingEvent).where(TrackingEvent.shipment_id == s.id)
                            .order_by(TrackingEvent.event_time.desc())).scalars().all()
        data["tracking_events"] = [{"id": e.id, "shipment_id": e.shipment_id,
                                    "event_time": e.event_time.isoformat(), "status": e.status,
                                    "description": e.description, "location": e.location,
                                    "source": "CARRIER_WEBHOOK" if e.raw else "MANUAL", "raw": e.raw,
                                    "created_at": e.created_at.isoformat()} for e in events]
    return data


def ship(db: Session, actor: dict, order_id: int, payload: dict) -> dict:
    order = db.execute(select(Order).where(Order.id == order_id).with_for_update()).scalar_one_or_none()
    if order is None:
        raise NotFound("订单不存在")
    channel_ids = actor.get("channel_ids")
    if channel_ids is not None and order.channel_account_id not in channel_ids:
        raise Conflict("CHANNEL_OUT_OF_SCOPE", "订单超出数据范围")
    if order.payment_status not in ("PAID", "PARTIAL_REFUNDED") or order.status not in ("PAID", "FULFILLING", "SHIPPED"):
        raise Conflict("ORDER_STATE_INVALID", f"订单状态 {order.status}/{order.payment_status} 不允许发货")
    if order.fulfillment_status in ("SHIPPED", "DELIVERED"):
        raise Conflict("ORDER_STATE_INVALID", "订单已全部发货")
    carrier_id = payload.get("carrier_id")
    if not carrier_id and payload.get("carrier_code"):
        row = db.execute(select(Carrier).where(Carrier.tenant_id == settings.tenant_id,
                                               Carrier.code == str(payload["carrier_code"]).upper())).scalar_one_or_none()
        if row is None:
            raise NotFound(f"承运商 {payload['carrier_code']} 不存在")
        carrier_id = row.id
    carrier = get_or_404(db, Carrier, carrier_id, "承运商不存在")
    warehouse_id = payload.get("warehouse_id")
    raw_items = payload.get("items") or []
    if not raw_items:
        raise ValidationError("请至少选择一个订单行发货")
    items = db.execute(select(OrderItem).where(OrderItem.order_id == order.id)).scalars().all()
    item_map = {i.id: i for i in items}
    shipment = Shipment(
        tenant_id=settings.tenant_id, shipment_no=seq("SHP"), order_id=order.id,
        warehouse_id=warehouse_id, carrier_id=carrier.id, tracking_no=payload["tracking_no"],
        status="PENDING", package_count=int(payload.get("package_count", 1)),
        receiver_name=order.receiver_name, receiver_phone=order.receiver_phone,
        address_text=", ".join(str(x) for x in [
            (order.shipping_address or {}).get("province"), (order.shipping_address or {}).get("city"),
            (order.shipping_address or {}).get("district"), (order.shipping_address or {}).get("detail"),
        ] if x) or "-",
        shipped_at=now(), created_by=actor.get("id"),
    )
    db.add(shipment)
    db.flush()
    shipped_lines = 0
    for raw in raw_items:
        item = item_map.get(int(raw["order_item_id"]))
        if item is None:
            raise NotFound(f"订单行 {raw['order_item_id']} 不存在")
        quantity = int(raw["quantity"])
        remaining = item.quantity - (item.shipped_quantity or 0)
        if quantity < 1 or quantity > remaining:
            raise ValidationError(f"订单行 {item.sku_name} 最多可发 {remaining} 件")
        db.add(ShipmentItem(shipment_id=shipment.id, order_item_id=item.id, quantity=quantity))
        inventory.consume_for_shipment(db, sku_id=item.sku_id, warehouse_id=item.warehouse_id or warehouse_id,
                                       qty=quantity, order_item_id=item.id, shipment_id=shipment.id,
                                       operator_id=actor.get("id"))
        item.shipped_quantity = (item.shipped_quantity or 0) + quantity
        shipped_lines += 1
    db.flush()
    pending = db.execute(
        select(func.count()).select_from(OrderItem).where(OrderItem.order_id == order.id,
                                                         OrderItem.shipped_quantity < OrderItem.quantity)
    ).scalar_one()
    prev_fulfillment = order.fulfillment_status
    prev_status = order.status
    if pending == 0:
        order.fulfillment_status = "SHIPPED"
        order.status = "SHIPPED"
    else:
        order.fulfillment_status = "PARTIAL_SHIPPED"
        if order.status == "PAID":
            order.status = "FULFILLING"
    order.shipped_at = order.shipped_at or now()
    order.version = (order.version or 0) + 1
    db.add(OrderStatusHistory(tenant_id=settings.tenant_id, order_id=order.id, field="fulfillment_status",
                              from_value=prev_fulfillment, to_value=order.fulfillment_status, reason="仓库发货",
                              operator_type=actor.get("party", "SYSTEM"), operator_id=actor.get("id")))
    if prev_status != order.status:
        db.add(OrderStatusHistory(tenant_id=settings.tenant_id, order_id=order.id, field="status",
                                  from_value=prev_status, to_value=order.status, reason="订单已发货",
                                  operator_type=actor.get("party", "SYSTEM"), operator_id=actor.get("id")))
    audit.record(db, actor, "order_ship", "shipment", shipment.id,
                 after={"shipment_no": shipment.shipment_no, "tracking_no": shipment.tracking_no,
                        "lines": shipped_lines, "fulfillment_status": order.fulfillment_status},
                 channel_account_id=order.channel_account_id)
    audit.emit(db, "shipment.created", "shipment", shipment.id,
               {"shipment_no": shipment.shipment_no, "order_no": order.order_no,
                "tracking_no": shipment.tracking_no, "carrier": carrier.code}, actor.get("request_id"))
    db.commit()
    return _shipment_view(db, shipment, with_items=True)


def list_shipments(db: Session, actor: dict, *, page: int, page_size: int, status: str | None = None,
                   keyword: str | None = None) -> dict:
    stmt = select(Shipment).where(Shipment.tenant_id == settings.tenant_id)
    if actor.get("party") in ("CUSTOMER", "GUEST"):
        stmt = stmt.join(Order, Order.id == Shipment.order_id).where(Order.customer_id == actor.get("customer_id"))
    else:
        channel_ids = actor.get("channel_ids")
        if channel_ids is not None:
            if not channel_ids:
                stmt = stmt.where(Shipment.id < 0)
            else:
                stmt = stmt.join(Order, Order.id == Shipment.order_id).where(Order.channel_account_id.in_(channel_ids))
    if status:
        stmt = stmt.where(Shipment.status == status)
    if keyword:
        stmt = stmt.where(Shipment.shipment_no.ilike(f"%{keyword}%") | Shipment.tracking_no.ilike(f"%{keyword}%"))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    offset, limit = page_offset(page, page_size)
    rows = db.execute(stmt.order_by(Shipment.created_at.desc()).offset(offset).limit(limit)).scalars().all()
    return {"page": page, "page_size": page_size, "total": total, "meta": {"page": page, "page_size": page_size, "total": total},
            "items": [_shipment_view(db, s) for s in rows]}


def get_shipment(db: Session, actor: dict, shipment_id: int) -> dict:
    shipment = get_or_404(db, Shipment, shipment_id, "包裹不存在")
    order = db.get(Order, shipment.order_id)
    if actor.get("party") in ("CUSTOMER", "GUEST") and (order is None or order.customer_id != actor.get("customer_id")):
        raise NotFound("包裹不存在")
    return _shipment_view(db, shipment, with_items=True)


def list_carriers(db: Session) -> dict:
    rows = db.execute(select(Carrier).where(Carrier.tenant_id == settings.tenant_id).order_by(Carrier.id)).scalars().all()
    return list_payload([{"id": c.id, "code": c.code, "name": c.name,
                          "tracking_url_template": c.tracking_url_template, "status": c.status} for c in rows])


def add_tracking_event(db: Session, actor: dict, shipment_id: int, payload: dict) -> dict:
    shipment = get_or_404(db, Shipment, shipment_id, "包裹不存在")
    event = TrackingEvent(tenant_id=settings.tenant_id, shipment_id=shipment.id,
                          event_time=parse_dt(payload.get("event_time")), status=payload["status"],
                          description=payload["description"], location=payload.get("location"))
    db.add(event)
    if payload["status"] in ("PICKED_UP", "IN_TRANSIT", "DELIVERED", "EXCEPTION", "RETURNED"):
        shipment.status = payload["status"]
    if payload["status"] == "DELIVERED":
        shipment.delivered_at = event.event_time
        order = db.get(Order, shipment.order_id)
        pending = db.execute(
            select(func.count()).select_from(Shipment).where(Shipment.order_id == shipment.order_id,
                                                            Shipment.status != "DELIVERED")
        ).scalar_one()
        if order is not None and pending == 0 and order.fulfillment_status != "DELIVERED":
            order.fulfillment_status = "DELIVERED"
            db.add(OrderStatusHistory(tenant_id=settings.tenant_id, order_id=order.id, field="fulfillment_status",
                                      from_value="SHIPPED", to_value="DELIVERED", reason="物流签收",
                                      operator_type=actor.get("party", "SYSTEM"), operator_id=actor.get("id")))
    audit.record(db, actor, "tracking_event", "shipment", shipment.id, after={"status": payload["status"]})
    db.commit()
    return _shipment_view(db, shipment, with_items=True)


def logistics_callback(db: Session, payload: dict) -> dict:
    shipment = db.execute(select(Shipment).where(Shipment.shipment_no == payload["shipment_no"])).scalar_one_or_none()
    if shipment is None:
        raise NotFound("包裹不存在")
    order = db.get(Order, shipment.order_id)
    event = TrackingEvent(tenant_id=settings.tenant_id, shipment_id=shipment.id,
                          event_time=parse_dt(payload.get("event_time")), status=payload.get("status", "IN_TRANSIT"),
                          description=payload.get("description", "物流更新"), location=payload.get("location"),
                          raw=payload)
    db.add(event)
    try:
        db.flush()
    except Exception:
        db.rollback()
        return {"duplicate": True, "shipment_no": shipment.shipment_no}
    if payload.get("status") in ("PICKED_UP", "IN_TRANSIT", "DELIVERED", "EXCEPTION", "RETURNED"):
        shipment.status = payload["status"]
    if payload.get("status") == "DELIVERED":
        shipment.delivered_at = event.event_time
        if order is not None and order.fulfillment_status == "SHIPPED":
            order.fulfillment_status = "DELIVERED"
    audit.emit(db, "tracking.updated", "shipment", shipment.id,
               {"shipment_no": shipment.shipment_no, "status": payload.get("status")})
    db.commit()
    return {"duplicate": False, "shipment_no": shipment.shipment_no, "status": shipment.status}
