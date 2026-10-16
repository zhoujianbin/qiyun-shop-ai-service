from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require
from app.api.v1.common import actor_of
from app.core.db import get_db
from app.models import AppUser
from app.schemas.views import AfterSalesDetailView, AfterSalesPage
from app.services import aftersales as aftersales_service

router = APIRouter(prefix="/after-sales/applications", tags=["aftersales"])


class ApplicationItem(BaseModel):
    order_item_id: int
    quantity: int = Field(default=1, gt=0)


class ApplicationCreate(BaseModel):
    """售后申请：兼容 evidence/evidence_attachment_ids、items/order_item_id+quantity、expect_amount/refund_amount。"""

    order_id: int
    type: str
    reason_code: str
    reason_text: str | None = None
    description: str | None = None
    evidence: list = []
    evidence_attachment_ids: list[int] | None = None
    expect_amount: float | None = None
    refund_amount: float | None = None
    order_item_id: int | None = None
    quantity: int | None = None
    items: list[ApplicationItem] = []


class ReviewRequest(BaseModel):
    decision: str
    approved_amount: float | None = None
    need_return: bool | None = None
    review_note: str | None = None
    reason: str | None = None
    remark: str | None = None
    return_address: str | None = None
    assignee_id: int | None = None


class ReturnShipmentRequest(BaseModel):
    carrier_id: int | None = None
    carrier_code: str | None = None
    tracking_no: str
    shipped_at: str | None = None
    remark: str | None = None


class ReceiveRequest(BaseModel):
    restock: bool | None = None
    received: bool | None = None
    warehouse_id: int | None = None
    remark: str | None = None


class CompleteRequest(BaseModel):
    method: str = "ORIGINAL"
    conclusion: str | None = None
    refund_amount: float | None = None
    remark: str | None = None


class CancelRequest(BaseModel):
    reason: str | None = None


class MessageRequest(BaseModel):
    content: str
    attachments: list = []
    attachment_ids: list[int] | None = None
    visible_to_customer: bool = True


@router.post("", response_model=AfterSalesDetailView)
def create_application(payload: ApplicationCreate, request: Request, db: Session = Depends(get_db),
                       user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    data = payload.model_dump()
    data["items"] = [i.model_dump() if hasattr(i, "model_dump") else i for i in payload.items]
    return aftersales_service.create(db, actor, data)


@router.get("", response_model=AfterSalesPage)
def list_applications(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                      status: str | None = None, type: str | None = None, keyword: str | None = None,
                      db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return aftersales_service.list_applications(db, actor, page=page, page_size=page_size, status=status,
                                                type_=type, keyword=keyword)


@router.get("/{application_id}", response_model=AfterSalesDetailView)
def get_application(application_id: int, request: Request, db: Session = Depends(get_db),
                    user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return aftersales_service.get_application(db, actor, application_id)


@router.post("/{application_id}/review", response_model=AfterSalesDetailView)
def review(application_id: int, payload: ReviewRequest, request: Request, db: Session = Depends(get_db),
           user: AppUser = Depends(require("shop:aftersales:review"))) -> dict:
    actor = actor_of(request, user, db)
    return aftersales_service.review(db, actor, application_id, payload.model_dump())


@router.post("/{application_id}/return-shipment", response_model=AfterSalesDetailView)
def return_shipment(application_id: int, payload: ReturnShipmentRequest, request: Request,
                    db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return aftersales_service.return_shipment(db, actor, application_id, payload.model_dump())


@router.post("/{application_id}/receive", response_model=AfterSalesDetailView)
def receive(application_id: int, payload: ReceiveRequest, request: Request, db: Session = Depends(get_db),
            user: AppUser = Depends(require("shop:aftersales:review"))) -> dict:
    actor = actor_of(request, user, db)
    return aftersales_service.receive(db, actor, application_id, payload.model_dump())


@router.post("/{application_id}/complete", response_model=AfterSalesDetailView)
def complete(application_id: int, payload: CompleteRequest, request: Request, db: Session = Depends(get_db),
             user: AppUser = Depends(require("shop:aftersales:review"))) -> dict:
    actor = actor_of(request, user, db)
    return aftersales_service.complete(db, actor, application_id, payload.model_dump())


@router.post("/{application_id}/cancel", response_model=AfterSalesDetailView)
def cancel(application_id: int, payload: CancelRequest, request: Request, db: Session = Depends(get_db),
           user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return aftersales_service.cancel(db, actor, application_id, payload.reason)


@router.post("/{application_id}/messages", response_model=AfterSalesDetailView)
def add_message(application_id: int, payload: MessageRequest, request: Request, db: Session = Depends(get_db),
                user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return aftersales_service.add_message(db, actor, application_id, payload.model_dump())
