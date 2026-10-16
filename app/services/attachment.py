from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import Conflict, Forbidden, NotFound, ValidationError
from app.integrations import storage
from app.models import Attachment
from app.services import audit
from app.services.common import get_or_404


def _view(a: Attachment) -> dict:
    return {"id": a.id, "file_name": a.file_name, "content_type": a.content_type,
            "size_bytes": a.size_bytes, "checksum_sha256": a.checksum_sha256, "owner_type": a.owner_type,
            "owner_id": a.owner_id, "status": a.status, "created_at": a.created_at.isoformat(),
            "download_url": f"/api/v1/attachments/{a.id}",
            "url": f"/api/v1/attachments/{a.id}", "storage_key": a.storage_key, "is_public": False}


def upload(db: Session, actor: dict, *, file_name: str, content_type: str | None, payload: bytes,
           owner_type: str = "misc", owner_id: str | None = None) -> dict:
    resolved_type = storage.validate(file_name, content_type, payload)
    saved = storage.save(file_name, payload, owner_type)
    attachment = Attachment(
        tenant_id=settings.tenant_id,
        owner_type=owner_type,
        owner_id=str(owner_id) if owner_id is not None else None,
        file_name=file_name,
        content_type=resolved_type,
        size_bytes=saved["size"],
        storage_key=saved["storage_key"],
        checksum_sha256=saved["checksum"],
        uploaded_by=actor.get("id"),
        status="READY",
    )
    db.add(attachment)
    db.flush()
    audit.record(db, actor, "attachment_upload", "attachment", attachment.id,
                 after={"file_name": file_name, "size": saved["size"], "checksum": saved["checksum"]})
    db.commit()
    return _view(attachment)


def get(db: Session, actor: dict, attachment_id: int) -> Attachment:
    attachment = get_or_404(db, Attachment, attachment_id, "附件不存在")
    if attachment.status != "READY":
        raise Conflict("ATTACHMENT_NOT_READY", f"附件状态 {attachment.status} 不可下载")
    if not storage.exists(attachment.storage_key):
        raise NotFound("附件文件已丢失")
    if actor.get("party") == "STAFF" or attachment.uploaded_by == actor.get("id"):
        return attachment
    raise Forbidden("无权下载该附件", "RESOURCE_FORBIDDEN")


def list_attachments(db: Session, *, owner_type: str | None = None, owner_id: str | None = None) -> list[dict]:
    stmt = select(Attachment).where(Attachment.tenant_id == settings.tenant_id)
    if owner_type:
        stmt = stmt.where(Attachment.owner_type == owner_type)
    if owner_id:
        stmt = stmt.where(Attachment.owner_id == str(owner_id))
    rows = db.execute(stmt.order_by(Attachment.id.desc())).scalars().all()
    return [_view(a) for a in rows]


def path_for(attachment: Attachment) -> str:
    return str(storage.path_of(attachment.storage_key))
