from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require
from app.api.v1.common import actor_of
from app.core.db import get_db
from app.models import AppUser
from app.schemas.views import AttachmentView
from app.services import attachment as attachment_service

router = APIRouter(prefix="/attachments", tags=["attachment"])


@router.post("", response_model=AttachmentView)
async def upload_attachment(request: Request, file: UploadFile = File(...), owner_type: str = Form("misc"),
                            owner_id: str | None = Form(None), db: Session = Depends(get_db),
                            user: AppUser = Depends(get_current_user)) -> dict:
    actor = actor_of(request, user, db)
    payload = await file.read()
    return attachment_service.upload(db, actor, file_name=file.filename or "upload.bin",
                                     content_type=file.content_type, payload=payload,
                                     owner_type=owner_type, owner_id=owner_id)


@router.get("", response_model=list[AttachmentView])
def list_attachments(owner_type: str | None = None, owner_id: str | None = None,
                     db: Session = Depends(get_db),
                     user: AppUser = Depends(require("shop:aftersales:read", "shop:invoice:read",
                                                     "shop:customer:read"))) -> list[dict]:
    return attachment_service.list_attachments(db, owner_type=owner_type, owner_id=owner_id)


@router.get("/{attachment_id}")
def download_attachment(attachment_id: int, request: Request, db: Session = Depends(get_db),
                        user: AppUser = Depends(get_current_user)) -> FileResponse:
    actor = actor_of(request, user, db)
    attachment = attachment_service.get(db, actor, attachment_id)
    return FileResponse(attachment_service.path_for(attachment), media_type=attachment.content_type,
                        filename=attachment.file_name)
