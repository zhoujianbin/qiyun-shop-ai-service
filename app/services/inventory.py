from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import Conflict, NotFound, ValidationError
from app.models import Inventory, InventoryLedger, InventoryReservation, Product, Sku, Warehouse
from app.services import audit
from app.services.common import get_or_404, list_payload, page_offset

ADMIN_CHANGE_TYPES = {"PURCHASE_IN", "RETURN_IN", "ADJUST", "DAMAGE", "TRANSFER_IN", "TRANSFER_OUT"}


def _warehouse_view(w: Warehouse) -> dict:
    return {"id": w.id, "code": w.code, "name": w.name, "region": w.region, "address": w.address,
            "priority": w.priority, "status": w.status}


def list_warehouses(db: Session) -> dict:
    rows = db.execute(select(Warehouse).where(Warehouse.tenant_id == settings.tenant_id).order_by(Warehouse.priority, Warehouse.id)).scalars().all()
    return list_payload([_warehouse_view(w) for w in rows])


def create_warehouse(db: Session, actor: dict, payload: dict) -> dict:
    wh = Warehouse(tenant_id=settings.tenant_id, code=payload["code"], name=payload["name"],
                   region=payload.get("region"), address=payload.get("address"), priority=payload.get("priority", 100))
    db.add(wh)
    db.flush()
    audit.record(db, actor, "warehouse_create", "warehouse", wh.id, after={"code": wh.code})
    db.commit()
    return _warehouse_view(wh)


def _ledger(db: Session, *, sku_id: int, warehouse_id: int, change_type: str, qty_delta: int,
            qty_after: int, avail_after: int, res_after: int, ref_type: str | None, ref_id: str | None,
            operator_id: int | None, remark: str | None) -> None:
    db.add(InventoryLedger(tenant_id=settings.tenant_id, sku_id=sku_id, warehouse_id=warehouse_id,
                           change_type=change_type, qty_delta=qty_delta, qty_after=qty_after,
                           qty_available_after=avail_after, qty_reserved_after=res_after,
                           ref_type=ref_type, ref_id=ref_id, operator_id=operator_id, remark=remark))


def _lock_row(db: Session, sku_id: int, warehouse_id: int) -> Inventory:
    row = db.execute(
        select(Inventory).where(Inventory.sku_id == sku_id, Inventory.warehouse_id == warehouse_id).with_for_update()
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(f"SKU {sku_id} 在仓库 {warehouse_id} 没有库存记录")
    return row


def pick_warehouse(db: Session, sku_id: int, qty: int) -> Inventory:
    """按仓库优先级选择可满足数量的仓库（一期单仓逻辑，多渠道可在配置层扩展）。"""
    rows = db.execute(
        select(Inventory).join(Warehouse, Warehouse.id == Inventory.warehouse_id)
        .where(Inventory.sku_id == sku_id, Warehouse.status == "ACTIVE",
               Inventory.qty_available - Inventory.qty_reserved >= qty)
        .order_by(Warehouse.priority, Warehouse.id).with_for_update(of=Inventory)
    ).scalars().all()
    if not rows:
        raise Conflict("INVENTORY_INSUFFICIENT", "可售库存不足", {"sku_id": sku_id, "required": qty})
    return rows[0]


def reserve(db: Session, *, sku_id: int, warehouse_id: int, qty: int, order_id=None, order_item_id=None, expires_at=None) -> None:
    result = db.execute(
        text("""update commerce.inventory set qty_available = qty_available - :q, qty_reserved = qty_reserved + :q,
                version = version + 1 where sku_id = :s and warehouse_id = :w and qty_available >= :q"""),
        {"q": qty, "s": sku_id, "w": warehouse_id},
    )
    if result.rowcount == 0:
        raise Conflict("INVENTORY_INSUFFICIENT", "可售库存不足", {"sku_id": sku_id, "warehouse_id": warehouse_id, "required": qty})
    row = _lock_row(db, sku_id, warehouse_id)
    _ledger(db, sku_id=sku_id, warehouse_id=warehouse_id, change_type="RESERVE", qty_delta=0,
            qty_after=row.qty_available + row.qty_reserved, avail_after=row.qty_available, res_after=row.qty_reserved,
            ref_type="ORDER", ref_id=str(order_id) if order_id else None, operator_id=None, remark="下单锁定")
    db.add(InventoryReservation(tenant_id=settings.tenant_id, order_id=order_id, order_item_id=order_item_id,
                                sku_id=sku_id, warehouse_id=warehouse_id, qty=qty, status="ACTIVE", expires_at=expires_at))


def release_order(db: Session, order_id: int, reason: str = "订单释放", actor_id: int | None = None) -> int:
    rows = db.execute(
        select(InventoryReservation).where(InventoryReservation.order_id == order_id,
                                          InventoryReservation.status == "ACTIVE").with_for_update()
    ).scalars().all()
    total = 0
    for r in rows:
        inv = _lock_row(db, r.sku_id, r.warehouse_id)
        inv.qty_available += r.qty
        inv.qty_reserved -= r.qty
        inv.version = (inv.version or 0) + 1
        r.status = "RELEASED"
        _ledger(db, sku_id=r.sku_id, warehouse_id=r.warehouse_id, change_type="RELEASE", qty_delta=0,
                qty_after=inv.qty_available + inv.qty_reserved, avail_after=inv.qty_available,
                res_after=inv.qty_reserved, ref_type="ORDER", ref_id=str(order_id), operator_id=actor_id, remark=reason)
        total += r.qty
    return total


def consume_for_shipment(db: Session, *, sku_id: int, warehouse_id: int, qty: int, order_item_id: int,
                         shipment_id: int, operator_id: int | None) -> None:
    result = db.execute(
        text("""update commerce.inventory set qty_reserved = qty_reserved - :q, version = version + 1
                where sku_id = :s and warehouse_id = :w and qty_reserved >= :q"""),
        {"q": qty, "s": sku_id, "w": warehouse_id},
    )
    if result.rowcount == 0:
        raise Conflict("INVENTORY_INSUFFICIENT", "已锁定库存不足，无法出库", {"sku_id": sku_id, "required": qty})
    inv = _lock_row(db, sku_id, warehouse_id)
    _ledger(db, sku_id=sku_id, warehouse_id=warehouse_id, change_type="SALE_OUT", qty_delta=-qty,
            qty_after=inv.qty_available + inv.qty_reserved, avail_after=inv.qty_available,
            res_after=inv.qty_reserved, ref_type="SHIPMENT", ref_id=str(shipment_id), operator_id=operator_id, remark="发货出库")
    res = db.execute(
        select(InventoryReservation).where(InventoryReservation.order_item_id == order_item_id,
                                          InventoryReservation.status == "ACTIVE").with_for_update()
    ).scalars().first()
    if res:
        res.status = "CONSUMED"
        res.released_at = None


def adjust(db: Session, actor: dict, payload: dict) -> dict:
    change_type = payload["change_type"]
    if change_type not in ADMIN_CHANGE_TYPES:
        raise ValidationError("不允许的库存变动类型：" + change_type)
    delta = int(payload["qty_delta"])
    if delta == 0:
        raise ValidationError("变动数量不能为 0")
    if change_type in ("PURCHASE_IN", "RETURN_IN", "TRANSFER_IN") and delta < 0:
        raise ValidationError(f"{change_type} 必须为正数")
    if change_type in ("DAMAGE", "TRANSFER_OUT") and delta > 0:
        raise ValidationError(f"{change_type} 必须为负数")
    sku = get_or_404(db, Sku, payload["sku_id"], "SKU 不存在")
    inv = _lock_row(db, sku.id, payload["warehouse_id"])
    expected = payload.get("version", payload.get("expected_version"))
    if expected is not None and inv.version != expected:
        raise Conflict("INVENTORY_VERSION_CONFLICT", "库存已被他人修改，请刷新后重试")
    before = {"qty_available": inv.qty_available, "qty_reserved": inv.qty_reserved, "version": inv.version}
    if inv.qty_available + delta < 0:
        raise Conflict("INVENTORY_INSUFFICIENT", "调整后可用库存不能为负")
    inv.qty_available += delta
    inv.version = (inv.version or 0) + 1
    if payload.get("safety_stock") is not None:
        inv.safety_stock = payload["safety_stock"]
    _ledger(db, sku_id=sku.id, warehouse_id=inv.warehouse_id, change_type=change_type, qty_delta=delta,
            qty_after=inv.qty_available + inv.qty_reserved, avail_after=inv.qty_available,
            res_after=inv.qty_reserved, ref_type="MANUAL", ref_id=None, operator_id=actor.get("id"),
            remark=payload.get("reason"))
    after = {"qty_available": inv.qty_available, "qty_reserved": inv.qty_reserved, "version": inv.version}
    audit.record(db, actor, "inventory_adjust", "inventory", f"{sku.id}:{inv.warehouse_id}", before=before, after=after,
                 channel_account_id=None)
    db.commit()
    return {"sku_id": sku.id, "warehouse_id": inv.warehouse_id, "qty_available": inv.qty_available,
            "qty_reserved": inv.qty_reserved, "version": inv.version, "change_type": change_type, "qty_delta": delta}


def list_inventory(db: Session, *, page: int, page_size: int, keyword: str | None = None,
                   warehouse_id: int | None = None, low_stock_only: bool = False) -> dict:
    stmt = (select(Inventory, Sku, Warehouse, Product).join(Sku, Sku.id == Inventory.sku_id)
            .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
            .join(Product, Product.id == Sku.product_id)
            .where(Inventory.tenant_id == settings.tenant_id))
    if keyword:
        stmt = stmt.where(Sku.sku_code.ilike(f"%{keyword}%") | Sku.name.ilike(f"%{keyword}%"))
    if warehouse_id:
        stmt = stmt.where(Inventory.warehouse_id == warehouse_id)
    if low_stock_only:
        stmt = stmt.where(Inventory.qty_available <= Inventory.safety_stock)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    offset, limit = page_offset(page, page_size)
    rows = db.execute(stmt.order_by(Sku.sku_code, Warehouse.priority).offset(offset).limit(limit)).all()
    items = [{"id": i.id, "sku_id": s.id, "sku_code": s.sku_code, "sku_name": s.name, "product_id": s.product_id,
              "product_name": p.name, "warehouse_id": w.id, "warehouse_name": w.name,
              "qty_available": i.qty_available, "qty_reserved": i.qty_reserved, "qty_in_transit": i.qty_in_transit,
              "sellable_qty": i.qty_available - i.qty_reserved, "safety_stock": i.safety_stock,
              "is_low_stock": i.qty_available <= i.safety_stock, "version": i.version,
              "updated_at": i.updated_at.isoformat() if i.updated_at else None} for i, s, w, p in rows]
    return {"page": page, "page_size": page_size, "total": total, "meta": {"page": page, "page_size": page_size, "total": total},
            "items": items}


def list_ledger(db: Session, *, page: int, page_size: int, sku_id: int | None = None,
                warehouse_id: int | None = None, change_type: str | None = None) -> dict:
    stmt = select(InventoryLedger).where(InventoryLedger.tenant_id == settings.tenant_id)
    if sku_id:
        stmt = stmt.where(InventoryLedger.sku_id == sku_id)
    if warehouse_id:
        stmt = stmt.where(InventoryLedger.warehouse_id == warehouse_id)
    if change_type:
        stmt = stmt.where(InventoryLedger.change_type == change_type)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    offset, limit = page_offset(page, page_size)
    rows = db.execute(stmt.order_by(InventoryLedger.created_at.desc(), InventoryLedger.id.desc()).offset(offset).limit(limit)).scalars().all()
    items = [{"id": r.id, "sku_id": r.sku_id, "warehouse_id": r.warehouse_id, "change_type": r.change_type,
              "qty_delta": r.qty_delta, "qty_after": r.qty_after, "ref_type": r.ref_type, "ref_id": r.ref_id,
              "remark": r.remark, "created_at": r.created_at.isoformat()} for r in rows]
    return {"page": page, "page_size": page_size, "total": total, "meta": {"page": page, "page_size": page_size, "total": total},
            "items": items}


def alerts(db: Session) -> dict:
    rows = db.execute(
        select(Inventory, Sku, Warehouse).join(Sku, Sku.id == Inventory.sku_id)
        .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
        .where(Inventory.tenant_id == settings.tenant_id, Inventory.qty_available <= Inventory.safety_stock)
        .order_by(Sku.sku_code)
    ).all()
    return list_payload([{"id": i.id, "sku_id": s.id, "sku_code": s.sku_code, "sku_name": s.name,
                          "warehouse_id": w.id, "warehouse_name": w.name, "qty_available": i.qty_available,
                          "qty_reserved": i.qty_reserved, "qty_in_transit": i.qty_in_transit,
                          "safety_stock": i.safety_stock, "is_low_stock": True,
                          "sellable_qty": i.qty_available - i.qty_reserved} for i, s, w in rows])
