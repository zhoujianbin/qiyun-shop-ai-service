"""文档与版本治理：提交审核、发布门禁、回滚、定时生效。"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import Conflict, NotFound, ValidationError
from app.models.generated import Chunk, Document, DocumentVersion, ReviewTask
from app.services import audit, knowledge_rule

REQUIRED_DOC_FIELDS = ("title", "category", "owner")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load(db: Session, version_id: int) -> tuple[DocumentVersion, Document]:
    version = db.get(DocumentVersion, version_id)
    if version is None or version.tenant_id != settings.tenant_id:
        raise NotFound("版本不存在")
    document = db.get(Document, version.document_pk)
    if document is None:
        raise NotFound("文档不存在")
    return version, document


def version_view(version: DocumentVersion) -> dict:
    return {
        "id": version.id,
        "document_pk": version.document_pk,
        "version": version.version,
        "status": version.status,
        "checksum": version.checksum,
        "change_summary": version.change_summary,
        "source_kind": version.source_kind,
        "effective_from": version.effective_from.isoformat() if version.effective_from else None,
        "effective_until": version.effective_until.isoformat() if version.effective_until else None,
        "published_at": version.published_at.isoformat() if version.published_at else None,
        "created_by": version.created_by,
        "created_at": version.created_at.isoformat() if version.created_at else None,
        "content_md": version.content_md,
    }


def document_view(document: Document, *, include_latest: bool = True) -> dict:
    payload = {
        "id": document.id,
        "document_id": document.document_id,
        "title": document.title,
        "category": document.category,
        "owner": document.owner,
        "status": document.status,
        "current_version": document.current_version,
        "product_scope": document.product_scope,
        "channel_scope": document.channel_scope or [],
        "identity_level": document.identity_level,
        "effective_date": document.effective_date.isoformat() if document.effective_date else None,
        "metadata": document.metadata_json or {},
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
    }
    if include_latest:
        payload["chunk_count"] = None
    return payload


def chunk_view(chunk: Chunk) -> dict:
    meta = chunk.metadata_json or {}
    return {
        "id": chunk.id,
        "ord": chunk.ord,
        "title_path": chunk.title_path or "",
        "content": chunk.content,
        "char_count": len(chunk.content),
        "token_count": chunk.token_count,
        "embedding_status": chunk.embedding_status,
        "identity_level": chunk.identity_level,
        "line_start": meta.get("source_line_start"),
        "line_end": meta.get("source_line_end"),
    }


def create_version(db: Session, actor: dict, document_pk: int, *, content_md: str,
                   change_summary: str | None = None) -> dict:
    """后台以文本新建草稿版本：版本号递增、内容重新切片、写审计。"""
    document = db.get(Document, document_pk)
    if document is None or document.tenant_id != settings.tenant_id:
        raise NotFound("文档不存在")
    content = (content_md or "").strip()
    if not content:
        raise ValidationError("内容不能为空")

    latest = db.execute(
        select(DocumentVersion.version)
        .where(DocumentVersion.document_pk == document_pk)
        .order_by(DocumentVersion.version.desc()).limit(1)
    ).scalar()
    next_version = int(latest or 0) + 1

    version = DocumentVersion(
        tenant_id=settings.tenant_id,
        document_pk=document_pk,
        version=next_version,
        content_md=content,
        checksum=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        status="DRAFT",
        change_summary=(change_summary or "").strip() or None,
        source_kind="MANUAL",
        created_by=actor.get("id"),
    )
    db.add(version)
    try:
        db.flush()
    except IntegrityError as exc:  # 并发保存撞唯一键
        raise Conflict("VERSION_CONFLICT", "该文档的版本号已被占用，请刷新后重试") from exc

    from app.services.knowledge_chunk import split_markdown

    for chunk in split_markdown(content, first_line=1):
        db.add(Chunk(
            tenant_id=settings.tenant_id,
            document_version_id=version.id,
            ord=chunk.ord,
            title_path=chunk.title_path or None,
            content=chunk.content,
            token_count=chunk.token_count,
            embedding_status="PENDING",
            identity_level=document.identity_level,
            metadata_json={
                "source_line_start": chunk.line_start,
                "source_line_end": chunk.line_end,
                "headings": chunk.title_path,
                "doc_version": str(next_version),
                "source": "editor",
            },
        ))

    audit.record(db, actor, "knowledge.version.create", "knowledge.document_version", version.id,
                 after={"document_id": document.document_id, "version": next_version,
                        "source_kind": "MANUAL"})
    db.flush()
    return version_view(version)


def submit(db: Session, actor: dict, version_id: int) -> dict:
    version, document = _load(db, version_id)
    if version.status not in ("DRAFT", "FAILED"):
        raise Conflict("INVALID_STATE", f"当前状态不可提交：{version.status}")
    version.status = "REVIEWING"
    db.flush()

    existing = db.execute(
        select(ReviewTask).where(
            ReviewTask.document_version_id == version.id,
            ReviewTask.status.in_(("PENDING", "CLAIMED")),
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(ReviewTask(
            tenant_id=settings.tenant_id,
            document_version_id=version.id,
            status="PENDING",
            created_by=actor.get("id"),
        ))
    audit.record(db, actor, "knowledge.version.submit", "knowledge.document_version", version.id,
                 after={"status": version.status})
    audit.emit(db, "knowledge.version.submitted", "document_version", version.id,
               {"document_id": document.document_id, "version": version.version},
               request_id=actor.get("request_id"))
    db.flush()
    return version_view(version)


def _check_publish_gates(db: Session, version: DocumentVersion, document: Document) -> list[str]:
    reasons: list[str] = []
    chunk_count = len(db.execute(
        select(Chunk.id).where(Chunk.document_version_id == version.id)
    ).scalars().all())
    if chunk_count == 0:
        reasons.append("切片为空：该版本没有任何切片")
    for field in REQUIRED_DOC_FIELDS:
        if not str(getattr(document, field) or "").strip():
            reasons.append(f"必填元数据缺失：{field}")
    current = db.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_pk == document.id,
            DocumentVersion.status == "ACTIVE",
            DocumentVersion.id != version.id,
        )
    ).scalar_one_or_none()
    if current is not None and current.checksum == version.checksum:
        reasons.append("内容校验和与当前生效版本相同：没有变化，拒绝发布")
    blocking = knowledge_rule.open_blocking_conflicts(db)
    if blocking:
        reasons.append("存在未解决的阻断级规则冲突：" + "、".join(str(row.id) for row in blocking))
    return reasons


def publish(db: Session, actor: dict, version_id: int, *, change_summary: str | None,
            effective_from: datetime | None = None) -> dict:
    version, document = _load(db, version_id)
    if version.status == "ARCHIVED":
        raise Conflict("INVALID_STATE", "已归档的版本不可发布")
    if not (change_summary or "").strip():
        raise ValidationError("必须填写变更摘要 change_summary")

    reasons = _check_publish_gates(db, version, document)
    if reasons:
        raise ValidationError("发布被门禁拒绝", details={"reasons": reasons})

    previous = db.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_pk == document.id, DocumentVersion.status == "ACTIVE"
        )
    ).scalars().all()

    target_status = "ACTIVE"
    if effective_from is not None and effective_from > _now():
        target_status = "SCHEDULED"

    if target_status == "ACTIVE":
        for row in previous:
            if row.id != version.id:
                row.status = "ARCHIVED"
                audit.emit(db, "knowledge.version.archived", "document_version", row.id,
                           {"document_id": document.document_id, "version": row.version})
        db.flush()  # 先让旧版本退出 ACTIVE，避免撞部分唯一索引
        document.status = "ACTIVE"
        document.current_version = version.version
    version.status = target_status
    version.change_summary = change_summary.strip()
    version.effective_from = effective_from
    version.published_at = _now()
    version.published_by = actor.get("id")
    db.flush()

    audit.record(db, actor, "knowledge.version.publish", "knowledge.document_version", version.id,
                 after={"status": target_status, "version": version.version})
    audit.emit(db, "knowledge.version.published", "document_version", version.id,
               {"document_id": document.document_id, "version": version.version, "status": target_status},
               request_id=actor.get("request_id"))

    return {
        **version_view(version),
        "publish_info": {
            "change_summary": version.change_summary,
            "affected_scope": {
                "product_scope": document.product_scope,
                "channel_scope": document.channel_scope or [],
            },
            "citation_count": 0,
            "rollback_target": previous[0].version if previous else None,
        },
        "reasons": [],
    }


def rollback(db: Session, actor: dict, version_id: int) -> dict:
    """回滚到给定版本：复制内容生成新版本并直接生效，不覆盖历史。"""
    target, document = _load(db, version_id)
    if target.status not in ("ACTIVE", "ARCHIVED", "FAILED"):
        raise Conflict("INVALID_STATE", f"该版本不可作为回滚目标：{target.status}")

    latest = db.execute(
        select(DocumentVersion.version)
        .where(DocumentVersion.document_pk == document.id)
        .order_by(DocumentVersion.version.desc()).limit(1)
    ).scalar_one()
    new_version = DocumentVersion(
        tenant_id=settings.tenant_id,
        document_pk=document.id,
        version=int(latest) + 1,
        content_md=target.content_md,
        checksum=target.checksum,
        status="DRAFT",
        change_summary=f"回滚到版本 {target.version}",
        source_kind=target.source_kind,
        published_at=_now(),
        published_by=actor.get("id"),
        created_by=actor.get("id"),
    )
    db.add(new_version)
    db.flush()

    for row in db.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_pk == document.id,
            DocumentVersion.status == "ACTIVE",
            DocumentVersion.id != new_version.id,
        )
    ).scalars().all():
        row.status = "ARCHIVED"
    db.flush()  # 旧版本先退出 ACTIVE，再把新版本置为 ACTIVE
    new_version.status = "ACTIVE"

    for chunk in db.execute(
        select(Chunk).where(Chunk.document_version_id == target.id)
    ).scalars().all():
        db.add(Chunk(
            tenant_id=settings.tenant_id,
            document_version_id=new_version.id,
            ord=chunk.ord,
            title_path=chunk.title_path,
            content=chunk.content,
            token_count=chunk.token_count,
            embedding=chunk.embedding,
            embedding_status="READY" if chunk.embedding is not None else "PENDING",
            identity_level=chunk.identity_level,
            metadata_json=chunk.metadata_json or {},
        ))

    document.status = "ACTIVE"
    document.current_version = new_version.version
    db.flush()

    audit.record(db, actor, "knowledge.version.rollback", "knowledge.document_version", new_version.id,
                 before={"from_version": latest}, after={"to_version": target.version})
    audit.emit(db, "knowledge.version.rolled_back", "document_version", new_version.id,
               {"document_id": document.document_id, "to_version": target.version},
               request_id=actor.get("request_id"))
    return version_view(new_version)


def activate_due(db: Session) -> dict:
    """把到点的待生效版本转为生效（worker 调用）。"""
    due = db.execute(
        select(DocumentVersion).where(
            DocumentVersion.status == "SCHEDULED",
            DocumentVersion.effective_from.is_not(None),
            DocumentVersion.effective_from <= _now(),
        )
    ).scalars().all()
    activated = 0
    for version in due:
        document = db.get(Document, version.document_pk)
        for row in db.execute(
            select(DocumentVersion).where(
                DocumentVersion.document_pk == version.document_pk,
                DocumentVersion.status == "ACTIVE",
            )
        ).scalars().all():
            row.status = "ARCHIVED"
            audit.emit(db, "knowledge.version.archived", "document_version", row.id,
                       {"document_id": document.document_id if document else None, "version": row.version})
        version.status = "ACTIVE"
        if document is not None:
            document.status = "ACTIVE"
            document.current_version = version.version
        audit.emit(db, "knowledge.version.published", "document_version", version.id,
                   {"document_id": document.document_id if document else None,
                    "version": version.version, "status": "ACTIVE"})
        activated += 1
    db.flush()
    return {"activated": activated}


def list_versions(db: Session, document_pk: int) -> list[dict]:
    document = db.get(Document, document_pk)
    if document is None or document.tenant_id != settings.tenant_id:
        raise NotFound("文档不存在")
    rows = db.execute(
        select(DocumentVersion).where(DocumentVersion.document_pk == document_pk)
        .order_by(DocumentVersion.version.desc())
    ).scalars().all()
    return [{k: v for k, v in version_view(row).items() if k != "content_md"} for row in rows]


def list_chunks(db: Session, version_id: int, *, page: int, page_size: int) -> dict:
    _load(db, version_id)
    rows = db.execute(
        select(Chunk).where(Chunk.document_version_id == version_id).order_by(Chunk.ord)
        .offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    total = len(db.execute(select(Chunk.id).where(Chunk.document_version_id == version_id)).scalars().all())
    return {"page": page, "page_size": page_size, "total": total,
            "items": [chunk_view(row) for row in rows]}

# ---------------------------------------------------------------------------
# 文档列表 / 详情 / 治理报告 / 概览
# ---------------------------------------------------------------------------
def list_documents(db: Session, *, keyword: str | None = None, category: str | None = None,
                   status: str | None = None, product_scope: str | None = None,
                   page: int = 1, page_size: int = 20, document_ids: list[str] | None = None) -> dict:
    from sqlalchemy import func, or_

    statement = select(Document).where(Document.tenant_id == settings.tenant_id)
    if keyword:
        like = f"%{keyword}%"
        statement = statement.where(or_(Document.title.ilike(like), Document.document_id.ilike(like)))
    if category:
        statement = statement.where(Document.category == category)
    if status:
        statement = statement.where(Document.status == status.upper())
    if product_scope:
        statement = statement.where(Document.product_scope == product_scope)
    if document_ids is not None:
        statement = statement.where(Document.document_id.in_(document_ids))
    total = db.execute(select(func.count()).select_from(statement.subquery())).scalar_one()
    rows = db.execute(
        statement.order_by(Document.updated_at.desc(), Document.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    return {
        "page": page, "page_size": page_size, "total": total,
        "items": [document_view(row) for row in rows],
        "meta": {"page": page, "page_size": page_size, "total": total},
    }


def document_detail(db: Session, document_pk: int) -> dict:
    from app.models.generated import Chunk

    document = db.get(Document, document_pk)
    if document is None or document.tenant_id != settings.tenant_id:
        raise NotFound("文档不存在")
    versions = db.execute(
        select(DocumentVersion).where(DocumentVersion.document_pk == document_pk)
        .order_by(DocumentVersion.version.desc())
    ).scalars().all()
    active = next((row for row in versions if row.status == "ACTIVE"), None)
    payload = document_view(document)
    payload["versions"] = [version_view(row) for row in versions]
    payload["active_version"] = version_view(active) if active else None
    payload["chunk_count"] = db.execute(
        select(func.count()).select_from(Chunk).where(
            Chunk.document_version_id == (active.id if active else -1)
        )
    ).scalar_one()
    return payload


def governance_report(db: Session) -> dict:
    """五类治理报告：重复、过期、孤立、冲突、与商品主数据不一致。"""
    from app.models import Product
    from app.models.generated import Chunk, RuleConflict

    documents = db.execute(
        select(Document).where(Document.tenant_id == settings.tenant_id)
    ).scalars().all()
    now = _now()

    # 版本信息
    versions = db.execute(select(DocumentVersion)).scalars().all()
    active_by_doc: dict[int, DocumentVersion] = {}
    latest_by_doc: dict[int, DocumentVersion] = {}
    for version in sorted(versions, key=lambda row: (row.document_pk, row.version)):
        latest_by_doc[version.document_pk] = version
        if version.status == "ACTIVE":
            active_by_doc[version.document_pk] = version

    # 1) 重复：标题相同或最新内容校验和相同
    by_title: dict[str, list[Document]] = {}
    by_checksum: dict[str, list[Document]] = {}
    for document in documents:
        by_title.setdefault(document.title.strip(), []).append(document)
        latest = latest_by_doc.get(document.id)
        if latest is not None:
            by_checksum.setdefault(latest.checksum, []).append(document)
    duplicates = []
    seen_pairs = set()
    for bucket in list(by_title.values()) + list(by_checksum.values()):
        if len(bucket) < 2:
            continue
        for left in bucket:
            for right in bucket:
                if left.id >= right.id:
                    continue
                key = (left.id, right.id)
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                duplicates.append({
                    "type": "DUPLICATE",
                    "document_id": left.document_id,
                    "title": left.title,
                    "detail": f"与 {right.document_id}（{right.title}）重复",
                    "filter": {"document_ids": [left.document_id, right.document_id]},
                })

    # 2) 过期：生效版本已过期，或 12 个月未更新
    expired = []
    for document in documents:
        active = active_by_doc.get(document.id)
        reason = None
        if active is not None and active.effective_until is not None and active.effective_until < now:
            reason = "生效版本已过期"
        elif document.updated_at is not None and (now - document.updated_at).days > 365:
            reason = "超过 12 个月未更新"
        if reason:
            expired.append({
                "type": "EXPIRED", "document_id": document.document_id, "title": document.title,
                "detail": reason, "filter": {"status": "ACTIVE", "expired": True},
            })

    # 3) 孤立：没有任何其他文档引用它的 document_id
    contents = db.execute(select(DocumentVersion.content_md)).scalars().all()
    blob = "\n".join(contents)
    orphans = []
    for document in documents:
        if blob.count(document.document_id) <= 1:  # 只在自己正文里出现（或从未出现）
            orphans.append({
                "type": "ORPHAN", "document_id": document.document_id, "title": document.title,
                "detail": "没有其他文档引用该 document_id",
                "filter": {"document_ids": [document.document_id]},
            })

    # 4) 冲突：未解决的阻断级规则冲突 + 同一文档多 ACTIVE
    conflicts = []
    for row in db.execute(
        select(RuleConflict).where(RuleConflict.status == "OPEN", RuleConflict.severity == "BLOCK")
    ).scalars().all():
        conflicts.append({
            "type": "CONFLICT", "document_id": None, "title": f"规则冲突 #{row.id}",
            "detail": f"{row.conflict_type}：规则 {row.rule_a_id} vs {row.rule_b_id}",
            "filter": {"conflicts": True},
        })
    active_counter: dict[int, int] = {}
    for version in versions:
        if version.status == "ACTIVE":
            active_counter[version.document_pk] = active_counter.get(version.document_pk, 0) + 1
    for document_pk, count in active_counter.items():
        if count > 1:
            conflicts.append({
                "type": "CONFLICT", "document_id": None, "title": f"文档 {document_pk}",
                "detail": f"同一文档存在 {count} 个生效版本",
                "filter": {"multiple_active": True},
            })

    # 5) 与商品主数据不一致
    known_models = set(db.execute(select(Product.model_code)).scalars().all())
    inconsistent = []
    for document in documents:
        if document.product_scope and known_models and document.product_scope not in known_models:
            inconsistent.append({
                "type": "INCONSISTENT", "document_id": document.document_id, "title": document.title,
                "detail": f"product_scope={document.product_scope} 不在商品主数据中",
                "filter": {"product_scope": document.product_scope},
            })

    return {
        "duplicate": duplicates,
        "expired": expired,
        "orphan": orphans,
        "conflict": conflicts,
        "inconsistent": inconsistent,
        "counts": {
            "duplicate": len(duplicates), "expired": len(expired), "orphan": len(orphans),
            "conflict": len(conflicts), "inconsistent": len(inconsistent),
        },
    }


def overview(db: Session) -> dict:
    from sqlalchemy import func

    from app.models.generated import Chunk, ReviewTask

    tenant = settings.tenant_id
    document_count = db.execute(
        select(func.count()).select_from(Document).where(Document.tenant_id == tenant)
    ).scalar_one()
    chunk_count = db.execute(
        select(func.count()).select_from(Chunk).where(Chunk.tenant_id == tenant)
    ).scalar_one()
    pending = db.execute(
        select(func.count()).select_from(ReviewTask).where(
            ReviewTask.tenant_id == tenant, ReviewTask.status.in_(("PENDING", "CLAIMED"))
        )
    ).scalar_one()
    report = governance_report(db)
    return {
        "documents": document_count,
        "chunks": chunk_count,
        "pending_review": pending,
        "expired": report["counts"]["expired"],
        "conflicts": report["counts"]["conflict"],
        "governance": report["counts"],
    }
