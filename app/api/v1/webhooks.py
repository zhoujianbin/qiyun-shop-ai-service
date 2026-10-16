from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services import fulfillment as fulfillment_service
from app.services import payment as payment_service
from app.services import refund as refund_service

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class PaymentCallback(BaseModel):
    event_id: str
    payment_no: str
    amount: float
    channel_txn_no: str | None = None
    paid_at: str | None = None
    signature: str | None = None


class RefundCallback(BaseModel):
    refund_no: str
    status: str
    error_code: str | None = None
    error_message: str | None = None


class LogisticsCallback(BaseModel):
    shipment_no: str
    status: str
    description: str | None = None
    location: str | None = None
    event_time: str | None = None


@router.post("/payment/{channel}")
def payment_callback(channel: str, payload: PaymentCallback, db: Session = Depends(get_db)) -> dict:
    return payment_service.handle_callback(db, channel, payload.model_dump())


@router.post("/refund/{channel}")
def refund_callback(channel: str, payload: RefundCallback, db: Session = Depends(get_db)) -> dict:
    return refund_service.handle_callback(db, payload.model_dump())


@router.post("/logistics/{carrier}")
def logistics_callback(carrier: str, payload: LogisticsCallback, db: Session = Depends(get_db)) -> dict:
    return fulfillment_service.logistics_callback(db, payload.model_dump())
