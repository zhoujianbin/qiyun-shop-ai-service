from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.errors import Forbidden, Unauthorized
from app.core.security import decode_token
from app.models import AppPermission, AppRole, AppRolePermission, AppUser, AppUserRole, ChannelAccount, StaffChannelScope

ALL_CHANNEL_ROLES = {"SUPER_ADMIN", "AUDITOR"}


def get_current_user(request: Request, db: Session = Depends(get_db)) -> AppUser:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise Unauthorized("缺少访问令牌", "AUTH_TOKEN_MISSING")
    claims = decode_token(auth[7:].strip())
    user = db.get(AppUser, int(claims["sub"]))
    if not user or user.status != "ACTIVE":
        raise Unauthorized("账号不可用", "AUTH_ACCOUNT_DISABLED")
    request.state.user_id = user.id
    request.state.tenant_id = user.tenant_id
    request.state.party = user.party
    return user


def get_roles(db: Session, user: AppUser) -> list[str]:
    rows = db.execute(
        select(AppRole.code).join(AppUserRole, AppUserRole.role_id == AppRole.id).where(AppUserRole.user_id == user.id)
    ).scalars().all()
    return list(rows)


def get_permissions(db: Session, user: AppUser) -> set[str]:
    if user.is_super_admin:
        return set(db.execute(select(AppPermission.code)).scalars().all())
    rows = db.execute(
        select(AppPermission.code)
        .join(AppRolePermission, AppRolePermission.permission_id == AppPermission.id)
        .join(AppUserRole, AppUserRole.role_id == AppRolePermission.role_id)
        .where(AppUserRole.user_id == user.id)
    ).scalars().all()
    return set(rows)


def request_permissions(request: Request, db: Session, user: AppUser) -> set[str]:
    cached = getattr(request.state, "permissions", None)
    if cached is None:
        cached = get_permissions(db, user)
        request.state.permissions = cached
        request.state.roles = get_roles(db, user)
    return cached


def require(*codes: str) -> Callable:
    """权限依赖：任意一个权限码命中即通过。"""

    def dependency(request: Request, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)) -> AppUser:
        perms = request_permissions(request, db, user)
        if not any(code in perms for code in codes):
            raise Forbidden("缺少权限：" + "/".join(codes), details={"required": list(codes)})
        return user

    return dependency


def get_roles_cached(request: Request, db: Session, user: AppUser) -> list[str]:
    request_permissions(request, db, user)
    return getattr(request.state, "roles", [])


def visible_channel_ids(request: Request, db: Session, user: AppUser) -> list[int] | None:
    """返回可见渠道 id 列表；None 表示全部渠道。"""
    roles = get_roles_cached(request, db, user)
    if user.is_super_admin or (set(roles) & ALL_CHANNEL_ROLES):
        return None
    rows = db.execute(select(StaffChannelScope.channel_account_id).where(StaffChannelScope.user_id == user.id)).scalars().all()
    return list(rows)


def check_channel_scope(request: Request, db: Session, user: AppUser, channel_account_id: int | None) -> None:
    if channel_account_id is None:
        return
    allowed = visible_channel_ids(request, db, user)
    if allowed is not None and channel_account_id not in allowed:
        raise Forbidden("渠道超出数据范围", "CHANNEL_OUT_OF_SCOPE", {"channel_account_id": channel_account_id})


def first_channel_id(db: Session) -> int | None:
    return db.execute(select(ChannelAccount.id).where(ChannelAccount.status == "ACTIVE").order_by(ChannelAccount.id)).scalars().first()


def tenant_id() -> int:
    return settings.tenant_id
