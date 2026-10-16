from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require
from app.api.v1.common import actor_of
from app.core.db import get_db
from app.models import AppUser
from app.schemas.views import MockSucceedView, PaymentPage, PaymentView
from app.services import payment as payment_service

router = APIRouter(prefix="/payments", tags=["payment"])


class PaymentCreate(BaseModel):
    order_id: int
    method: str = "MOCK"


@router.get("", response_model=PaymentPage)
def list_payments(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                  status: str | None = None, keyword: str | None = None, db: Session = Depends(get_db),
                  user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return payment_service.list_payments(db, actor, page=page, page_size=page_size, status=status, keyword=keyword)


@router.post("", response_model=PaymentView)
def create_payment(payload: PaymentCreate, request: Request, db: Session = Depends(get_db),
                   user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return payment_service.create_payment(db, actor, payload.order_id, payload.method)


@router.get("/{payment_id}", response_model=PaymentView)
def get_payment(payment_id: int, request: Request, db: Session = Depends(get_db),
                user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return payment_service.get_payment(db, actor, payment_id)


@router.post("/{payment_id}/mock-succeed", response_model=MockSucceedView)
def mock_succeed(payment_id: int, request: Request, db: Session = Depends(get_db),
                 user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return payment_service.mock_succeed(db, actor, payment_id)
