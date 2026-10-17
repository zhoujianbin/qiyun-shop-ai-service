"""审核：队列、认领互斥、锚定批注、决定留痕、自审策略。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import Conflict, NotFound, ValidationError
from app.models.generated import Document, DocumentVersion, ReviewComment, ReviewTask
from app.services import audit
from app.services.common import now

DECISIONS = ("APPROVED", "CHANGES_REQUESTED", "REJECTED")


def review_enabled_self() -> bool:
    return bool(settings.knowledge_allow_self_review)


def task_view(task: ReviewTask, version: DocumentVersion | None = None) -> dict:
    payload = {
        "id": task.id,
        "document_version_id": task.document_version_id,
        "assignee_id": task.assignee_id,
        "status": task.status,
        "due_at": task.due_at.isoformat() if task.due_at else None,
        "decision": task.decision,
        "decided_at": task.decided_at.isoformat() if task.decided_at else None,
        "note": task.note,
        "self_review": task.self_review,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }
    if version is not None:
        payload["version"] = {
            "id": version.id,
            "version": version.version,
            "status": version.status,
            "checksum": version.checksum,
            "change_summary": version.change_summary,
            "created_by": version.created_by,
        }
    return payload


def comment_view(row: ReviewComment) -> dict:
    return {
        "id": row.id,
        "version_id": row.version_id,
        "task_id": row.task_id,
        "author_id": row.author_id,
        "anchor": row.anchor or {},
        "content": row.content,
        "resolved": row.resolved,
        "parent_id": row.parent_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _load(db: Session, task_id: int) -> ReviewTask:
    task = db.get(ReviewTask, task_id)
    if task is None or task.tenant_id != settings.tenant_id:
        raise NotFound("审核任务不存在")
    return task


def list_tasks(db: Session, *, status: str | None = None) -> list[dict]:
    statement = select(ReviewTask).where(ReviewTask.tenant_id == settings.tenant_id)
    if status:
        statement = statement.where(ReviewTask.status == status.upper())
    tasks = db.execute(statement.order_by(ReviewTask.created_at.desc())).scalars().all()
    versions = {
        row.id: row for row in db.execute(
            select(DocumentVersion).where(DocumentVersion.id.in_([task.document_version_id for task in tasks]))
        ).scalars().all()
    } if tasks else {}
    return [task_view(task, versions.get(task.document_version_id)) for task in tasks]


def get_task(db: Session, task_id: int) -> dict:
    task = _load(db, task_id)
    version = db.get(DocumentVersion, task.document_version_id)
    payload = task_view(task, version)
    document = db.get(Document, version.document_pk) if version else None
    payload["document"] = {"id": document.id, "document_id": document.document_id,
                           "title": document.title, "category": document.category} if document else None
    blocking = []
    from app.services import knowledge_rule
    blocking = [knowledge_rule.conflict_view(row) for row in knowledge_rule.open_blocking_conflicts(db)]
    payload["conflicts"] = blocking
    return payload


def claim(db: Session, actor: dict, task_id: int) -> dict:
    task = _load(db, task_id)
    if task.status == "DECIDED":
        raise Conflict("INVALID_STATE", "任务已完成")
    if task.status == "CLAIMED" and task.assignee_id != actor.get("id"):
        raise Conflict("ALREADY_CLAIMED", "任务已被他人认领")
    task.status = "CLAIMED"
    task.assignee_id = actor.get("id")
    audit.record(db, actor, "knowledge.review.claim", "knowledge.review_task", task.id)
    db.flush()
    return task_view(task)


def decide(db: Session, actor: dict, task_id: int, decision: str, note: str | None) -> dict:
    task = _load(db, task_id)
    decision = (decision or "").upper()
    if decision not in DECISIONS:
        raise ValidationError(f"decision 非法：{decision}（允许 {', '.join(DECISIONS)}）")
    if not (note or "").strip():
        raise ValidationError("审核决定必须填写理由")
    if task.status == "DECIDED":
        raise Conflict("INVALID_STATE", "任务已完成")

    version = db.get(DocumentVersion, task.document_version_id)
    if version is None:
        raise NotFound("版本不存在")

    is_self = version.created_by is not None and version.created_by == actor.get("id")
    if is_self and not review_enabled_self():
        raise Conflict("SELF_REVIEW_FORBIDDEN", "不允许审核自己提交的版本")
    task.self_review = bool(is_self)

    task.status = "DECIDED"
    task.decision = decision
    task.decided_at = now()
    task.note = note.strip()
    task.assignee_id = task.assignee_id or actor.get("id")

    if decision == "CHANGES_REQUESTED":
        version.status = "DRAFT"
    elif decision == "REJECTED":
        version.status = "FAILED"
    # APPROVED：版本保持 REVIEWING，等待发布

    audit.record(db, actor, "knowledge.review.decide", "knowledge.review_task", task.id,
                 after={"decision": decision, "self_review": task.self_review, "note": task.note})
    db.flush()
    return task_view(task, version)


def list_comments(db: Session, task_id: int) -> list[dict]:
    _load(db, task_id)
    rows = db.execute(
        select(ReviewComment).where(ReviewComment.task_id == task_id).order_by(ReviewComment.created_at)
    ).scalars().all()
    return [comment_view(row) for row in rows]


def add_comment(db: Session, actor: dict, task_id: int, anchor: dict, content: str) -> dict:
    task = _load(db, task_id)
    if not (content or "").strip():
        raise ValidationError("批注内容不能为空")
    anchor = anchor or {}
    if not any(key in anchor for key in ("title_path", "chunk_ord", "char_range")):
        raise ValidationError("批注锚点必须包含 title_path / chunk_ord / char_range 之一")
    row = ReviewComment(
        tenant_id=settings.tenant_id,
        version_id=task.document_version_id,
        task_id=task.id,
        author_id=actor.get("id"),
        anchor=anchor,
        content=content.strip(),
    )
    db.add(row)
    db.flush()
    audit.record(db, actor, "knowledge.review.comment", "knowledge.review_comment", row.id,
                 after={"anchor": anchor})
    return comment_view(row)
