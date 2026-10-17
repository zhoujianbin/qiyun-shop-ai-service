"""知识库接口：导入、规则、版本发布、审核。"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import require
from app.api.v1.common import actor_of
from app.core.db import get_db
from app.core.errors import ValidationError
from app.models import AppUser
from app.schemas.knowledge import (
    ChunkPreviewItem, ChunkPreviewRequest, DocumentPage, DocumentView, ImportJobView, PublishRequest,
    PublishResult, RetrievalRequest, RetrievalResult, ReviewCommentCreate, ReviewCommentView,
    ReviewDecideRequest, ReviewTaskView, RuleConflictView, RuleCreate, RuleImportResult, RuleUpdate,
    RuleView, VersionBase,
)
from app.services import (
    knowledge_governance, knowledge_import, knowledge_retrieval, knowledge_review, knowledge_rule,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _parse_effective(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"effective_from 不是合法时间：{value}") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------- 导入
@router.post("/import/jobs", response_model=ImportJobView)
async def create_import_job(
    request: Request,
    files: list[UploadFile] = File(..., description="一次可传多个文件"),
    db: Session = Depends(get_db),
    user: AppUser = Depends(require("knowledge:document:import")),
) -> dict:
    actor = actor_of(request, user, db)
    payloads = [(upload.filename or "upload", upload.content_type, await upload.read()) for upload in files]
    return knowledge_import.create_job(db, actor, payloads,
                                       idempotency_key=request.headers.get("Idempotency-Key"))


@router.get("/import/jobs/{job_id}", response_model=ImportJobView)
def get_import_job(job_id: int, db: Session = Depends(get_db),
                   user: AppUser = Depends(require("knowledge:document:import"))) -> dict:
    return knowledge_import.get_job(db, job_id)


@router.post("/preview-chunks", response_model=list[ChunkPreviewItem])
def preview_chunks(payload: ChunkPreviewRequest, db: Session = Depends(get_db),
                   user: AppUser = Depends(require("knowledge:document:write"))) -> list[dict]:
    return knowledge_import.preview_chunks(payload.content_md, first_line=payload.first_line)


# ---------------------------------------------------------------- 检索
@router.post("/retrieval/test", response_model=RetrievalResult)
def retrieval_test(payload: RetrievalRequest, request: Request, db: Session = Depends(get_db),
                   user: AppUser = Depends(require("knowledge:retrieval:test"))) -> dict:
    actor = actor_of(request, user, db)
    filters = payload.filters.model_dump(exclude_none=True)
    result = knowledge_retrieval.search(
        db, payload.query, filters=filters, top_k=payload.top_k, actor=actor,
        identity_level=payload.identity_level,
    )
    knowledge_retrieval.log_search(db, actor, payload.query, filters, payload.top_k, result,
                                   identity_level=payload.identity_level, kind="TEST")
    return result


# ---------------------------------------------------------------- 文档
@router.get("/documents", response_model=DocumentPage)
def list_documents(keyword: str | None = None, category: str | None = None,
                   status: str | None = None, product_scope: str | None = None,
                   page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                   db: Session = Depends(get_db),
                   user: AppUser = Depends(require("knowledge:document:read"))) -> dict:
    return knowledge_governance.list_documents(
        db, keyword=keyword, category=category, status=status,
        product_scope=product_scope, page=page, page_size=page_size,
    )


@router.get("/documents/{document_pk}", response_model=DocumentView)
def get_document(document_pk: int, db: Session = Depends(get_db),
                 user: AppUser = Depends(require("knowledge:document:read"))) -> dict:
    return knowledge_governance.document_detail(db, document_pk)


# ---------------------------------------------------------------- 治理与概览
@router.get("/governance/report")
def governance_report(db: Session = Depends(get_db),
                      user: AppUser = Depends(require("knowledge:governance:read"))) -> dict:
    return knowledge_governance.governance_report(db)


@router.get("/overview", response_model=None)
def overview(db: Session = Depends(get_db),
             user: AppUser = Depends(require("knowledge:document:read"))) -> dict:
    return knowledge_governance.overview(db)


# ---------------------------------------------------------------- 规则
@router.get("/rules", response_model=list[RuleView])
def list_rules(status: str | None = None, source_kind: str | None = None,
               db: Session = Depends(get_db),
               user: AppUser = Depends(require("knowledge:rule:read"))) -> list[dict]:
    return knowledge_rule.list_rules(db, status=status, source_kind=source_kind)


@router.post("/rules", response_model=RuleView)
def create_rule(payload: RuleCreate, request: Request, db: Session = Depends(get_db),
                user: AppUser = Depends(require("knowledge:rule:write"))) -> dict:
    return knowledge_rule.create_rule(db, actor_of(request, user, db), payload.model_dump())


@router.post("/rules/import", response_model=RuleImportResult)
async def import_rules(request: Request, files: list[UploadFile] = File(...),
                       db: Session = Depends(get_db),
                       user: AppUser = Depends(require("knowledge:document:import"))) -> dict:
    payloads = [(upload.filename or "upload", await upload.read()) for upload in files]
    return knowledge_rule.import_yaml(db, actor_of(request, user, db), payloads)


@router.get("/rules/{rule_pk}", response_model=RuleView)
def get_rule(rule_pk: int, db: Session = Depends(get_db),
             user: AppUser = Depends(require("knowledge:rule:read"))) -> dict:
    return knowledge_rule.get_rule(db, rule_pk)


@router.patch("/rules/{rule_pk}", response_model=RuleView)
def update_rule(rule_pk: int, payload: RuleUpdate, request: Request, db: Session = Depends(get_db),
                user: AppUser = Depends(require("knowledge:rule:write"))) -> dict:
    return knowledge_rule.update_rule(db, actor_of(request, user, db), rule_pk,
                                      payload.model_dump(exclude_none=True))


@router.post("/rules/check-conflicts", response_model=list[RuleConflictView])
def check_conflicts(db: Session = Depends(get_db),
                    user: AppUser = Depends(require("knowledge:rule:read"))) -> list[dict]:
    rows = knowledge_rule.sync_conflicts(db)
    return [knowledge_rule.conflict_view(row) for row in rows]


@router.get("/rule-conflicts", response_model=list[RuleConflictView])
def list_conflicts(status: str | None = None, db: Session = Depends(get_db),
                   user: AppUser = Depends(require("knowledge:rule:read"))) -> list[dict]:
    from sqlalchemy import select

    from app.models.generated import RuleConflict
    statement = select(RuleConflict)
    if status:
        statement = statement.where(RuleConflict.status == status.upper())
    rows = db.execute(statement.order_by(RuleConflict.id)).scalars().all()
    return [knowledge_rule.conflict_view(row) for row in rows]


@router.patch("/rule-conflicts/{conflict_id}", response_model=RuleConflictView)
def resolve_conflict(conflict_id: int, request: Request, db: Session = Depends(get_db),
                     user: AppUser = Depends(require("knowledge:rule:write"))) -> dict:
    return knowledge_rule.resolve_conflict(db, actor_of(request, user, db), conflict_id)


# ---------------------------------------------------------------- 版本与发布
@router.get("/documents/{document_pk}/versions", response_model=list[VersionBase])
def list_versions(document_pk: int, db: Session = Depends(get_db),
                  user: AppUser = Depends(require("knowledge:document:read"))) -> list[dict]:
    return knowledge_governance.list_versions(db, document_pk)


@router.post("/versions/{version_id}/submit", response_model=VersionBase)
def submit_version(version_id: int, request: Request, db: Session = Depends(get_db),
                   user: AppUser = Depends(require("knowledge:document:write"))) -> dict:
    return knowledge_governance.submit(db, actor_of(request, user, db), version_id)


@router.post("/versions/{version_id}/publish", response_model=PublishResult)
def publish_version(version_id: int, payload: PublishRequest, request: Request,
                    db: Session = Depends(get_db),
                    user: AppUser = Depends(require("knowledge:document:publish"))) -> dict:
    return knowledge_governance.publish(
        db, actor_of(request, user, db), version_id,
        change_summary=payload.change_summary,
        effective_from=_parse_effective(payload.effective_from),
    )


@router.post("/versions/{version_id}/rollback", response_model=VersionBase)
def rollback_version(version_id: int, request: Request, db: Session = Depends(get_db),
                     user: AppUser = Depends(require("knowledge:document:rollback"))) -> dict:
    return knowledge_governance.rollback(db, actor_of(request, user, db), version_id)


@router.get("/versions/{version_id}/chunks")
def list_chunks(version_id: int, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                db: Session = Depends(get_db),
                user: AppUser = Depends(require("knowledge:document:read"))) -> dict:
    return knowledge_governance.list_chunks(db, version_id, page=page, page_size=page_size)


# ---------------------------------------------------------------- 审核
@router.get("/review/tasks", response_model=list[ReviewTaskView])
def list_review_tasks(status: str | None = None, db: Session = Depends(get_db),
                      user: AppUser = Depends(require("knowledge:review:read"))) -> list[dict]:
    return knowledge_review.list_tasks(db, status=status)


@router.get("/review/tasks/{task_id}", response_model=ReviewTaskView)
def get_review_task(task_id: int, db: Session = Depends(get_db),
                    user: AppUser = Depends(require("knowledge:review:read"))) -> dict:
    return knowledge_review.get_task(db, task_id)


@router.post("/review/tasks/{task_id}/claim", response_model=ReviewTaskView)
def claim_review_task(task_id: int, request: Request, db: Session = Depends(get_db),
                      user: AppUser = Depends(require("knowledge:review:write"))) -> dict:
    return knowledge_review.claim(db, actor_of(request, user, db), task_id)


@router.post("/review/tasks/{task_id}/decide", response_model=ReviewTaskView)
def decide_review_task(task_id: int, payload: ReviewDecideRequest, request: Request,
                       db: Session = Depends(get_db),
                       user: AppUser = Depends(require("knowledge:review:write"))) -> dict:
    return knowledge_review.decide(db, actor_of(request, user, db), task_id,
                                   payload.decision, payload.note)


@router.get("/review/tasks/{task_id}/comments", response_model=list[ReviewCommentView])
def list_review_comments(task_id: int, db: Session = Depends(get_db),
                         user: AppUser = Depends(require("knowledge:review:read"))) -> list[dict]:
    return knowledge_review.list_comments(db, task_id)


@router.post("/review/tasks/{task_id}/comments", response_model=ReviewCommentView)
def add_review_comment(task_id: int, payload: ReviewCommentCreate, request: Request,
                       db: Session = Depends(get_db),
                       user: AppUser = Depends(require("knowledge:review:write"))) -> dict:
    return knowledge_review.add_comment(db, actor_of(request, user, db), task_id,
                                        payload.anchor, payload.content)
