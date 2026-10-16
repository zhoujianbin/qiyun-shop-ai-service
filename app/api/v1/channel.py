from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require
from app.core.db import get_db
from app.models import AppUser
from app.schemas.views import ChannelAccountPage, ChannelView, PublicChannelView
from app.services import staff as staff_service

router = APIRouter(prefix="/channel-accounts", tags=["channel"])


class ChannelCreate(BaseModel):
    code: str
    name: str
    platform_code: str | None = None
    channel_type: str = "OTHER"
    external_account_id: str | None = None
    commerce_enabled: bool = True


class ChannelUpdate(BaseModel):
    name: str | None = None
    platform_code: str | None = None
    external_account_id: str | None = None
    commerce_enabled: bool | None = None
    status: str | None = None


@router.get("", response_model=ChannelAccountPage)
def list_channels(db: Session = Depends(get_db), user: AppUser = Depends(require("shared:channel:read"))) -> list[dict]:
    return staff_service.list_channels(db)


@router.post("", response_model=ChannelView)
def create_channel(payload: ChannelCreate, db: Session = Depends(get_db),
                   user: AppUser = Depends(require("shared:channel:write"))) -> dict:
    return staff_service.create_channel(db, {"id": user.id, "party": user.party, "label": user.display_name},
                                        payload.model_dump())


@router.patch("/{channel_id}", response_model=ChannelView)
def update_channel(channel_id: int, payload: ChannelUpdate, db: Session = Depends(get_db),
                   user: AppUser = Depends(require("shared:channel:write"))) -> dict:
    return staff_service.update_channel(db, {"id": user.id, "party": user.party, "label": user.display_name},
                                        channel_id, payload.model_dump(exclude_none=True))


public_router = APIRouter(prefix="/channels", tags=["channel"])


@public_router.get("", response_model=list[PublicChannelView])
def list_public_channels(db: Session = Depends(get_db)) -> list[dict]:
    """C 端可见渠道列表（无需权限，登录/游客均可访问）。"""
    return staff_service.list_public_channels(db)
