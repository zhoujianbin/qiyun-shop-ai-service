from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require
from app.api.v1.common import actor_of
from app.core.db import get_db
from app.models import AppUser
from app.schemas.views import (
    OrderDetailView,
    OrderPage,
    OrderTimelineView,
    OrderView,
    ShipmentDetailView,
)
from app.services import fulfillment as fulfillment_service
from app.services import order as order_service

router = APIRouter(prefix="/orders", tags=["order"])


class OrderItemInput(BaseModel):
    sku_id: int
    quantity: int = Field(gt=0, le=999)


class OrderCreate(BaseModel):
    """下单：items 直购或 cart_item_ids 购物车结算（source_mode=CART）。"""

    items: list[OrderItemInput] | None = None
    cart_item_ids: list[int] | None = None
    source_mode: str | None = "CART"
    channel_account_id: int | None = None
    coupon_code: str | None = None
    expected_delivery_time: str | None = None
    address_id: int | None = None
    receiver_name: str | None = None
    receiver_phone: str | None = None
    province: str | None = None
    city: str | None = None
    district: str | None = None
    detail: str | None = None
    buyer_remark: str | None = None
    source: str = "OFFICIAL_MALL"
    payment_method: str = "MOCK"


class CancelRequest(BaseModel):
    reason: str | None = None
    notify_customer: bool | None = None


class AddressUpdate(BaseModel):
    address_id: int | None = None
    receiver_name: str | None = None
    receiver_mobile: str | None = None
    receiver_phone: str | None = None
    province: str | None = None
    city: str | None = None
    district: str | None = None
    detail: str | None = None


class RemarkUpdate(BaseModel):
    buyer_remark: str | None = None
    staff_remark: str | None = None


class ShipItem(BaseModel):
    order_item_id: int
    quantity: int = Field(gt=0)


class ShipRequest(BaseModel):
    """发货：carrier_code 为前端契约字段，carrier_id 为兼容别名。"""

    carrier_id: int | None = None
    carrier_code: str | None = None
    tracking_no: str
    warehouse_id: int | None = None
    package_count: int = 1
    shipped_at: str | None = None
    remark: str | None = None
    items: list[ShipItem]


@router.post("", response_model=OrderDetailView)
def create_order(request: Request, payload: OrderCreate, db: Session = Depends(get_db),
                 user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    data = payload.model_dump()
    data["items"] = [i.model_dump() if hasattr(i, "model_dump") else i for i in payload.items or []]
    if not data.get("channel_account_id"):
        from app.services.cart import default_channel_id

        data["channel_account_id"] = default_channel_id(db)
    return order_service.create_order(db, actor, data)


@router.get("", response_model=OrderPage)
def list_orders(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                status: str | None = None, payment_status: str | None = None, fulfillment_status: str | None = None,
                keyword: str | None = None, channel_account_id: int | None = None, db: Session = Depends(get_db),
                user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    if user.party == "STAFF":
        from app.api.deps import request_permissions

        perms = request_permissions(request, db, user)
        if "shop:order:read" not in perms:
            from app.core.errors import Forbidden

            raise Forbidden("缺少权限：shop:order:read")
    return order_service.list_orders(db, actor, page=page, page_size=page_size, status=status,
                                     payment_status=payment_status, fulfillment_status=fulfillment_status,
                                     keyword=keyword, channel_account_id=channel_account_id)


@router.get("/{order_id}", response_model=OrderDetailView)
def get_order(order_id: int, request: Request, db: Session = Depends(get_db),
              user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return order_service.get_order(db, actor, order_id)


@router.get("/{order_id}/timeline", response_model=OrderTimelineView)
def order_timeline(order_id: int, request: Request, db: Session = Depends(get_db),
                   user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return order_service.timeline(db, actor, order_id)


@router.post("/{order_id}/cancel", response_model=OrderDetailView)
def cancel_order(order_id: int, payload: CancelRequest, request: Request, db: Session = Depends(get_db),
                 user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return order_service.cancel(db, actor, order_id, payload.reason)


@router.post("/{order_id}/confirm-receipt", response_model=OrderDetailView)
def confirm_receipt(order_id: int, request: Request, db: Session = Depends(get_db),
                    user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return order_service.confirm_receipt(db, actor, order_id)


@router.patch("/{order_id}/address", response_model=OrderDetailView)
def update_address(order_id: int, payload: AddressUpdate, request: Request, db: Session = Depends(get_db),
                   user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return order_service.update_address(db, actor, order_id, payload.model_dump(exclude_none=True))


@router.patch("/{order_id}/remark", response_model=OrderView)
def update_remark(order_id: int, payload: RemarkUpdate, request: Request, db: Session = Depends(get_db),
                  user: AppUser = Depends(require("shop:order:write"))) -> dict:
    actor = actor_of(request, user, db)
    return order_service.set_remark(db, actor, order_id, payload.model_dump(exclude_none=True))


@router.post("/{order_id}/ship", response_model=ShipmentDetailView)
def ship_order(order_id: int, payload: ShipRequest, request: Request, db: Session = Depends(get_db),
               user: AppUser = Depends(require("shop:fulfillment:write"))) -> dict:
    actor = actor_of(request, user, db)
    data = payload.model_dump()
    data["items"] = [i.model_dump() if hasattr(i, "model_dump") else i for i in payload.items]
    return fulfillment_service.ship(db, actor, order_id, data)
