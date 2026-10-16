from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import Conflict, Forbidden, Unauthorized
from app.core.security import (
    create_access_token, create_refresh_token, hash_password, hash_refresh_token, verify_password,
)
from app.models import AppRole, AppUser, AppUserRole, CustomerProfile, RefreshToken
from app.services import audit
from app.services.common import now

MAX_FAILED = 5


def _roles(db: Session, user_id: int) -> list[str]:
    return list(db.execute(
        select(AppRole.code).join(AppUserRole, AppUserRole.role_id == AppRole.id).where(AppUserRole.user_id == user_id)
    ).scalars().all())


def _permissions(db: Session, user: AppUser) -> list[str]:
    from app.api.deps import get_permissions

    return sorted(get_permissions(db, user))


def _issue_tokens(db: Session, user: AppUser, user_agent: str | None = None) -> dict:
    roles = _roles(db, user.id)
    access = create_access_token(user.id, user.tenant_id, user.party, roles)
    raw_refresh, digest = create_refresh_token()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=digest,
        expires_at=now() + timedelta(days=settings.jwt_refresh_ttl_days),
        user_agent=(user_agent or "")[:255] or None,
    ))
    return {
        "access_token": access,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_ttl_minutes * 60,
        "party": user.party,
        "roles": roles,
    }


def _find_user(db: Session, identifier: str) -> AppUser | None:
    """支持用户名或手机号登录（前端 C 端使用 mobile）。"""
    user = db.execute(
        select(AppUser).where(AppUser.tenant_id == settings.tenant_id, AppUser.username == identifier)
    ).scalar_one_or_none()
    if user is None and identifier:
        user = db.execute(
            select(AppUser).where(AppUser.tenant_id == settings.tenant_id, AppUser.phone == identifier)
        ).scalar_one_or_none()
    return user


def _login(db: Session, username: str, password: str, expect_staff: bool, user_agent: str | None = None) -> dict:
    user = _find_user(db, username)
    if not user:
        raise Unauthorized("账号或密码错误", "AUTH_INVALID_CREDENTIALS")
    if user.locked_until and user.locked_until > now():
        raise Unauthorized("账号已锁定，请稍后再试", "AUTH_ACCOUNT_LOCKED")
    if not verify_password(password, user.password_hash):
        user.failed_login_count = (user.failed_login_count or 0) + 1
        if user.failed_login_count >= MAX_FAILED:
            user.locked_until = now() + timedelta(minutes=15)
            user.failed_login_count = 0
        db.commit()
        raise Unauthorized("账号或密码错误", "AUTH_INVALID_CREDENTIALS")
    if user.status != "ACTIVE":
        raise Unauthorized("账号不可用", "AUTH_ACCOUNT_DISABLED")
    if expect_staff and user.party != "STAFF":
        raise Forbidden("该入口仅限员工", "AUTH_WRONG_PORTAL")
    if not expect_staff and user.party not in ("CUSTOMER", "GUEST"):
        raise Forbidden("该入口仅限客户", "AUTH_WRONG_PORTAL")
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now()
    db.commit()
    tokens = _issue_tokens(db, user, user_agent)
    audit.record(db, {"id": user.id, "party": user.party, "label": user.display_name}, "login", "app_user", user.id)
    db.commit()
    return {**tokens, "user": me(db, user)}


def login_staff(db: Session, username: str, password: str, user_agent: str | None = None) -> dict:
    return _login(db, username, password, True, user_agent)


def login_customer(db: Session, username: str, password: str, user_agent: str | None = None) -> dict:
    return _login(db, username, password, False, user_agent)


def register_customer(db: Session, payload: dict) -> dict:
    """注册：接受 username/mobile 两种标识，昵称与手机号字段兼容前端命名。"""
    mobile = payload.get("mobile") or payload.get("phone")
    username = payload.get("username") or mobile
    if not username:
        raise Conflict("VALIDATION_FAILED", "缺少用户名或手机号")
    exists = db.execute(
        select(AppUser.id).where(AppUser.tenant_id == settings.tenant_id, AppUser.username == username)
    ).scalar_one_or_none()
    if exists:
        raise Conflict("USERNAME_TAKEN", "用户名已被占用")
    if mobile:
        phone_exists = db.execute(
            select(AppUser.id).where(AppUser.tenant_id == settings.tenant_id, AppUser.phone == mobile)
        ).scalar_one_or_none()
        if phone_exists:
            raise Conflict("MOBILE_TAKEN", "手机号已注册")
    user = AppUser(
        tenant_id=settings.tenant_id,
        party="CUSTOMER",
        username=username,
        phone=mobile,
        email=payload.get("email"),
        password_hash=hash_password(payload["password"]),
        display_name=payload.get("nickname") or payload.get("display_name") or username,
    )
    db.add(user)
    db.flush()
    db.add(CustomerProfile(tenant_id=settings.tenant_id, user_id=user.id, nickname=user.display_name, real_name=user.display_name))
    db.commit()
    tokens = _issue_tokens(db, user, None)
    audit.record(db, {"id": user.id, "party": "CUSTOMER", "label": user.display_name}, "register", "app_user", user.id)
    db.commit()
    return {**tokens, "user": me(db, user)}


def guest_session(db: Session, display_name: str | None = None, user_agent: str | None = None) -> dict:
    import uuid

    user = AppUser(
        tenant_id=settings.tenant_id,
        party="GUEST",
        username="guest-" + uuid.uuid4().hex[:12],
        password_hash=hash_password(uuid.uuid4().hex),
        display_name=display_name or "访客",
    )
    db.add(user)
    db.commit()
    return _issue_tokens(db, user, user_agent)


def refresh(db: Session, raw_token: str, user_agent: str | None = None) -> dict:
    digest = hash_refresh_token(raw_token)
    row = db.execute(select(RefreshToken).where(RefreshToken.token_hash == digest)).scalar_one_or_none()
    if not row or row.revoked_at is not None or row.expires_at < now():
        raise Unauthorized("刷新令牌无效或已失效", "AUTH_REFRESH_INVALID")
    user = db.get(AppUser, row.user_id)
    if not user or user.status != "ACTIVE":
        raise Unauthorized("账号不可用", "AUTH_ACCOUNT_DISABLED")
    row.revoked_at = now()
    db.commit()
    return _issue_tokens(db, user, user_agent)


def logout(db: Session, user: AppUser) -> dict:
    rows = db.execute(select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))).scalars().all()
    for row in rows:
        row.revoked_at = now()
    db.commit()
    return {"revoked": len(rows)}


def change_password(db: Session, user: AppUser, old_password: str, new_password: str) -> dict:
    if not verify_password(old_password, user.password_hash):
        raise Unauthorized("原密码错误", "AUTH_INVALID_CREDENTIALS")
    user.password_hash = hash_password(new_password)
    user.password_changed_at = now()
    rows = db.execute(select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))).scalars().all()
    for row in rows:
        row.revoked_at = now()
    audit.record(db, {"id": user.id, "party": user.party, "label": user.display_name}, "password_change", "app_user", user.id)
    db.commit()
    return {"changed": True, "revoked_sessions": len(rows)}


def me(db: Session, user: AppUser) -> dict:
    roles = _roles(db, user.id)
    from app.api.deps import get_permissions

    perms = sorted(get_permissions(db, user))
    customer_id = None
    if user.party in ("CUSTOMER", "GUEST"):
        customer_id = db.execute(select(CustomerProfile.id).where(CustomerProfile.user_id == user.id)).scalar_one_or_none()
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "party": user.party,
        "is_super_admin": user.is_super_admin,
        "roles": roles,
        "permissions": perms,
        "customer_id": customer_id,
        "tenant_id": user.tenant_id,
        "channel_scope": _channel_scope(db, user, roles),
    }


def _channel_scope(db: Session, user: AppUser, roles: list[str]) -> list[str]:
    """返回可见渠道的 platform_code 列表（前端用于渠道范围展示）。"""
    from app.models import ChannelAccount, StaffChannelScope

    if user.party != "STAFF":
        return [row for row in db.execute(
            select(ChannelAccount.platform_code).where(ChannelAccount.tenant_id == settings.tenant_id,
                                                      ChannelAccount.status == "ACTIVE",
                                                      ChannelAccount.commerce_enabled.is_(True))
        ).scalars().all()]
    if user.is_super_admin or {"SUPER_ADMIN", "AUDITOR"} & set(roles):
        stmt = select(ChannelAccount.platform_code).where(ChannelAccount.tenant_id == settings.tenant_id)
    else:
        stmt = (select(ChannelAccount.platform_code)
                .join(StaffChannelScope, StaffChannelScope.channel_account_id == ChannelAccount.id)
                .where(StaffChannelScope.user_id == user.id))
    return [row for row in db.execute(stmt).scalars().all()]
