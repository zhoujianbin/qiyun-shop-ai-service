from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require
from app.api.v1.common import actor_of
from app.core.db import get_db
from app.models import AppUser
from app.schemas.views import (RefundAttemptPage, RefundDetailView, RefundPage, RefundView)
from app.services import refund as refund_service

router = APIRouter(prefix="/refunds", tags=["refund"])


class RefundCreate(BaseModel):
    order_id: int
    amount: float = Field(gt=0)
    method: str | None = None
    channel: str | None = None
    reason: str | None = None
    application_id: int | None = None
    after_sales_id: int | None = None
    order_item_id: int | None = None


@router.get("", response_model=RefundPage)
def list_refunds(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                 status: str | None = None, keyword: str | None = None, db: Session = Depends(get_db),
                 user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    if user.party == "STAFF":
        from app.api.deps import request_permissions

        if "shop:refund:read" not in request_permissions(request, db, user):
            from app.core.errors import Forbidden

            raise Forbidden("缺少权限：shop:refund:read")
    return refund_service.list_refunds(db, actor, page=page, page_size=page_size, status=status, keyword=keyword)


@router.post("", response_model=RefundView)
def create_refund(payload: RefundCreate, request: Request, db: Session = Depends(get_db),
                  user: AppUser = Depends(require("shop:refund:write"))) -> dict:
    actor = actor_of(request, user, db)
    return refund_service.create(db, actor, payload.model_dump())


@router.get("/{refund_id}", response_model=RefundDetailView)
def get_refund(refund_id: int, request: Request, db: Session = Depends(get_db),
               user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return refund_service.get_refund(db, actor, refund_id)


@router.get("/{refund_id}/attempts", response_model=RefundAttemptPage)
def refund_attempts(refund_id: int, request: Request, db: Session = Depends(get_db),
                    user: AppUser = Depends(require("shop:refund:read"))) -> dict:
    actor = actor_of(request, user, db)
    return refund_service.list_attempts(db, actor, refund_id)


@router.post("/{refund_id}/execute", response_model=RefundView)
def execute_refund(refund_id: int, request: Request, db: Session = Depends(get_db),
                   user: AppUser = Depends(require("shop:refund:write"))) -> dict:
    actor = actor_of(request, user, db)
    return refund_service.execute(db, actor, refund_id)
