"""四期本体接口：实体 / 关系 / 别名 / 审核 / 图遍历 / 切片映射。

权限：读走 ontology:read，写走 ontology:write，审核走 ontology:review。
写接口一律带 Idempotency-Key（由中间件强制），并记 audit_log。
"""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import require
from app.api.v1.common import actor_of
from app.core.db import get_db
from app.models import AppUser
from app.schemas.ontology import (
    AliasPage, AliasUpsert, AliasView, BackfillResult, EntityCreate, EntityPage, EntityUpdate,
    EntityView, GraphView, ImportResult, RelationPage, RelationUpsert, RelationView, RelinkResult,
    ReviewRequest, ReviewResult,
)
from app.services import ontology

router = APIRouter(prefix="/knowledge/ontology", tags=["ontology"])


@router.post("/import", response_model=ImportResult)
def import_rules(request: Request, db: Session = Depends(get_db),
                 user: AppUser = Depends(require("ontology:write"))) -> dict:
    return ontology.import_structured_rules(db, actor_of(request, user, db))


@router.get("/entities", response_model=EntityPage)
def list_entities(kind: str | None = None, status: str | None = None, keyword: str | None = None,
                  page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                  db: Session = Depends(get_db),
                  user: AppUser = Depends(require("ontology:read"))) -> dict:
    return ontology.list_entities(db, kind=kind, status=status, keyword=keyword,
                                  page=page, page_size=page_size)


@router.get("/entities/{entity_id}", response_model=EntityView)
def get_entity(entity_id: int, db: Session = Depends(get_db),
               user: AppUser = Depends(require("ontology:read"))) -> dict:
    return ontology.get_entity(db, entity_id)


@router.post("/entities", response_model=EntityView)
def create_entity(payload: EntityCreate, request: Request, db: Session = Depends(get_db),
                  user: AppUser = Depends(require("ontology:write"))) -> dict:
    return ontology.create_entity(db, actor_of(request, user, db), payload.model_dump())


@router.put("/entities/{entity_id}", response_model=EntityView)
def update_entity(entity_id: int, payload: EntityUpdate, request: Request,
                  db: Session = Depends(get_db),
                  user: AppUser = Depends(require("ontology:write"))) -> dict:
    return ontology.update_entity(db, actor_of(request, user, db), entity_id, payload.model_dump())


@router.get("/relations", response_model=RelationPage)
def list_relations(entity_id: int | None = None, predicate: str | None = None,
                   status: str | None = None, page: int = Query(1, ge=1),
                   page_size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db),
                   user: AppUser = Depends(require("ontology:read"))) -> dict:
    return ontology.list_relations(db, entity_id=entity_id, predicate=predicate, status=status,
                                   page=page, page_size=page_size)


@router.post("/relations", response_model=RelationView)
def upsert_relation(payload: RelationUpsert, request: Request, db: Session = Depends(get_db),
                    user: AppUser = Depends(require("ontology:write"))) -> dict:
    return ontology.upsert_relation(db, actor_of(request, user, db), payload.model_dump())


@router.get("/aliases", response_model=AliasPage)
def list_aliases(entity_id: int | None = None, keyword: str | None = None,
                 page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
                 db: Session = Depends(get_db),
                 user: AppUser = Depends(require("ontology:read"))) -> dict:
    return ontology.list_aliases(db, entity_id=entity_id, keyword=keyword,
                                 page=page, page_size=page_size)


@router.post("/aliases", response_model=AliasView)
def upsert_alias(payload: AliasUpsert, request: Request, db: Session = Depends(get_db),
                 user: AppUser = Depends(require("ontology:write"))) -> dict:
    return ontology.upsert_alias(db, actor_of(request, user, db), payload.model_dump())


@router.post("/review", response_model=ReviewResult)
def review(payload: ReviewRequest, request: Request, db: Session = Depends(get_db),
           user: AppUser = Depends(require("ontology:review"))) -> dict:
    return ontology.review(db, actor_of(request, user, db),
                           entity_ids=payload.entity_ids, action=payload.action)


@router.get("/graph", response_model=GraphView)
def graph(entity_id: int, depth: int = Query(1, ge=1, le=2), db: Session = Depends(get_db),
          user: AppUser = Depends(require("ontology:read"))) -> dict:
    # 图遍历含内部实体编码，客户侧不可见；服务内已把深度上限钳到 2
    return ontology.graph(db, entity_id, depth=depth)


@router.post("/chunks/backfill", response_model=BackfillResult)
def backfill_chunks(request: Request, db: Session = Depends(get_db),
                    user: AppUser = Depends(require("ontology:write"))) -> dict:
    return ontology.backfill_chunk_entities(db, actor_of(request, user, db))


@router.post("/chunks/relink", response_model=RelinkResult)
def relink_chunks(request: Request, db: Session = Depends(get_db),
                  user: AppUser = Depends(require("ontology:write"))) -> dict:
    return ontology.relink_chunks(db, actor_of(request, user, db))
