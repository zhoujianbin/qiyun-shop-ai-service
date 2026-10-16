from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require
from app.api.v1.common import actor_of
from app.core.db import get_db
from app.models import AppUser
from app.schemas.views import (
    AttributeDefinitionView,
    BrandPage,
    BrandView,
    CategoryView,
    ProductDetailView,
    ProductPage,
    SearchProductPage,
    SkuPage,
    SkuView,
)
from app.services import catalog as catalog_service

router = APIRouter(tags=["catalog"])


class BrandCreate(BaseModel):
    code: str
    name: str
    logo_url: str | None = None
    sort_order: int = 0


class CategoryCreate(BaseModel):
    code: str
    name: str
    parent_id: int | None = None
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = None
    sort_order: int | None = None
    icon_url: str | None = None
    status: str | None = None


class ProductCreate(BaseModel):
    spu_code: str
    name: str
    category_id: int
    brand_id: int | None = None
    product_line: str | None = None
    model_code: str | None = None
    subtitle: str | None = None
    description_md: str | None = None
    highlights: list[str] = []
    spec_summary: dict = {}
    warranty_summary: str | None = None
    install_required: bool = False
    install_notes: str | None = None
    service_scope: str | None = None


class ProductUpdate(BaseModel):
    name: str | None = None
    brand_id: int | None = None
    category_id: int | None = None
    product_line: str | None = None
    model_code: str | None = None
    subtitle: str | None = None
    description_md: str | None = None
    highlights: list[str] | None = None
    spec_summary: dict | None = None
    warranty_summary: str | None = None
    install_required: bool | None = None
    install_notes: str | None = None
    service_scope: str | None = None
    sort_order: int | None = None


class SkuCreate(BaseModel):
    sku_code: str
    name: str
    price: float = Field(gt=0)
    market_price: float | None = None
    cost_price: float | None = None
    spec_summary: str | None = None
    barcode: str | None = None
    weight_g: int | None = None
    status: str = "ON_SALE"
    sort_order: int = 0


class SkuUpdate(BaseModel):
    name: str | None = None
    spec_summary: str | None = None
    price: float | None = Field(default=None, gt=0)
    market_price: float | None = None
    cost_price: float | None = None
    barcode: str | None = None
    weight_g: int | None = None
    status: str | None = None
    sort_order: int | None = None
    reason: str | None = None


@router.get("/brands", response_model=BrandPage)
def list_brands(db: Session = Depends(get_db), user: AppUser = Depends(require("shop:product:read"))) -> list[dict]:
    return catalog_service.list_brands(db)


@router.post("/brands", response_model=BrandView)
def create_brand(payload: BrandCreate, db: Session = Depends(get_db),
                 user: AppUser = Depends(require("shop:product:write"))) -> dict:
    return catalog_service.create_brand(db, {"id": user.id, "party": user.party, "label": user.display_name},
                                        payload.model_dump())


@router.get("/categories", response_model=list[CategoryView])
def list_categories(db: Session = Depends(get_db), user: AppUser = Depends(require("shop:category:read"))) -> list[dict]:
    return catalog_service.list_categories(db)


@router.post("/categories", response_model=CategoryView)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db),
                    user: AppUser = Depends(require("shop:category:write"))) -> dict:
    return catalog_service.create_category(db, {"id": user.id, "party": user.party, "label": user.display_name},
                                           payload.model_dump())


@router.patch("/categories/{category_id}", response_model=CategoryView)
def update_category(category_id: int, payload: CategoryUpdate, db: Session = Depends(get_db),
                    user: AppUser = Depends(require("shop:category:write"))) -> dict:
    return catalog_service.update_category(db, {"id": user.id, "party": user.party, "label": user.display_name},
                                           category_id, payload.model_dump(exclude_none=True))


@router.get("/products", response_model=ProductPage)
def list_products(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), keyword: str | None = None,
                  category_id: int | None = None, status: str | None = None, product_type: str | None = None,
                  product_line: str | None = None, db: Session = Depends(get_db),
                  user: AppUser = Depends(require("shop:product:read"))) -> dict:
    return catalog_service.list_products(db, {}, page=page, page_size=page_size, keyword=keyword,
                                         category_id=category_id, status=status,
                                         product_type=product_type or None)


@router.post("/products", response_model=ProductDetailView)
def create_product(payload: ProductCreate, db: Session = Depends(get_db),
                   user: AppUser = Depends(require("shop:product:write"))) -> dict:
    return catalog_service.create_product(db, {"id": user.id, "party": user.party, "label": user.display_name},
                                          payload.model_dump())


@router.get("/products/search", response_model=SearchProductPage)
def search_products(q: str | None = None, keyword: str | None = None, category_id: int | None = None,
                    product_line: str | None = None, product_type: str | None = None, sort: str | None = None,
                    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                    db: Session = Depends(get_db)) -> dict:
    """C 端商品列表：公开访问，只返回在售商品，包含 SKU 与可售数量。"""
    return catalog_service.search_products(db, keyword=keyword or q, category_id=category_id,
                                           product_line=product_line, product_type=product_type, sort=sort,
                                           page=page, page_size=page_size)


@router.get("/products/{product_id}", response_model=ProductDetailView)
def get_product(product_id: int, db: Session = Depends(get_db),
                user: AppUser = Depends(require("shop:product:read"))) -> dict:
    return catalog_service.get_product(db, product_id)


@router.get("/products/{product_id}/public", response_model=ProductDetailView)
def get_public_product(product_id: int, db: Session = Depends(get_db)) -> dict:
    return catalog_service.get_public_product(db, product_id)


@router.patch("/products/{product_id}", response_model=ProductDetailView)
def update_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db),
                   user: AppUser = Depends(require("shop:product:write"))) -> dict:
    return catalog_service.update_product(db, {"id": user.id, "party": user.party, "label": user.display_name},
                                          product_id, payload.model_dump(exclude_none=True))


@router.post("/products/{product_id}/publish", response_model=ProductDetailView)
def publish_product(product_id: int, db: Session = Depends(get_db),
                    user: AppUser = Depends(require("shop:product:write"))) -> dict:
    return catalog_service.set_product_status(db, {"id": user.id, "party": user.party, "label": user.display_name},
                                              product_id, "ON_SALE")


@router.post("/products/{product_id}/unpublish", response_model=ProductDetailView)
def unpublish_product(product_id: int, db: Session = Depends(get_db),
                      user: AppUser = Depends(require("shop:product:write"))) -> dict:
    return catalog_service.set_product_status(db, {"id": user.id, "party": user.party, "label": user.display_name},
                                              product_id, "OFF_SHELF")


@router.get("/products/{product_id}/skus", response_model=SkuPage)
def list_skus(product_id: int, db: Session = Depends(get_db),
              user: AppUser = Depends(require("shop:product:read"))) -> dict:
    return catalog_service.list_skus(db, product_id)


@router.post("/products/{product_id}/skus", response_model=SkuView)
def create_sku(product_id: int, payload: SkuCreate, db: Session = Depends(get_db),
               user: AppUser = Depends(require("shop:product:write"))) -> dict:
    return catalog_service.create_sku(db, {"id": user.id, "party": user.party, "label": user.display_name},
                                      product_id, payload.model_dump())


@router.patch("/skus/{sku_id}", response_model=SkuView)
def update_sku(sku_id: int, payload: SkuUpdate, db: Session = Depends(get_db),
               user: AppUser = Depends(require("shop:product:write"))) -> dict:
    return catalog_service.update_sku(db, {"id": user.id, "party": user.party, "label": user.display_name},
                                      sku_id, payload.model_dump(exclude_none=True))


@router.get("/attributes", response_model=list[AttributeDefinitionView])
def list_attributes(db: Session = Depends(get_db),
                    user: AppUser = Depends(require("shop:product:read"))) -> list[dict]:
    return catalog_service.list_attribute_definitions(db)
