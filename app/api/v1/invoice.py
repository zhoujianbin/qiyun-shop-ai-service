from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require
from app.api.v1.common import actor_of
from app.core.db import get_db
from app.models import AppUser
from app.schemas.views import InvoicePage, InvoiceView
from app.services import invoice as invoice_service

router = APIRouter(prefix="/invoices", tags=["invoice"])


class InvoiceCreate(BaseModel):
    order_id: int
    type: str = "ELECTRONIC"
    title_type: str | None = None
    title: str
    tax_no: str | None = None
    content: str | None = None
    amount: float | None = None
    bank_name: str | None = None
    bank_account: str | None = None
    registered_address: str | None = None
    registered_phone: str | None = None
    email: str | None = None
    remark: str | None = None


class InvoiceIssue(BaseModel):
    invoice_no: str | None = None
    file_url: str | None = None
    issue_type: str | None = None
    tax_amount: float | None = None
    attachment_id: int | None = None
    issued_at: str | None = None


class InvoiceVoid(BaseModel):
    reason: str | None = None
    issue_type: str | None = None


@router.get("", response_model=InvoicePage)
def list_invoices(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                  status: str | None = None, db: Session = Depends(get_db),
                  user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return invoice_service.list_invoices(db, actor, page=page, page_size=page_size, status=status)


@router.post("", response_model=InvoiceView)
def apply_invoice(payload: InvoiceCreate, request: Request, db: Session = Depends(get_db),
                  user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return invoice_service.apply(db, actor, payload.model_dump())


@router.get("/{invoice_id}", response_model=InvoiceView)
def get_invoice(invoice_id: int, request: Request, db: Session = Depends(get_db),
                user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return invoice_service.get_invoice(db, actor, invoice_id)


@router.post("/{invoice_id}/issue", response_model=InvoiceView)
def issue_invoice(invoice_id: int, payload: InvoiceIssue, request: Request, db: Session = Depends(get_db),
                  user: AppUser = Depends(require("shop:invoice:write"))) -> dict:
    actor = actor_of(request, user, db)
    return invoice_service.issue(db, actor, invoice_id, payload.model_dump())


@router.post("/{invoice_id}/void", response_model=InvoiceView)
def void_invoice(invoice_id: int, payload: InvoiceVoid, request: Request, db: Session = Depends(get_db),
                 user: AppUser = Depends(require("shop:invoice:write"))) -> dict:
    actor = actor_of(request, user, db)
    return invoice_service.void(db, actor, invoice_id, payload.reason)
