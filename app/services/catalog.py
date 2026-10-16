from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import Conflict, NotFound, ValidationError
from app.models import (AttributeDefinition, Brand, Category, Inventory, PriceChangeLog, Product,
                       ProductAttributeValue, ProductMedia, Sku, SkuAttributeValue)
from app.services import audit
from app.services.common import get_or_404, list_payload, money, now, page_offset


PRODUCT_TYPE_TO_LINE = {
    "SMART_LOCK": "智能门锁",
    "CAMERA": "家用摄像头",
    "CLEANING_ROBOT": "清洁机器人",
    "SMART_LIGHT": "智能灯具",
    "HOME_GATEWAY": "家庭网关",
    "ACCESSORY": "配件耗材",
    "CONSUMABLE": "配件耗材",
    "CLOUD_SERVICE": "云服务",
    "INSTALL_SERVICE": "安装维修",
}
LINE_TO_PRODUCT_TYPE = {
    "智能门锁": "SMART_LOCK",
    "家用摄像头": "CAMERA",
    "清洁机器人": "CLEANING_ROBOT",
    "智能灯具": "SMART_LIGHT",
    "家庭网关": "HOME_GATEWAY",
    "配件耗材": "ACCESSORY",
    "云服务": "CLOUD_SERVICE",
    "安装维修": "INSTALL_SERVICE",
}


def _brand_view(b: Brand) -> dict:
    return {"id": b.id, "code": b.code, "name": b.name, "logo_url": b.logo_url, "status": b.status, "sort_order": b.sort_order}


def _category_view(c: Category) -> dict:
    return {"id": c.id, "code": c.code, "name": c.name, "parent_id": c.parent_id, "path": c.path,
            "depth": c.depth, "sort_order": c.sort_order, "icon_url": c.icon_url, "status": c.status}


def _product_attributes(db: Session, product_id: int) -> list[dict]:
    rows = db.execute(
        select(ProductAttributeValue, AttributeDefinition)
        .join(AttributeDefinition, AttributeDefinition.id == ProductAttributeValue.attribute_id)
        .where(ProductAttributeValue.product_id == product_id)
    ).all()
    return [{"product_id": product_id, "attribute_id": definition.id, "code": definition.code,
             "name": definition.name, "data_type": definition.data_type, "unit": definition.unit,
             "value_text": value.value_text, "is_spec": definition.is_spec,
             "options": definition.options} for value, definition in rows]


def _sku_view(s: Sku) -> dict:
    return {"id": s.id, "product_id": s.product_id, "sku_code": s.sku_code, "name": s.name,
            "spec_summary": s.spec_summary, "price": money(s.price), "market_price": money(s.market_price),
            "cost_price": money(s.cost_price), "barcode": s.barcode, "weight_g": s.weight_g, "status": s.status}


def _product_view(db: Session, p: Product, with_skus: bool = False) -> dict:
    brand = db.get(Brand, p.brand_id) if p.brand_id else None
    category = db.get(Category, p.category_id) if p.category_id else None
    data = {
        "id": p.id, "spu_code": p.spu_code, "name": p.name, "brand_id": p.brand_id, "category_id": p.category_id,
        "category_name": category.name if category else None,
        "brand_name": brand.name if brand else None,
        "product_line": p.product_line, "product_type": LINE_TO_PRODUCT_TYPE.get(p.product_line or "", None),
        "channel_scope": [], "model_code": p.model_code, "subtitle": p.subtitle,
        "description_md": p.description_md, "highlights": p.highlights, "spec_summary": p.spec_summary,
        "warranty_summary": p.warranty_summary, "install_required": p.install_required, "install_notes": p.install_notes,
        "service_scope": p.service_scope, "currency": p.currency, "min_price": money(p.min_price),
        "max_price": money(p.max_price), "status": p.status, "published_at": p.published_at.isoformat() if p.published_at else None,
        "version": p.version,
    }
    media = db.execute(select(ProductMedia).where(ProductMedia.product_id == p.id).order_by(ProductMedia.sort_order)).scalars().all()
    data["media"] = [{"id": m.id, "product_id": m.product_id, "url": m.url,
                      "thumb_url": (m.url[:-5] + "-thumb.webp") if m.url.endswith(".webp") else None,
                      "media_type": m.media_type,
                      "alt_text": m.alt_text, "sort_order": m.sort_order, "is_main": index == 0}
                     for index, m in enumerate(media)]
    data["attributes"] = _product_attributes(db, p.id)
    if with_skus:
        skus = db.execute(select(Sku).where(Sku.product_id == p.id).order_by(Sku.sort_order, Sku.id)).scalars().all()
        data["skus"] = []
        for s in skus:
            item = _sku_view(s)
            rows = db.execute(
                select(Inventory.warehouse_id, Inventory.qty_available, Inventory.qty_reserved)
                .where(Inventory.sku_id == s.id)
            ).all()
            item["inventory"] = [
                {"warehouse_id": r[0], "qty_available": r[1], "qty_reserved": r[2], "sellable": r[1] - r[2]} for r in rows
            ]
            item["sellable_qty"] = sum(r[1] - r[2] for r in rows)
            data["skus"].append(item)
    return data


def list_brands(db: Session) -> dict:
    rows = db.execute(select(Brand).where(Brand.tenant_id == settings.tenant_id).order_by(Brand.sort_order, Brand.id)).scalars().all()
    return list_payload([_brand_view(b) for b in rows])


def create_brand(db: Session, actor: dict, payload: dict) -> dict:
    brand = Brand(tenant_id=settings.tenant_id, code=payload["code"], name=payload["name"], logo_url=payload.get("logo_url"), sort_order=payload.get("sort_order", 0))
    db.add(brand)
    db.flush()
    audit.record(db, actor, "brand_create", "brand", brand.id, after={"code": brand.code, "name": brand.name})
    db.commit()
    return _brand_view(brand)


def list_categories(db: Session) -> list[dict]:
    rows = db.execute(select(Category).where(Category.tenant_id == settings.tenant_id).order_by(Category.depth, Category.sort_order, Category.id)).scalars().all()
    return [_category_view(c) for c in rows]


def create_category(db: Session, actor: dict, payload: dict) -> dict:
    parent = get_or_404(db, Category, payload["parent_id"], "父类目不存在") if payload.get("parent_id") else None
    depth = (parent.depth + 1) if parent else 1
    if depth > 5:
        raise ValidationError("类目层级不能超过 5 级")
    cat = Category(tenant_id=settings.tenant_id, parent_id=parent.id if parent else None, code=payload["code"],
                   name=payload["name"], path="", depth=depth, sort_order=payload.get("sort_order", 0))
    db.add(cat)
    db.flush()
    cat.path = (parent.path if parent else "/") + str(cat.id) + "/"
    audit.record(db, actor, "category_create", "category", cat.id, after={"code": cat.code, "name": cat.name})
    db.commit()
    return _category_view(cat)


def update_category(db: Session, actor: dict, category_id: int, payload: dict) -> dict:
    cat = get_or_404(db, Category, category_id, "类目不存在")
    before = _category_view(cat)
    for field in ("name", "sort_order", "icon_url", "status"):
        if field in payload and payload[field] is not None:
            setattr(cat, field, payload[field])
    audit.record(db, actor, "category_update", "category", cat.id, before=before, after=_category_view(cat))
    db.commit()
    return _category_view(cat)


def list_products(db: Session, actor: dict, *, page: int, page_size: int, keyword: str | None = None,
                  category_id: int | None = None, status: str | None = None,
                  product_type: str | None = None) -> dict:
    stmt = select(Product).where(Product.tenant_id == settings.tenant_id)
    if keyword:
        stmt = stmt.where(or_(Product.name.ilike(f"%{keyword}%"), Product.spu_code.ilike(f"%{keyword}%")))
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if status:
        stmt = stmt.where(Product.status == status)
    if product_type:
        line = PRODUCT_TYPE_TO_LINE.get(product_type)
        stmt = stmt.where(Product.product_line == line) if line else stmt.where(Product.id < 0)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    offset, limit = page_offset(page, page_size)
    rows = db.execute(stmt.order_by(Product.sort_order, Product.id.desc()).offset(offset).limit(limit)).scalars().all()
    return {"page": page, "page_size": page_size, "total": total, "meta": {"page": page, "page_size": page_size, "total": total},
            "items": [_product_view(db, p, with_skus=True) for p in rows]}


def get_product(db: Session, product_id: int) -> dict:
    product = get_or_404(db, Product, product_id)
    return _product_view(db, product, with_skus=True)


def create_product(db: Session, actor: dict, payload: dict) -> dict:
    get_or_404(db, Category, payload["category_id"], "类目不存在")
    product = Product(
        tenant_id=settings.tenant_id,
        spu_code=payload["spu_code"],
        name=payload["name"],
        brand_id=payload.get("brand_id"),
        category_id=payload["category_id"],
        product_line=payload.get("product_line"),
        model_code=payload.get("model_code"),
        subtitle=payload.get("subtitle"),
        description_md=payload.get("description_md"),
        highlights=payload.get("highlights", []),
        spec_summary=payload.get("spec_summary", {}),
        warranty_summary=payload.get("warranty_summary"),
        install_required=payload.get("install_required", False),
        install_notes=payload.get("install_notes"),
        service_scope=payload.get("service_scope"),
        min_price=0,
        max_price=0,
        status="DRAFT",
        created_by=actor.get("id"),
        updated_by=actor.get("id"),
    )
    db.add(product)
    db.flush()
    audit.record(db, actor, "product_create", "product", product.id, after={"spu_code": product.spu_code})
    db.commit()
    return _product_view(db, product, with_skus=True)


def update_product(db: Session, actor: dict, product_id: int, payload: dict) -> dict:
    product = get_or_404(db, Product, product_id)
    before = _product_view(db, product)
    for field in ("name", "brand_id", "category_id", "product_line", "model_code", "subtitle", "description_md",
                  "highlights", "spec_summary", "warranty_summary", "install_required", "install_notes",
                  "service_scope", "sort_order"):
        if field in payload and payload[field] is not None:
            setattr(product, field, payload[field])
    product.version = (product.version or 0) + 1
    product.updated_by = actor.get("id")
    audit.record(db, actor, "product_update", "product", product.id, before=before, after=_product_view(db, product))
    db.commit()
    return _product_view(db, product, with_skus=True)


def set_product_status(db: Session, actor: dict, product_id: int, status: str) -> dict:
    product = get_or_404(db, Product, product_id)
    if status == "ON_SALE":
        sku_count = db.execute(select(func.count()).select_from(Sku).where(Sku.product_id == product.id, Sku.status == "ON_SALE")).scalar_one()
        if sku_count == 0:
            raise Conflict("PRODUCT_NO_SKU", "至少需要一个在售 SKU 才能上架")
        product.published_at = product.published_at or now()
    product.status = status
    product.version = (product.version or 0) + 1
    audit.record(db, actor, "product_status", "product", product.id, after={"status": status})
    db.commit()
    return _product_view(db, product, with_skus=True)


def _refresh_price_range(db: Session, product_id: int) -> None:
    row = db.execute(select(func.min(Sku.price), func.max(Sku.price)).where(Sku.product_id == product_id)).one()
    product = db.get(Product, product_id)
    if product and row[0] is not None:
        product.min_price = row[0]
        product.max_price = row[1]


def create_sku(db: Session, actor: dict, product_id: int, payload: dict) -> dict:
    get_or_404(db, Product, product_id, "商品不存在")
    sku = Sku(
        tenant_id=settings.tenant_id,
        product_id=product_id,
        sku_code=payload["sku_code"],
        name=payload["name"],
        spec_summary=payload.get("spec_summary"),
        price=payload["price"],
        market_price=payload.get("market_price"),
        cost_price=payload.get("cost_price"),
        barcode=payload.get("barcode"),
        weight_g=payload.get("weight_g"),
        status=payload.get("status", "ON_SALE"),
        sort_order=payload.get("sort_order", 0),
    )
    db.add(sku)
    db.flush()
    _refresh_price_range(db, product_id)
    audit.record(db, actor, "sku_create", "sku", sku.id, after={"sku_code": sku.sku_code, "price": money(sku.price)})
    db.commit()
    return _sku_view(sku)


def update_sku(db: Session, actor: dict, sku_id: int, payload: dict) -> dict:
    sku = get_or_404(db, Sku, sku_id, "SKU 不存在")
    before = _sku_view(sku)
    old_price = sku.price
    for field in ("name", "spec_summary", "price", "market_price", "cost_price", "barcode", "weight_g", "status", "sort_order"):
        if field in payload and payload[field] is not None:
            setattr(sku, field, payload[field])
    sku.version = (sku.version or 0) + 1
    if payload.get("price") is not None and sku.price != old_price:
        db.add(PriceChangeLog(tenant_id=settings.tenant_id, sku_id=sku.id, old_price=old_price, new_price=sku.price,
                              reason=payload.get("reason", "后台调价"), changed_by=actor.get("id")))
    _refresh_price_range(db, sku.product_id)
    audit.record(db, actor, "sku_update", "sku", sku.id, before=before, after=_sku_view(sku))
    db.commit()
    return _sku_view(sku)


SORT_OPTIONS = {
    "price_asc": (Product.min_price.asc(), Product.id.asc()),
    "price_desc": (Product.min_price.desc(), Product.id.desc()),
    "newest": (Product.published_at.desc().nullslast(), Product.id.desc()),
    "default": (Product.sort_order.asc(), Product.id.desc()),
}


def search_products(db: Session, *, keyword: str | None = None, category_id: int | None = None,
                    product_line: str | None = None, product_type: str | None = None, sort: str | None = None,
                    page: int = 1, page_size: int = 20) -> dict:
    """C 端商品检索：仅返回在售商品，附带 SKU 与可售数量，供商城列表与加购使用。"""
    stmt = select(Product).where(Product.tenant_id == settings.tenant_id, Product.status == "ON_SALE")
    if keyword:
        pattern = f"%{keyword}%"
        stmt = stmt.where(or_(Product.name.ilike(pattern), Product.subtitle.ilike(pattern),
                              Product.spu_code.ilike(pattern), Product.model_code.ilike(pattern)))
    if category_id:
        child_ids = list(db.execute(select(Category.id).where(Category.path.like(f"%/{category_id}/%"))).scalars().all())
        stmt = stmt.where(Product.category_id.in_([category_id, *child_ids]))
    if product_line:
        stmt = stmt.where(Product.product_line == product_line)
    if product_type:
        lines = [PRODUCT_TYPE_TO_LINE[product_type]] if product_type in PRODUCT_TYPE_TO_LINE else []
        stmt = stmt.where(Product.product_line.in_(lines)) if lines else stmt.where(Product.id < 0)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    offset, limit = page_offset(page, page_size)
    order_by = SORT_OPTIONS.get(sort or "default", SORT_OPTIONS["default"])
    rows = db.execute(stmt.order_by(*order_by).offset(offset).limit(limit)).scalars().all()
    items = []
    for product in rows:
        view = _product_view(db, product, with_skus=True)
        view["sellable_qty"] = sum(sku.get("sellable_qty", 0) for sku in view.get("skus", []))
        items.append(view)
    return {"page": page, "page_size": page_size, "total": total, "meta": {"page": page, "page_size": page_size, "total": total},
            "items": items}


def list_skus(db: Session, product_id: int) -> dict:
    """SKU 列表（含各仓库存），供后台 SKU 页使用。"""
    get_or_404(db, Product, product_id, "商品不存在")
    rows = db.execute(select(Sku).where(Sku.product_id == product_id)
                      .order_by(Sku.sort_order, Sku.id)).scalars().all()
    items = []
    for sku in rows:
        item = _sku_view(sku)
        inv_rows = db.execute(
            select(Inventory.warehouse_id, Inventory.qty_available, Inventory.qty_reserved)
            .where(Inventory.sku_id == sku.id)
        ).all()
        item["inventory"] = [{"warehouse_id": r[0], "qty_available": r[1], "qty_reserved": r[2],
                              "sellable": r[1] - r[2]} for r in inv_rows]
        item["sellable_qty"] = sum(r[1] - r[2] for r in inv_rows)
        items.append(item)
    return list_payload(items)


def get_public_product(db: Session, product_id: int) -> dict:
    product = db.get(Product, product_id)
    if not product or product.status != "ON_SALE":
        raise NotFound("商品不存在或已下架")
    return _product_view(db, product, with_skus=True)


def list_attribute_definitions(db: Session) -> list[dict]:
    rows = db.execute(select(AttributeDefinition).where(AttributeDefinition.tenant_id == settings.tenant_id).order_by(AttributeDefinition.sort_order)).scalars().all()
    return [{"id": a.id, "code": a.code, "name": a.name, "data_type": a.data_type, "unit": a.unit,
             "is_spec": a.is_spec, "options": a.options} for a in rows]
