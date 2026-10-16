from datetime import timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    AfterSalesApplication, CustomerProfile, Inventory, Order, OrderItem, Product, Refund, Sku, Warehouse,
)
from app.services.common import money, now


def _channel_filter(stmt, actor: dict, model, column):
    channel_ids = actor.get("channel_ids")
    if actor.get("party") == "STAFF" and channel_ids is not None:
        if not channel_ids:
            return stmt.where(column < 0)
        return stmt.where(column.in_(channel_ids))
    return stmt


def dashboard(db: Session, actor: dict, *, days: int = 30, channel_account_id: int | None = None) -> dict:
    since = now() - timedelta(days=days)
    stmt = select(
        func.count(Order.id),
        func.coalesce(func.sum(Order.payable_amount), 0),
        func.coalesce(func.sum(Order.paid_amount), 0),
        func.coalesce(func.sum(Order.refunded_amount), 0),
        func.coalesce(func.sum(case((Order.status == "CANCELLED", 1), else_=0)), 0),
        func.coalesce(func.sum(case((Order.payment_status.in_(["PAID", "PARTIAL_REFUNDED", "REFUNDED"]), 1), else_=0)), 0),
        func.coalesce(func.sum(case((Order.fulfillment_status.in_(["SHIPPED", "DELIVERED"]), 1), else_=0)), 0),
        func.coalesce(func.sum(case((Order.after_sales_status != "NONE", 1), else_=0)), 0),
    ).where(Order.tenant_id == settings.tenant_id, Order.created_at >= since)
    if channel_account_id:
        stmt = stmt.where(Order.channel_account_id == channel_account_id)
    stmt = _channel_filter(stmt, actor, Order, Order.channel_account_id)
    row = db.execute(stmt).one()
    order_count, payable, paid, refunded, cancelled, paid_orders, shipped, after_sales = row
    customers = db.execute(select(func.count()).select_from(CustomerProfile).where(CustomerProfile.tenant_id == settings.tenant_id)).scalar_one()
    products = db.execute(select(func.count()).select_from(Product).where(Product.tenant_id == settings.tenant_id)).scalar_one()
    skus = db.execute(select(func.count()).select_from(Sku).where(Sku.tenant_id == settings.tenant_id)).scalar_one()
    low_stock = db.execute(select(func.count()).select_from(Inventory).where(
        Inventory.tenant_id == settings.tenant_id, Inventory.qty_available <= Inventory.safety_stock)).scalar_one()
    pending_after_sales = db.execute(select(func.count()).select_from(AfterSalesApplication).where(
        AfterSalesApplication.tenant_id == settings.tenant_id,
        AfterSalesApplication.status.notin_(["COMPLETED", "REJECTED", "CANCELLED"]))).scalar_one()
    paid_total = float(paid or 0)
    refunded_total = float(refunded or 0)
    date_from = (now() - timedelta(days=days)).date().isoformat()
    date_to = now().date().isoformat()
    return {
        "generated_at": now().isoformat(),
        "date_from": date_from,
        "date_to": date_to,
        "range_days": days,
        "gross_sales_amount": money(payable),
        "net_sales_amount": money(paid_total - refunded_total),
        "refund_amount": money(refunded),
        "avg_order_value": money(paid_total / int(paid_orders)) if int(paid_orders) else "0.00",
        "new_customers": int(customers),
        "pending_after_sales_count": int(pending_after_sales),
        "top_products": [],
        "channel_breakdown": [],
        "order_count": int(order_count),
        "paid_order_count": int(paid_orders),
        "cancelled_order_count": int(cancelled),
        "shipped_order_count": int(shipped),
        "after_sales_order_count": int(after_sales),
        "gmv": money(payable),
        "paid_amount": money(paid),
        "refunded_amount": money(refunded),
        "net_revenue": money(paid_total - refunded_total),
        "average_order_value": money(paid_total / int(paid_orders)) if int(paid_orders) else "0.00",
        "pay_rate": round(int(paid_orders) / int(order_count), 4) if int(order_count) else 0,
        "cancel_rate": round(int(cancelled) / int(order_count), 4) if int(order_count) else 0,
        "customer_count": int(customers),
        "product_count": int(products),
        "sku_count": int(skus),
        "low_stock_count": int(low_stock),
        "pending_after_sales": int(pending_after_sales),
    }


def sales_daily(db: Session, actor: dict, *, days: int = 30, channel_account_id: int | None = None) -> dict:
    since = now() - timedelta(days=days)
    day = func.date_trunc("day", Order.created_at)
    stmt = select(
        day.label("stat_date"),
        Order.channel_account_id,
        func.count(Order.id),
        func.coalesce(func.sum(Order.payable_amount), 0),
        func.coalesce(func.sum(Order.paid_amount), 0),
        func.coalesce(func.sum(Order.refunded_amount), 0),
    ).where(Order.tenant_id == settings.tenant_id, Order.created_at >= since)
    if channel_account_id:
        stmt = stmt.where(Order.channel_account_id == channel_account_id)
    stmt = _channel_filter(stmt, actor, Order, Order.channel_account_id)
    stmt = stmt.group_by(day, Order.channel_account_id).order_by(day, Order.channel_account_id)
    rows = db.execute(stmt).all()
    return {"range_days": days, "items": [
        {"stat_date": r[0].date().isoformat(), "date": r[0].date().isoformat(), "channel_account_id": r[1],
         "order_count": r[2], "payable_amount": money(r[3]), "paid_amount": money(r[4]),
         "gmv": money(r[3]), "refund_amount": money(r[5]), "refunded_amount": money(r[5]),
         "new_customers": 0} for r in rows]}


def inventory_report(db: Session, actor: dict) -> dict:
    rows = db.execute(
        select(Inventory, Sku, Warehouse).join(Sku, Sku.id == Inventory.sku_id)
        .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
        .where(Inventory.tenant_id == settings.tenant_id).order_by(Sku.sku_code)
    ).all()
    total_available = sum(i.qty_available for i, _, _ in rows)
    total_reserved = sum(i.qty_reserved for i, _, _ in rows)
    total_value = sum(float(i.qty_available) * float(s.cost_price or s.price or 0) for i, s, _ in rows)
    alerts = [{"sku_code": s.sku_code, "sku_name": s.name, "warehouse_name": w.name,
               "qty_available": i.qty_available, "safety_stock": i.safety_stock}
              for i, s, w in rows if i.qty_available <= i.safety_stock]
    return {"generated_at": now().isoformat(), "total_available": total_available,
            "total_reserved": total_reserved, "total_cost_value": money(total_value),
            "total_available_qty": total_available, "total_reserved_qty": total_reserved,
            "total_in_transit_qty": sum(i.qty_in_transit for i, _, _ in rows),
            "warehouse_count": len({w.id for _, _, w in rows}), "sku_count": len({s.id for _, s, _ in rows}),
            "low_stock_count": len(alerts), "out_of_stock_count": sum(1 for i, _, _ in rows if i.qty_available == 0),
            "by_warehouse": [], "alerts": alerts}


def after_sales_report(db: Session, actor: dict, *, days: int = 30) -> dict:
    since = now() - timedelta(days=days)
    stmt = select(AfterSalesApplication.status, func.count()).where(
        AfterSalesApplication.tenant_id == settings.tenant_id,
        AfterSalesApplication.created_at >= since).group_by(AfterSalesApplication.status)
    rows = db.execute(stmt).all()
    refund_stmt = select(func.count(), func.coalesce(func.sum(Refund.amount), 0)).where(
        Refund.tenant_id == settings.tenant_id, Refund.created_at >= since)
    refund_row = db.execute(refund_stmt).one()
    by_type = db.execute(select(AfterSalesApplication.type, func.count()).where(
        AfterSalesApplication.tenant_id == settings.tenant_id,
        AfterSalesApplication.created_at >= since).group_by(AfterSalesApplication.type)).all()
    by_status_map = {r[0]: r[1] for r in rows}
    return {"generated_at": now().isoformat(), "range_days": days,
            "application_count": sum(by_status_map.values()),
            "completed_count": by_status_map.get("COMPLETED", 0),
            "rejected_count": by_status_map.get("REJECTED", 0),
            "processing_count": by_status_map.get("SUBMITTED", 0) + by_status_map.get("REVIEWING", 0),
            "by_status_map": by_status_map,
            "by_status": [{"status": key, "count": value} for key, value in by_status_map.items()],
            "by_type": [{"type": key, "count": value} for key, value in {r[0]: r[1] for r in by_type}.items()],
            "refund_count": int(refund_row[0]), "refund_amount": money(refund_row[1])}
