from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.api.deps import require
from app.core.db import get_db
from app.core.errors import ValidationError
from app.models import AppUser
from app.schemas.views import (
    AuditLogPage,
    PermissionPage,
    RolePage,
    PermissionView,
    RoleView,
    UserChannelScopesView,
    UserPage,
    UserRolesView,
    UserView,
)
from app.services import staff as staff_service

router = APIRouter(tags=["staff"])


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=12, max_length=128)
    email: str | None = None
    phone: str | None = None
    role_codes: list[str] = []
    channel_account_ids: list[int] | None = None
    channel_ids: list[int] | None = None

    @model_validator(mode="after")
    def _pick_channel_field(self):
        if self.channel_account_ids is None and self.channel_ids is not None:
            self.channel_account_ids = self.channel_ids
        return self


class UserUpdate(BaseModel):
    display_name: str | None = None
    email: str | None = None
    phone: str | None = None
    status: str | None = None
    version: int | None = None


class RoleCodes(BaseModel):
    role_codes: list[str]


class ChannelScopes(BaseModel):
    """渠道范围：channel_account_ids 为契约字段，channel_ids 为兼容别名。"""

    channel_account_ids: list[int] | None = None
    channel_ids: list[int] | None = None

    @model_validator(mode="after")
    def _pick_channel_field(self):
        if self.channel_account_ids is None and self.channel_ids is not None:
            self.channel_account_ids = self.channel_ids
        if self.channel_account_ids is None:
            raise ValidationError("缺少 channel_account_ids")
        return self


def _actor(user: AppUser) -> dict:
    return {"id": user.id, "party": user.party, "label": user.display_name, "is_super_admin": user.is_super_admin}


@router.get("/staff/users", response_model=UserPage)
def list_users(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), keyword: str | None = None,
               status: str | None = None, db: Session = Depends(get_db),
               user: AppUser = Depends(require("shared:staff:read"))) -> dict:
    return staff_service.list_users(db, page=page, page_size=page_size, keyword=keyword, status=status)


@router.post("/staff/users", response_model=UserView)
def create_user(payload: UserCreate, db: Session = Depends(get_db),
                user: AppUser = Depends(require("shared:staff:write"))) -> dict:
    data = payload.model_dump()
    data["channel_ids"] = payload.channel_account_ids or []
    return staff_service.create_user(db, _actor(user), data)


@router.get("/roles", response_model=RolePage)
def list_roles(db: Session = Depends(get_db), user: AppUser = Depends(require("shared:staff:read"))) -> list[dict]:
    return staff_service.list_roles(db)


@router.get("/permissions", response_model=PermissionPage)
def list_permissions(db: Session = Depends(get_db), user: AppUser = Depends(require("shared:staff:read"))) -> list[dict]:
    return staff_service.list_permissions(db)


@router.get("/staff/users/{user_id}", response_model=UserView)
def get_user(user_id: int, db: Session = Depends(get_db),
             user: AppUser = Depends(require("shared:staff:read"))) -> dict:
    return staff_service.get_user(db, user_id)


@router.patch("/staff/users/{user_id}", response_model=UserView)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db),
                user: AppUser = Depends(require("shared:staff:write"))) -> dict:
    return staff_service.update_user(db, _actor(user), user_id, payload.model_dump(exclude_none=True))


@router.post("/staff/users/{user_id}/disable", response_model=UserView)
def disable_user(user_id: int, db: Session = Depends(get_db),
                 user: AppUser = Depends(require("shared:staff:write"))) -> dict:
    return staff_service.disable_user(db, _actor(user), user_id)


@router.get("/staff/users/{user_id}/roles", response_model=UserRolesView)
def get_user_roles(user_id: int, db: Session = Depends(get_db),
                   user: AppUser = Depends(require("shared:staff:read"))) -> dict:
    return staff_service.get_user_roles(db, user_id)


@router.put("/staff/users/{user_id}/roles", response_model=UserView)
def set_user_roles(user_id: int, payload: RoleCodes, db: Session = Depends(get_db),
                   user: AppUser = Depends(require("shared:staff:write"))) -> dict:
    return staff_service.set_roles(db, _actor(user), user_id, payload.role_codes)


@router.get("/staff/users/{user_id}/channel-scopes", response_model=UserChannelScopesView)
def get_user_channel_scopes(user_id: int, db: Session = Depends(get_db),
                            user: AppUser = Depends(require("shared:staff:read"))) -> dict:
    return staff_service.get_channel_scopes(db, user_id)


@router.put("/staff/users/{user_id}/channel-scopes", response_model=UserView)
def set_user_channel_scopes(user_id: int, payload: ChannelScopes, db: Session = Depends(get_db),
                            user: AppUser = Depends(require("shared:staff:write"))) -> dict:
    return staff_service.set_channel_scopes(db, _actor(user), user_id, payload.channel_account_ids)


@router.get("/audit-logs", response_model=AuditLogPage)
def list_audit_logs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                    resource_type: str | None = None, action: str | None = None, actor_id: int | None = None,
                    db: Session = Depends(get_db), user: AppUser = Depends(require("shared:audit:read"))) -> dict:
    return staff_service.list_audit_logs(db, page=page, page_size=page_size, resource_type=resource_type,
                                         action=action, actor_id=actor_id)
