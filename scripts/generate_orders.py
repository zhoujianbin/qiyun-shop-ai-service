"""通过真实服务层生成测试订单：待付款、已付款、已发货、已完成、退款完成、退货中、待审核。"""
import random
from datetime import timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    AfterSalesApplication, AppUser, Carrier, ChannelAccount, CustomerAddress, CustomerProfile, Invoice,
    Order, OrderItem, Payment, Refund, Shipment, Sku, TrackingEvent, Warehouse,
)
from app.services import aftersales, fulfillment, invoice as invoice_service, order as order_service, payment as payment_service

PLANS = [
    ("PENDING", 18), ("PAID", 18), ("SHIPPED", 18), ("COMPLETED", 20),
    ("REFUND_DONE", 10), ("RETURN_WAITING", 8), ("AFTERSALES_REVIEW", 8),
]

REASONS = [
    ("QUALITY_ISSUE", "产品功能异常", "设备使用中出现功能异常，已按客服指引复位仍无效。"),
    ("DAMAGE_ON_ARRIVAL", "到货破损", "外包装破损，开箱发现外观有磕碰。"),
    ("WRONG_ITEM", "收到错误商品", "收到的型号与订单不一致。"),
    ("NOT_AS_DESCRIBED", "与描述不符", "实际功能与商品页说明存在差异。"),
    ("INSTALL_ISSUE", "安装问题", "上门安装后排布或联网存在问题。"),
]


def _customer_actor(user_id: int, label: str, customer_id: int) -> dict:
    return {"id": user_id, "party": "CUSTOMER", "label": label, "customer_id": customer_id, "channel_ids": None}


def _staff_actor(user_id: int, label: str) -> dict:
    return {"id": user_id, "party": "STAFF", "label": label, "channel_ids": None}


def _pick_plan(rng: random.Random) -> str:
    total = sum(w for _, w in PLANS)
    point = rng.uniform(0, total)
    acc = 0.0
    for name, weight in PLANS:
        acc += weight
        if point <= acc:
            return name
    return "COMPLETED"


def generate(db: Session, count: int = 60, seed: int = 42) -> dict:
    rng = random.Random(seed)
    customers = db.execute(select(CustomerProfile, AppUser).join(AppUser, AppUser.id == CustomerProfile.user_id)).all()
    channels = db.execute(select(ChannelAccount).where(ChannelAccount.status == "ACTIVE")).scalars().all()
    skus = db.execute(select(Sku).where(Sku.status == "ON_SALE")).scalars().all()
    carriers = db.execute(select(Carrier)).scalars().all()
    staff = {u.username: u for u in db.execute(select(AppUser).where(AppUser.party == "STAFF")).scalars().all()}
    ship_actor = _staff_actor(staff["ops01"].id, staff["ops01"].display_name)
    review_actor = _staff_actor(staff["aftersales01"].id, staff["aftersales01"].display_name)
    finance_actor = _staff_actor(staff["finance01"].id, staff["finance01"].display_name)

    stats = {name: 0 for name, _ in PLANS}
    stats["invoices"] = 0
    order_ids = []
    for i in range(count):
        profile, user = rng.choice(customers)
        channel = channels[i % len(channels)]
        address = db.execute(select(CustomerAddress).where(CustomerAddress.customer_id == profile.id,
                                                          CustomerAddress.is_default.is_(True))).scalars().first()
        actor = _customer_actor(user.id, user.display_name, profile.id)
        chosen = rng.sample(skus, rng.choice([1, 1, 2]))
        items = [{"sku_id": s.id, "quantity": rng.choice([1, 1, 2])} for s in chosen]
        created = order_service.create_order(db, actor, {
            "items": items, "channel_account_id": channel.id,
            "address_id": address.id if address else None,
            "receiver_name": user.display_name, "receiver_phone": user.phone,
            "province": "浙江省", "city": "杭州市", "district": "余杭区", "detail": "测试地址",
            "buyer_remark": rng.choice([None, None, "工作日送货", "请放快递柜"]),
            "source": "OFFICIAL_MALL" if channel.code == "OFFICIAL_MALL" else "ECOMMERCE",
        })
        order_id = created["id"]
        order_ids.append(order_id)
        plan = _pick_plan(rng)
        payment = db.execute(select(Payment).where(Payment.order_id == order_id).order_by(Payment.id.desc())).scalars().first()
        if plan == "PENDING":
            stats[plan] += 1
            continue
        payment_service.mock_succeed(db, actor, payment.id)
        full = db.get(Order, order_id)
        if plan == "PAID":
            stats[plan] += 1
        else:
            order_items = db.execute(select(OrderItem).where(OrderItem.order_id == order_id)).scalars().all()
            ship_items = [{"order_item_id": it.id, "quantity": it.quantity} for it in order_items]
            shipment = fulfillment.ship(db, ship_actor, order_id, {
                "carrier_id": rng.choice(carriers).id, "tracking_no": f"SF{rng.randint(10**11, 10**12 - 1)}",
                "warehouse_id": order_items[0].warehouse_id, "items": ship_items,
            })
            fulfillment.add_tracking_event(db, ship_actor, shipment["id"], {
                "status": "PICKED_UP", "description": "承运商已揽收", "location": "华东一号仓"})
            if plan in ("SHIPPED",):
                fulfillment.add_tracking_event(db, ship_actor, shipment["id"], {
                    "status": "IN_TRANSIT", "description": "快件已到达中转中心", "location": "杭州转运中心"})
                stats[plan] += 1
            else:
                fulfillment.add_tracking_event(db, ship_actor, shipment["id"], {
                    "status": "DELIVERED", "description": "快件已签收", "location": full.receiver_name})
                if plan == "COMPLETED":
                    order_service.confirm_receipt(db, _customer_actor(user.id, user.display_name, profile.id), order_id)
                    stats[plan] += 1
                else:
                    order_service.confirm_receipt(db, _customer_actor(user.id, user.display_name, profile.id), order_id)
                    reason_code, reason_text, description = rng.choice(REASONS)
                    as_type = "RETURN_REFUND" if plan == "RETURN_WAITING" else "REFUND_ONLY"
                    app = aftersales.create(db, actor, {
                        "order_id": order_id, "type": as_type, "reason_code": reason_code,
                        "reason_text": reason_text, "description": description,
                        "evidence": [], "expect_amount": float(full.paid_amount or 0),
                        "items": [{"order_item_id": order_items[0].id, "quantity": 1}],
                    })
                    if plan == "AFTERSALES_REVIEW":
                        stats[plan] += 1
                    elif plan == "RETURN_WAITING":
                        aftersales.review(db, review_actor, app["id"], {
                            "decision": "APPROVE", "approved_amount": float(full.paid_amount or 0),
                            "need_return": True, "review_note": "同意退货，请寄回并保持配件完整"})
                        if rng.random() < 0.6:
                            aftersales.return_shipment(db, actor, app["id"], {
                                "carrier_id": rng.choice(carriers).id, "tracking_no": f"ZTO{rng.randint(10**11, 10**12 - 1)}"})
                        stats[plan] += 1
                    else:
                        aftersales.review(db, review_actor, app["id"], {
                            "decision": "APPROVE", "approved_amount": float(full.paid_amount or 0),
                            "need_return": False, "review_note": "核实属实，同意退款"})
                        aftersales.complete(db, review_actor, app["id"], {"method": "ORIGINAL"})
                        stats[plan] += 1
        if plan in ("COMPLETED", "REFUND_DONE") and rng.random() < 0.45:
            try:
                created_invoice = invoice_service.apply(db, actor, {
                    "order_id": order_id, "type": rng.choice(["ELECTRONIC", "VAT_NORMAL"]),
                    "title_type": "PERSONAL", "title": user.display_name, "amount": float(full.paid_amount or 0)})
                if rng.random() < 0.7:
                    invoice_service.issue(db, finance_actor, created_invoice["id"], {})
                stats["invoices"] += 1
            except Exception:
                pass
    return {"orders": len(order_ids), "by_plan": stats, "order_ids": order_ids}


def backdate(db: Session, order_ids: list[int], seed: int = 7) -> int:
    """把测试订单及其关联记录整体前移，让报表与列表呈现真实时间分布。"""
    rng = random.Random(seed)
    shifted = 0
    for oid in order_ids:
        delta = timedelta(days=rng.uniform(0.1, 29.0), hours=rng.uniform(0, 12))
        db.execute(text("""update commerce.orders set created_at = created_at - :d, updated_at = updated_at - :d,
                pay_deadline = pay_deadline - :d, paid_at = paid_at - :d, shipped_at = shipped_at - :d,
                completed_at = completed_at - :d, cancelled_at = cancelled_at - :d where id = :i"""),
                   {"d": delta, "i": oid})
        db.execute(text("update commerce.order_status_history set created_at = created_at - :d where order_id = :i"),
                   {"d": delta, "i": oid})
        db.execute(text("""update commerce.payment set created_at = created_at - :d, updated_at = updated_at - :d,
                expires_at = expires_at - :d, paid_at = paid_at - :d, closed_at = closed_at - :d where order_id = :i"""),
                   {"d": delta, "i": oid})
        db.execute(text("""update commerce.shipment set created_at = created_at - :d, updated_at = updated_at - :d,
                shipped_at = shipped_at - :d, delivered_at = delivered_at - :d where order_id = :i"""),
                   {"d": delta, "i": oid})
        db.execute(text("""update commerce.tracking_event set created_at = created_at - :d, event_time = event_time - :d
                where shipment_id in (select id from commerce.shipment where order_id = :i)"""), {"d": delta, "i": oid})
        db.execute(text("""update commerce.after_sales_application set created_at = created_at - :d, updated_at = updated_at - :d,
                reviewed_at = reviewed_at - :d, received_at = received_at - :d, completed_at = completed_at - :d,
                closed_at = closed_at - :d, sla_due_at = sla_due_at - :d where order_id = :i"""), {"d": delta, "i": oid})
        db.execute(text("""update commerce.refund set created_at = created_at - :d, updated_at = updated_at - :d,
                approved_at = approved_at - :d, executed_at = executed_at - :d, closed_at = closed_at - :d
                where order_id = :i"""), {"d": delta, "i": oid})
        db.execute(text("""update commerce.invoice set created_at = created_at - :d, updated_at = updated_at - :d,
                issued_at = issued_at - :d, voided_at = voided_at - :d where order_id = :i"""), {"d": delta, "i": oid})
        db.execute(text("""update commerce.inventory_ledger set created_at = created_at - :d
                where ref_type in ('ORDER','SHIPMENT') and ref_id in (:oid, (select shipment_no from commerce.shipment where order_id = :i limit 1))"""),
                   {"d": delta, "i": oid, "oid": str(oid)})
        shifted += 1
    db.commit()
    return shifted
