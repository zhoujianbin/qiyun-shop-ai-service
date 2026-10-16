from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require
from app.api.v1.common import actor_of
from app.core.db import get_db
from app.models import AppUser
from app.schemas.views import CarrierPage, CarrierView, ShipmentDetailView, ShipmentPage
from app.services import fulfillment as fulfillment_service

router = APIRouter(tags=["fulfillment"])


class TrackingEventCreate(BaseModel):
    status: str
    description: str
    location: str | None = None
    event_time: str | None = None


@router.get("/carriers", response_model=CarrierPage)
def list_carriers(db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)) -> list[dict]:
    return fulfillment_service.list_carriers(db)


@router.get("/shipments", response_model=ShipmentPage)
def list_shipments(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                   status: str | None = None, keyword: str | None = None, db: Session = Depends(get_db),
                   user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return fulfillment_service.list_shipments(db, actor, page=page, page_size=page_size, status=status, keyword=keyword)


@router.get("/shipments/{shipment_id}", response_model=ShipmentDetailView)
def get_shipment(shipment_id: int, request: Request, db: Session = Depends(get_db),
                 user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    return fulfillment_service.get_shipment(db, actor, shipment_id)


@router.post("/shipments/{shipment_id}/tracking-events", response_model=ShipmentDetailView)
def add_tracking_event(shipment_id: int, payload: TrackingEventCreate, request: Request,
                       db: Session = Depends(get_db),
                       user: AppUser = Depends(require("shop:fulfillment:write"))) -> dict:
    actor = actor_of(request, user, db)
    return fulfillment_service.add_tracking_event(db, actor, shipment_id, payload.model_dump())
