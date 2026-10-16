from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import Conflict, NotFound, ValidationError
from app.models import (
    AfterSalesApplication, AfterSalesItem, AfterSalesMessage, Carrier, Order, OrderItem, OrderStatusHistory,
)
from app.services import audit, inventory, refund as refund_service
from app.services.common import get_or_404, money, now, page_offset, seq

TYPES = {"REFUND_ONLY", "RETURN_REFUND", "EXCHANGE", "REPAIR"}


def _view(db: Session, a: AfterSalesApplication, with_detail: bool = False) -> dict:
    data = {"id": a.id, "application_no": a.application_no, "order_id": a.order_id,
            "order_no": (db.get(Order, a.order_id).order_no if db.get(Order, a.order_id) else None),
            "order_item_id": None,
            "channel_account_id": a.channel_account_id, "type": a.type, "reason_code": a.reason_code,
            "reason_text": a.reason_text, "description": a.description, "evidence": a.evidence,
            "expect_amount": money(a.expect_amount), "approved_amount": money(a.approved_amount),
            "status": a.status, "need_return": a.need_return, "return_carrier_id": a.return_carrier_id,
            "return_tracking_no": a.return_tracking_no, "reviewer_id": a.reviewer_id,
            "reviewed_at": a.reviewed_at.isoformat() if a.reviewed_at else None, "review_note": a.review_note,
            "received_at": a.received_at.isoformat() if a.received_at else None,
            "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            "sla_due_at": a.sla_due_at.isoformat() if a.sla_due_at else None,
            "applied_at": a.created_at.isoformat(),
            "review_remark": a.review_note,
            "refund_amount": money(a.approved_amount or a.expect_amount),
            "evidence_attachment_ids": [item for item in (a.evidence or []) if isinstance(item, int)],
            "created_at": a.created_at.isoformat(), "updated_at": a.updated_at.isoformat(),
            "version": a.version}
    if with_detail:
        items = db.execute(select(AfterSalesItem).where(AfterSalesItem.application_id == a.id)).scalars().all()
        data["items"] = [{"order_item_id": i.order_item_id, "quantity": i.quantity, "amount": money(i.amount)} for i in items]
        if items:
            data["order_item_id"] = items[0].order_item_id
            data["quantity"] = items[0].quantity
        msgs = db.execute(select(AfterSalesMessage).where(AfterSalesMessage.application_id == a.id)
                          .order_by(AfterSalesMessage.created_at)).scalars().all()
        data["messages"] = [{"id": m.id, "application_id": m.application_id,
                             "author_type": m.author_type, "author_id": m.author_id,
                             "sender_type": m.author_type, "sender_id": m.author_id,
                             "content": m.content, "visible_to_customer": m.visible_to_customer,
                             "attachments": m.attachments,
                             "attachment_ids": [x for x in (m.attachments or []) if isinstance(x, int)],
                             "created_at": m.created_at.isoformat()} for m in msgs]
        from app.models import Refund

        refunds = db.execute(select(Refund).where(Refund.application_id == a.id)).scalars().all()
        data["refunds"] = [{"id": r.id, "refund_no": r.refund_no, "amount": money(r.amount), "status": r.status} for r in refunds]
    return data


def _apply_scope(stmt, actor: dict):
    if actor.get("party") in ("CUSTOMER", "GUEST"):
        return stmt.where(AfterSalesApplication.customer_id == actor.get("customer_id"))
    channel_ids = actor.get("channel_ids")
    if channel_ids is not None:
        if not channel_ids:
            return stmt.where(AfterSalesApplication.id < 0)
        return stmt.where(AfterSalesApplication.channel_account_id.in_(channel_ids))
    return stmt


def create(db: Session, actor: dict, payload: dict) -> dict:
    if actor.get("party") not in ("CUSTOMER", "GUEST"):
        raise Conflict("AFTER_SALES_STATE_INVALID", "仅客户可以提交售后申请")
    order = get_or_404(db, Order, payload["order_id"], "订单不存在")
    if order.customer_id != actor.get("customer_id"):
        raise NotFound("订单不存在")
    if payload["type"] not in TYPES:
        raise ValidationError("售后类型不合法")
    if order.status in ("CANCELLED", "CLOSED") and order.payment_status != "PAID":
        raise Conflict("AFTER_SALES_STATE_INVALID", "订单已取消或关闭，无法申请售后")
    items = db.execute(select(OrderItem).where(OrderItem.order_id == order.id)).scalars().all()
    raw_items = payload.get("items")
    if not raw_items and payload.get("order_item_id"):
        raw_items = [{"order_item_id": payload["order_item_id"], "quantity": payload.get("quantity") or 1}]
    if not raw_items:
        raw_items = [{"order_item_id": items[0].id, "quantity": payload.get("quantity") or 1}] if items else []
    evidence = payload.get("evidence") or payload.get("evidence_attachment_ids") or []
    expect_amount = payload.get("expect_amount")
    if expect_amount is None:
        expect_amount = payload.get("refund_amount")
    if not raw_items:
        raise ValidationError("订单没有可售后的商品")
    app = AfterSalesApplication(
        tenant_id=settings.tenant_id, application_no=seq("AS"), order_id=order.id, customer_id=order.customer_id,
        channel_account_id=order.channel_account_id, type=payload["type"], reason_code=payload["reason_code"],
        reason_text=payload.get("reason_text"), description=payload.get("description"),
        evidence=evidence, expect_amount=expect_amount,
        status="SUBMITTED", need_return=payload["type"] in ("RETURN_REFUND", "EXCHANGE"),
        sla_due_at=now() + __import__("datetime").timedelta(days=2),
    )
    db.add(app)
    db.flush()
    for raw in raw_items:
        item = next((i for i in items if i.id == int(raw["order_item_id"])), None)
        if item is None:
            raise NotFound(f"订单行 {raw['order_item_id']} 不存在")
        db.add(AfterSalesItem(application_id=app.id, order_item_id=item.id, quantity=int(raw.get("quantity", 1)),
                              amount=item.payable_amount))
        item.after_sales_status = "APPLYING"
    db.add(AfterSalesMessage(application_id=app.id, author_type="CUSTOMER", author_id=actor.get("id"),
                             content=payload.get("description") or "提交售后申请", attachments=evidence))
    order.after_sales_status = "APPLYING"
    audit.record(db, actor, "after_sales_create", "after_sales_application", app.id,
                 after={"application_no": app.application_no, "type": app.type},
                 channel_account_id=order.channel_account_id)
    audit.emit(db, "after_sales.created", "after_sales_application", app.id,
               {"application_no": app.application_no, "order_no": order.order_no}, actor.get("request_id"))
    db.commit()
    return _view(db, app, with_detail=True)


def list_applications(db: Session, actor: dict, *, page: int, page_size: int, status: str | None = None,
                      type_: str | None = None, keyword: str | None = None) -> dict:
    stmt = select(AfterSalesApplication).where(AfterSalesApplication.tenant_id == settings.tenant_id)
    stmt = _apply_scope(stmt, actor)
    if status:
        stmt = stmt.where(AfterSalesApplication.status == status)
    if type_:
        stmt = stmt.where(AfterSalesApplication.type == type_)
    if keyword:
        stmt = stmt.where(AfterSalesApplication.application_no.ilike(f"%{keyword}%"))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    offset, limit = page_offset(page, page_size)
    rows = db.execute(stmt.order_by(AfterSalesApplication.created_at.desc()).offset(offset).limit(limit)).scalars().all()
    return {"page": page, "page_size": page_size, "total": total, "meta": {"page": page, "page_size": page_size, "total": total},
            "items": [_view(db, a) for a in rows]}


def get_application(db: Session, actor: dict, application_id: int) -> dict:
    app = get_or_404(db, AfterSalesApplication, application_id, "售后单不存在")
    if actor.get("party") in ("CUSTOMER", "GUEST") and app.customer_id != actor.get("customer_id"):
        raise NotFound("售后单不存在")
    return _view(db, app, with_detail=True)


def review(db: Session, actor: dict, application_id: int, payload: dict) -> dict:
    app = db.execute(select(AfterSalesApplication).where(AfterSalesApplication.id == application_id).with_for_update()).scalar_one_or_none()
    if app is None:
        raise NotFound("售后单不存在")
    if app.status in ("COMPLETED", "CANCELLED"):
        raise Conflict("AFTER_SALES_STATE_INVALID", f"售后单已 {app.status}，不能重复审核")
    decision = payload["decision"]
    if decision == "REJECT":
        app.status = "REJECTED"
        app.reviewer_id = actor.get("id")
        app.reviewed_at = now()
        app.review_note = payload.get("review_note") or payload.get("remark") or payload.get("reason")
    elif decision == "APPROVE":
        amount = payload.get("approved_amount") or app.expect_amount
        if amount is None or float(amount) <= 0:
            raise ValidationError("通过售后必须给出审批金额")
        app.approved_amount = amount
        app.reviewer_id = actor.get("id")
        app.reviewed_at = now()
        app.review_note = payload.get("review_note") or payload.get("remark") or payload.get("reason")
        need_return = payload.get("need_return") if payload.get("need_return") is not None else app.need_return
        app.need_return = bool(need_return)
        app.status = "WAITING_RETURN" if app.need_return else "APPROVED"
    else:
        raise ValidationError("decision 只能是 APPROVE 或 REJECT")
    order = db.get(Order, app.order_id)
    order.after_sales_status = "REJECTED" if app.status == "REJECTED" else "PROCESSING"
    audit.record(db, actor, "after_sales_review", "after_sales_application", app.id,
                 after={"decision": decision, "status": app.status, "approved_amount": money(app.approved_amount)},
                 channel_account_id=app.channel_account_id)
    audit.emit(db, "after_sales.reviewed", "after_sales_application", app.id,
               {"application_no": app.application_no, "decision": decision, "status": app.status},
               actor.get("request_id"))
    db.commit()
    return _view(db, app, with_detail=True)


def return_shipment(db: Session, actor: dict, application_id: int, payload: dict) -> dict:
    app = get_or_404(db, AfterSalesApplication, application_id, "售后单不存在")
    if actor.get("party") in ("CUSTOMER", "GUEST") and app.customer_id != actor.get("customer_id"):
        raise NotFound("售后单不存在")
    if app.status != "WAITING_RETURN":
        raise Conflict("AFTER_SALES_STATE_INVALID", f"当前状态 {app.status} 不能填写退货物流")
    carrier_id = payload.get("carrier_id")
    if not carrier_id and payload.get("carrier_code"):
        row = db.execute(select(Carrier).where(Carrier.tenant_id == settings.tenant_id,
                                               Carrier.code == str(payload["carrier_code"]).upper())).scalar_one_or_none()
        if row is None:
            raise NotFound(f"承运商 {payload['carrier_code']} 不存在")
        carrier_id = row.id
    get_or_404(db, Carrier, carrier_id, "承运商不存在")
    app.return_carrier_id = carrier_id
    app.return_tracking_no = payload["tracking_no"]
    app.status = "RETURN_SHIPPED"
    audit.record(db, actor, "after_sales_return_shipment", "after_sales_application", app.id,
                 after={"tracking_no": app.return_tracking_no})
    db.commit()
    return _view(db, app, with_detail=True)


def receive(db: Session, actor: dict, application_id: int, payload: dict) -> dict:
    app = get_or_404(db, AfterSalesApplication, application_id, "售后单不存在")
    if app.status not in ("RETURN_SHIPPED", "WAITING_RETURN"):
        raise Conflict("AFTER_SALES_STATE_INVALID", f"当前状态 {app.status} 不能确认收货")
    app.status = "RECEIVED"
    app.received_at = now()
    restock = payload.get("restock")
    if restock is None:
        restock = bool(payload.get("received")) or payload.get("warehouse_id") is not None
    if restock:
        items = db.execute(select(AfterSalesItem).where(AfterSalesItem.application_id == app.id)).scalars().all()
        for line in items:
            order_item = db.get(OrderItem, line.order_item_id)
            if order_item and order_item.warehouse_id:
                inv = db.execute(select(inventory.Inventory).where(
                    inventory.Inventory.sku_id == order_item.sku_id,
                    inventory.Inventory.warehouse_id == order_item.warehouse_id).with_for_update()).scalar_one_or_none()
                if inv is not None:
                    inv.qty_available += line.quantity
                    inv.version = (inv.version or 0) + 1
                    inventory._ledger(db, sku_id=order_item.sku_id, warehouse_id=order_item.warehouse_id,
                                      change_type="RETURN_IN", qty_delta=line.quantity,
                                      qty_after=inv.qty_available + inv.qty_reserved,
                                      avail_after=inv.qty_available, res_after=inv.qty_reserved,
                                      ref_type="AFTER_SALES", ref_id=str(app.id), operator_id=actor.get("id"),
                                      remark="售后退货入库")
    audit.record(db, actor, "after_sales_receive", "after_sales_application", app.id, after={"status": app.status})
    db.commit()
    return _view(db, app, with_detail=True)


def complete(db: Session, actor: dict, application_id: int, payload: dict) -> dict:
    app = get_or_404(db, AfterSalesApplication, application_id, "售后单不存在")
    if app.status in ("COMPLETED", "CANCELLED", "REJECTED"):
        raise Conflict("AFTER_SALES_STATE_INVALID", f"售后单已 {app.status}")
    if app.approved_amount is None and payload.get("refund_amount") is not None:
        app.approved_amount = payload["refund_amount"]
    if app.approved_amount is None:
        raise ValidationError("尚未审批金额，不能完成售后")
    if app.need_return and app.status != "RECEIVED":
        raise Conflict("AFTER_SALES_STATE_INVALID",
                       f"需要退货的售后单必须确认收货后才能完成，当前状态 {app.status}")
    order = db.get(Order, app.order_id)
    app.status = "REFUNDING"
    db.commit()
    created = refund_service.create(db, actor, {"order_id": order.id, "application_id": app.id,
                                                "amount": app.approved_amount, "method": payload.get("method", "ORIGINAL"),
                                                "reason": f"售后单 {app.application_no} 退款"})
    executed = refund_service.execute(db, actor, created["id"])
    app.status = "COMPLETED"
    app.completed_at = now()
    order.after_sales_status = "COMPLETED"
    items = db.execute(select(AfterSalesItem).where(AfterSalesItem.application_id == app.id)).scalars().all()
    for line in items:
        order_item = db.get(OrderItem, line.order_item_id)
        if order_item:
            order_item.after_sales_status = "COMPLETED"
            order_item.refunded_amount = (order_item.refunded_amount or 0) + (line.amount or 0)
            if order_item.refunded_amount >= order_item.payable_amount:
                order_item.item_status = "REFUNDED"
    audit.record(db, actor, "after_sales_complete", "after_sales_application", app.id,
                 after={"status": app.status, "refund_no": executed["refund_no"]},
                 channel_account_id=app.channel_account_id)
    audit.emit(db, "after_sales.completed", "after_sales_application", app.id,
               {"application_no": app.application_no, "refund_no": executed["refund_no"]}, actor.get("request_id"))
    db.commit()
    return {**_view(db, app, with_detail=True), "refund": executed}


def cancel(db: Session, actor: dict, application_id: int, reason: str | None = None) -> dict:
    app = get_or_404(db, AfterSalesApplication, application_id, "售后单不存在")
    if actor.get("party") in ("CUSTOMER", "GUEST") and app.customer_id != actor.get("customer_id"):
        raise NotFound("售后单不存在")
    if app.status in ("COMPLETED", "CANCELLED"):
        raise Conflict("AFTER_SALES_STATE_INVALID", f"售后单已 {app.status}")
    app.status = "CANCELLED"
    app.review_note = reason
    app.closed_at = now()
    order = db.get(Order, app.order_id)
    order.after_sales_status = "NONE"
    items = db.execute(select(AfterSalesItem).where(AfterSalesItem.application_id == app.id)).scalars().all()
    for line in items:
        order_item = db.get(OrderItem, line.order_item_id)
        if order_item and order_item.item_status == "NORMAL":
            order_item.after_sales_status = "NONE"
    audit.record(db, actor, "after_sales_cancel", "after_sales_application", app.id, after={"reason": reason})
    db.commit()
    return _view(db, app, with_detail=True)


def add_message(db: Session, actor: dict, application_id: int, payload: dict) -> dict:
    app = get_or_404(db, AfterSalesApplication, application_id, "售后单不存在")
    if actor.get("party") in ("CUSTOMER", "GUEST") and app.customer_id != actor.get("customer_id"):
        raise NotFound("售后单不存在")
    visible = payload.get("visible_to_customer", True) if actor.get("party") == "STAFF" else True
    attachments = payload.get("attachments") or payload.get("attachment_ids") or []
    db.add(AfterSalesMessage(application_id=app.id, author_type=actor.get("party", "SYSTEM"),
                             author_id=actor.get("id"), content=payload["content"],
                             attachments=attachments, visible_to_customer=visible))
    audit.record(db, actor, "after_sales_message", "after_sales_application", app.id)
    db.commit()
    return _view(db, app, with_detail=True)
