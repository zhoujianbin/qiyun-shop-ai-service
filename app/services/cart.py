from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import NotFound, ValidationError
from app.models import AppUser, Cart, CartItem, Inventory, Product, Sku
from app.services.common import get_or_404, money
from app.services.customer import profile_of


def default_channel_id(db: Session) -> int:
    """默认渠道：优先官方商城，其次任一启用渠道。用于前端未显式传渠道的场景。"""
    from app.models import ChannelAccount

    row = db.execute(select(ChannelAccount).where(ChannelAccount.tenant_id == settings.tenant_id,
                                                  ChannelAccount.status == "ACTIVE",
                                                  ChannelAccount.code == "OFFICIAL_MALL")).scalars().first()
    if row is None:
        row = db.execute(select(ChannelAccount).where(ChannelAccount.tenant_id == settings.tenant_id,
                                                     ChannelAccount.status == "ACTIVE")
                         .order_by(ChannelAccount.id)).scalars().first()
    if row is None:
        raise NotFound("没有可用的渠道账号")
    return row.id


def _get_or_create(db: Session, customer_id: int, channel_account_id: int) -> Cart:
    cart = db.execute(select(Cart).where(Cart.customer_id == customer_id, Cart.channel_account_id == channel_account_id,
                                        Cart.status == "OPEN")).scalar_one_or_none()
    if cart is None:
        cart = Cart(tenant_id=settings.tenant_id, customer_id=customer_id, channel_account_id=channel_account_id, status="OPEN")
        db.add(cart)
        db.commit()
    return cart


def _view(db: Session, cart: Cart) -> dict:
    items = db.execute(select(CartItem).where(CartItem.cart_id == cart.id).order_by(CartItem.id)).scalars().all()
    result, total_amount = [], 0
    for item in items:
        sku = db.get(Sku, item.sku_id)
        product = db.get(Product, sku.product_id) if sku else None
        sellable = int(db.execute(
            select(func.coalesce(func.sum(Inventory.qty_available - Inventory.qty_reserved), 0))
            .where(Inventory.sku_id == item.sku_id)
        ).scalar_one())
        amount = (sku.price or 0) * item.quantity
        total_amount += amount
        result.append({"id": item.id, "cart_id": cart.id, "sku_id": item.sku_id, "quantity": item.quantity,
                       "selected": item.selected,
                       "sku_code": sku.sku_code if sku else None, "sku_name": sku.name if sku else None,
                       "product_id": product.id if product else None, "product_name": product.name if product else None,
                       "image_url": None, "unit_price": money(sku.price) if sku else None, "amount": money(amount),
                       "sellable_qty": sellable, "stock_available": sellable >= item.quantity,
                       "available": sellable >= item.quantity,
                       "added_at": item.added_at.isoformat() if item.added_at else None,
                       "updated_at": item.updated_at.isoformat() if item.updated_at else None})
    return {"id": cart.id, "customer_id": cart.customer_id, "channel_account_id": cart.channel_account_id,
            "status": cart.status, "items": result, "item_count": len(result),
            "selected_quantity": sum(item["quantity"] for item in result if item.get("selected")),
            "total_amount": money(total_amount),
            "updated_at": cart.updated_at.isoformat() if cart.updated_at else None}


def get_cart(db: Session, user: AppUser, channel_account_id: int | None = None) -> dict:
    profile = profile_of(db, user)
    cart = _get_or_create(db, profile.id, channel_account_id or default_channel_id(db))
    return _view(db, cart)


def add_item(db: Session, user: AppUser, payload: dict) -> dict:
    profile = profile_of(db, user)
    cart = _get_or_create(db, profile.id, payload.get("channel_account_id") or default_channel_id(db))
    sku = get_or_404(db, Sku, payload["sku_id"], "SKU 不存在")
    product = db.get(Product, sku.product_id)
    if sku.status != "ON_SALE" or product is None or product.status != "ON_SALE":
        raise ValidationError("该 SKU 当前不可购买")
    quantity = int(payload["quantity"])
    if quantity < 1 or quantity > 999:
        raise ValidationError("购买数量需在 1 到 999 之间")
    item = db.execute(select(CartItem).where(CartItem.cart_id == cart.id, CartItem.sku_id == sku.id)).scalar_one_or_none()
    if item:
        item.quantity = min(item.quantity + quantity, 999)
    else:
        db.add(CartItem(tenant_id=settings.tenant_id, cart_id=cart.id, sku_id=sku.id, quantity=quantity))
    db.commit()
    return _view(db, cart)


def update_item(db: Session, user: AppUser, item_id: int, payload: dict) -> dict:
    profile = profile_of(db, user)
    item = get_or_404(db, CartItem, item_id, "购物车条目不存在")
    cart = get_or_404(db, Cart, item.cart_id)
    if cart.customer_id != profile.id:
        raise NotFound("购物车条目不存在")
    if payload.get("quantity") is not None:
        quantity = int(payload["quantity"])
        if quantity < 1 or quantity > 999:
            raise ValidationError("购买数量需在 1 到 999 之间")
        item.quantity = quantity
    if payload.get("selected") is not None:
        item.selected = bool(payload["selected"])
    db.commit()
    return _view(db, cart)


def remove_item(db: Session, user: AppUser, item_id: int) -> dict:
    profile = profile_of(db, user)
    item = get_or_404(db, CartItem, item_id, "购物车条目不存在")
    cart = get_or_404(db, Cart, item.cart_id)
    if cart.customer_id != profile.id:
        raise NotFound("购物车条目不存在")
    db.delete(item)
    db.commit()
    return _view(db, cart)
