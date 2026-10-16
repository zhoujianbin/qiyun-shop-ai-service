from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import AppUser
from app.schemas.views import CartView
from app.services import cart as cart_service

router = APIRouter(prefix="/cart", tags=["cart"])


class CartItemCreate(BaseModel):
    """加购：channel_account_id 可选，缺省使用官方商城。"""

    sku_id: int
    quantity: int = Field(gt=0, le=999)
    channel_account_id: int | None = None


class CartItemUpdate(BaseModel):
    quantity: int | None = Field(default=None, gt=0, le=999)
    selected: bool | None = None


@router.get("", response_model=CartView)
def get_cart(channel_account_id: int | None = Query(None), db: Session = Depends(get_db),
             user: AppUser = Depends(get_current_user)) -> dict:
    """购物车：channel_account_id 可选，缺省使用官方商城（与前端加购默认一致）。"""
    return cart_service.get_cart(db, user, channel_account_id)


@router.post("/items", response_model=CartView)
def add_item(payload: CartItemCreate, db: Session = Depends(get_db),
             user: AppUser = Depends(get_current_user)) -> dict:
    return cart_service.add_item(db, user, payload.model_dump())


@router.patch("/items/{item_id}", response_model=CartView)
def update_item(item_id: int, payload: CartItemUpdate, db: Session = Depends(get_db),
                user: AppUser = Depends(get_current_user)) -> dict:
    return cart_service.update_item(db, user, item_id, payload.model_dump(exclude_none=True))


@router.delete("/items/{item_id}", response_model=CartView)
def remove_item(item_id: int, db: Session = Depends(get_db),
                user: AppUser = Depends(get_current_user)) -> dict:
    return cart_service.remove_item(db, user, item_id)
