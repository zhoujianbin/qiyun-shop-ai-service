from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import require
from app.api.v1.common import actor_of
from app.core.db import get_db
from app.models import AppUser
from app.schemas.views import (
    AfterSalesReportView,
    DashboardView,
    InventoryReportView,
    SalesDailyView,
)
from app.services import report as report_service

router = APIRouter(prefix="/reports", tags=["report"])


@router.get("/dashboard", response_model=DashboardView)
def dashboard(request: Request, days: int = Query(30, ge=1, le=365), channel_account_id: int | None = None,
              db: Session = Depends(get_db), user: AppUser = Depends(require("shop:report:read"))) -> dict:
    actor = actor_of(request, user, db)
    return report_service.dashboard(db, actor, days=days, channel_account_id=channel_account_id)


@router.get("/sales/daily", response_model=SalesDailyView)
def sales_daily(request: Request, days: int = Query(30, ge=1, le=365), channel_account_id: int | None = None,
                db: Session = Depends(get_db), user: AppUser = Depends(require("shop:report:read"))) -> dict:
    actor = actor_of(request, user, db)
    return report_service.sales_daily(db, actor, days=days, channel_account_id=channel_account_id)


@router.get("/inventory", response_model=InventoryReportView)
def inventory_report(request: Request, db: Session = Depends(get_db),
                     user: AppUser = Depends(require("shop:report:read"))) -> dict:
    actor = actor_of(request, user, db)
    return report_service.inventory_report(db, actor)


@router.get("/after-sales", response_model=AfterSalesReportView)
def after_sales_report(request: Request, days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db),
                       user: AppUser = Depends(require("shop:report:read"))) -> dict:
    actor = actor_of(request, user, db)
    return report_service.after_sales_report(db, actor, days=days)
