from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require
from app.core.db import get_db
from app.models import AppUser
from app.schemas.views import (
    InventoryAlertPage,
    InventoryAlertView,
    InventoryPage,
    LedgerPage,
    StockAdjustResult,
    WarehousePage,
    WarehouseView,
)
from app.services import inventory as inventory_service

router = APIRouter(tags=["inventory"])


class WarehouseCreate(BaseModel):
    code: str
    name: str
    region: str | None = None
    address: str | None = None
    priority: int = 100
    type: str | None = None
    contact_name: str | None = None
    contact_mobile: str | None = None


class StockAdjust(BaseModel):
    sku_id: int
    warehouse_id: int
    change_type: str
    qty_delta: int
    reason: str | None = None
    remark: str | None = None
    safety_stock: int | None = None
    version: int | None = None
    expected_version: int | None = None


@router.get("/warehouses", response_model=WarehousePage)
def list_warehouses(db: Session = Depends(get_db),
                    user: AppUser = Depends(require("shop:inventory:read"))) -> list[dict]:
    return inventory_service.list_warehouses(db)


@router.post("/warehouses", response_model=WarehouseView)
def create_warehouse(payload: WarehouseCreate, db: Session = Depends(get_db),
                     user: AppUser = Depends(require("shop:inventory:write"))) -> dict:
    return inventory_service.create_warehouse(db, {"id": user.id, "party": user.party, "label": user.display_name},
                                              payload.model_dump())


@router.get("/inventory", response_model=InventoryPage)
def list_inventory(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), keyword: str | None = None,
                   warehouse_id: int | None = None, low_stock_only: bool = False, db: Session = Depends(get_db),
                   user: AppUser = Depends(require("shop:inventory:read"))) -> dict:
    return inventory_service.list_inventory(db, page=page, page_size=page_size, keyword=keyword,
                                            warehouse_id=warehouse_id, low_stock_only=low_stock_only)


@router.post("/inventory/adjust", response_model=StockAdjustResult)
def adjust_inventory(payload: StockAdjust, db: Session = Depends(get_db),
                     user: AppUser = Depends(require("shop:inventory:write"))) -> dict:
    return inventory_service.adjust(db, {"id": user.id, "party": user.party, "label": user.display_name},
                                    payload.model_dump())


@router.get("/inventory/ledger", response_model=LedgerPage)
def list_ledger(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), sku_id: int | None = None,
                warehouse_id: int | None = None, change_type: str | None = None, db: Session = Depends(get_db),
                user: AppUser = Depends(require("shop:inventory:read"))) -> dict:
    return inventory_service.list_ledger(db, page=page, page_size=page_size, sku_id=sku_id,
                                         warehouse_id=warehouse_id, change_type=change_type)


@router.get("/inventory/alerts", response_model=InventoryAlertPage)
def inventory_alerts(db: Session = Depends(get_db),
                     user: AppUser = Depends(require("shop:inventory:read"))) -> list[dict]:
    return inventory_service.alerts(db)
