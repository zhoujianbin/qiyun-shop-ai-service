from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require
from app.api.v1.common import actor_of
from app.core.db import get_db
from app.models import AppUser
from app.schemas.views import (
    AddressView,
    CustomerDetailView,
    CustomerOrderPage,
    CustomerPage,
    CustomerView,
    DeleteResult,
)
from app.services import customer as customer_service

router = APIRouter(tags=["customer"])


class CustomerUpdate(BaseModel):
    nickname: str | None = None
    real_name: str | None = None
    remark: str | None = None
    gender: str | None = None
    birthday: str | None = None
    tags: list[str] | None = None
    default_channel_id: int | None = None


class AddressCreate(BaseModel):
    """收货地址：receiver_mobile 为前端契约字段，receiver_phone 为兼容别名。"""

    receiver_name: str
    receiver_mobile: str | None = None
    receiver_phone: str | None = None
    province: str
    city: str
    district: str
    detail: str
    postal_code: str | None = None
    is_default: bool = False


@router.get("/customers", response_model=CustomerPage)
def list_customers(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), keyword: str | None = None,
                   db: Session = Depends(get_db), user: AppUser = Depends(require("shop:customer:read"))) -> dict:
    return customer_service.list_customers(db, page=page, page_size=page_size, keyword=keyword)


@router.get("/customers/me", response_model=CustomerView)
def my_profile(request: Request, db: Session = Depends(get_db),
               user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return customer_service.get_customer(db, actor["customer_id"])


@router.get("/customers/me/addresses", response_model=list[AddressView])
def my_addresses(request: Request, db: Session = Depends(get_db),
                 user: AppUser = Depends(get_current_user)) -> list[dict]:
    return customer_service.list_addresses(db, user)


@router.post("/customers/me/addresses", response_model=AddressView)
def create_my_address(request: Request, payload: AddressCreate, db: Session = Depends(get_db),
                      user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return customer_service.create_address(db, actor, payload.model_dump(), user=user)


@router.patch("/customers/me/addresses/{address_id}", response_model=AddressView)
def update_my_address(request: Request, address_id: int, payload: AddressCreate,
                      db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return customer_service.update_address(db, actor, address_id, payload.model_dump(exclude_none=True),
                                           customer_ids=[actor["customer_id"]])


@router.delete("/customers/me/addresses/{address_id}", response_model=DeleteResult)
def delete_my_address(request: Request, address_id: int, db: Session = Depends(get_db),
                      user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return customer_service.delete_address(db, actor, address_id, customer_ids=[actor["customer_id"]])


@router.get("/customers/{customer_id}", response_model=CustomerDetailView)
def get_customer(customer_id: int, db: Session = Depends(get_db),
                 user: AppUser = Depends(require("shop:customer:read"))) -> dict:
    return customer_service.get_customer(db, customer_id)


@router.patch("/customers/{customer_id}", response_model=CustomerView)
def update_customer(customer_id: int, payload: CustomerUpdate, db: Session = Depends(get_db),
                    user: AppUser = Depends(require("shop:customer:write"))) -> dict:
    return customer_service.update_customer(db, {"id": user.id, "party": user.party, "label": user.display_name},
                                            customer_id, payload.model_dump(exclude_none=True))


@router.get("/customers/{customer_id}/addresses", response_model=list[AddressView])
def list_addresses(customer_id: int, db: Session = Depends(get_db),
                   user: AppUser = Depends(require("shop:customer:read"))) -> list[dict]:
    return customer_service.get_customer(db, customer_id)["addresses"]


@router.post("/customers/{customer_id}/addresses", response_model=AddressView)
def create_address(customer_id: int, payload: AddressCreate, db: Session = Depends(get_db),
                   user: AppUser = Depends(require("shop:customer:write"))) -> dict:
    return customer_service.create_address(db, {"id": user.id, "party": user.party, "label": user.display_name},
                                           payload.model_dump(), customer_id=customer_id)


@router.patch("/customers/addresses/{address_id}", response_model=AddressView)
def admin_update_address(address_id: int, payload: AddressCreate, db: Session = Depends(get_db),
                         user: AppUser = Depends(require("shop:customer:write"))) -> dict:
    return customer_service.update_address(db, {"id": user.id, "party": user.party, "label": user.display_name},
                                           address_id, payload.model_dump(exclude_none=True))


@router.delete("/customers/addresses/{address_id}", response_model=DeleteResult)
def admin_delete_address(address_id: int, db: Session = Depends(get_db),
                         user: AppUser = Depends(require("shop:customer:write"))) -> dict:
    return customer_service.delete_address(db, {"id": user.id, "party": user.party, "label": user.display_name},
                                           address_id)


@router.get("/customers/{customer_id}/orders", response_model=CustomerOrderPage)
def customer_orders(customer_id: int, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                    db: Session = Depends(get_db), user: AppUser = Depends(require("shop:customer:read"))) -> dict:
    return customer_service.customer_orders(db, customer_id, page=page, page_size=page_size)
