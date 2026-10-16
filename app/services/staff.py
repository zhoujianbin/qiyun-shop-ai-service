from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import Conflict, Forbidden, NotFound, ValidationError
from app.core.security import hash_password
from app.models import (
    AppPermission, AppRole, AppRolePermission, AppUser, AppUserRole, AuditLog, ChannelAccount, StaffChannelScope,
)
from app.services import audit
from app.services.common import get_or_404, list_payload, page_offset


def _user_view(db: Session, user: AppUser) -> dict:
    roles = db.execute(select(AppRole.code).join(AppUserRole, AppUserRole.role_id == AppRole.id)
                       .where(AppUserRole.user_id == user.id)).scalars().all()
    scopes = db.execute(select(StaffChannelScope.channel_account_id)
                        .where(StaffChannelScope.user_id == user.id)).scalars().all()
    return {"id": user.id, "username": user.username, "display_name": user.display_name, "party": user.party,
            "email": user.email, "phone": user.phone,
            "phone_masked": (user.phone[:3] + "****" + user.phone[-4:]) if user.phone and len(user.phone) >= 7 else user.phone,
            "status": user.status,
            "is_super_admin": user.is_super_admin, "roles": list(roles), "role_codes": list(roles),
            "channel_ids": list(scopes), "channel_account_ids": list(scopes),
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "created_at": user.created_at.isoformat()}


def list_users(db: Session, *, page: int, page_size: int, keyword: str | None = None,
               status: str | None = None) -> dict:
    stmt = select(AppUser).where(AppUser.tenant_id == settings.tenant_id, AppUser.party == "STAFF")
    if keyword:
        stmt = stmt.where(or_(AppUser.username.ilike(f"%{keyword}%"), AppUser.display_name.ilike(f"%{keyword}%")))
    if status:
        stmt = stmt.where(AppUser.status == status)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    offset, limit = page_offset(page, page_size)
    rows = db.execute(stmt.order_by(AppUser.id).offset(offset).limit(limit)).scalars().all()
    return {"page": page, "page_size": page_size, "total": total, "meta": {"page": page, "page_size": page_size, "total": total},
            "items": [_user_view(db, u) for u in rows]}


def get_user(db: Session, user_id: int) -> dict:
    user = get_or_404(db, AppUser, user_id, "员工不存在")
    if user.party != "STAFF":
        raise ValidationError("只能查看员工账号")
    return _user_view(db, user)


def get_user_roles(db: Session, user_id: int) -> dict:
    view = get_user(db, user_id)
    return {"user_id": view["id"], "role_codes": view["roles"], "roles": view["roles"],
            "channel_account_ids": view["channel_account_ids"], "channel_ids": view["channel_ids"]}


def get_channel_scopes(db: Session, user_id: int) -> dict:
    view = get_user(db, user_id)
    return {"user_id": view["id"], "channel_account_ids": view["channel_account_ids"],
            "channel_ids": view["channel_ids"]}


def create_user(db: Session, actor: dict, payload: dict) -> dict:
    exists = db.execute(select(AppUser.id).where(AppUser.tenant_id == settings.tenant_id,
                                                  AppUser.username == payload["username"])).scalar_one_or_none()
    if exists:
        raise Conflict("USERNAME_TAKEN", "用户名已存在")
    if len(payload["password"]) < 12:
        raise ValidationError("初始密码长度至少 12 位")
    user = AppUser(tenant_id=settings.tenant_id, party="STAFF", username=payload["username"],
                   display_name=payload["display_name"], email=payload.get("email"), phone=payload.get("phone"),
                   password_hash=hash_password(payload["password"]), status="ACTIVE")
    db.add(user)
    db.flush()
    _replace_roles(db, actor, user, payload.get("role_codes") or [])
    _replace_scopes(db, user, payload.get("channel_ids") or [])
    audit.record(db, actor, "staff_create", "app_user", user.id, after={"username": user.username})
    db.commit()
    return _user_view(db, user)


def update_user(db: Session, actor: dict, user_id: int, payload: dict) -> dict:
    user = get_or_404(db, AppUser, user_id, "员工不存在")
    if user.party != "STAFF":
        raise ValidationError("只能修改员工账号")
    if user.is_super_admin and not actor.get("is_super_admin"):
        raise Forbidden("不能修改超级管理员", "PERM_FORBIDDEN")
    before = _user_view(db, user)
    for field in ("display_name", "email", "phone"):
        if payload.get(field) is not None:
            setattr(user, field, payload[field])
    if payload.get("status") is not None and payload["status"] in ("ACTIVE", "DISABLED", "LOCKED", "PENDING"):
        user.status = payload["status"]
    if payload.get("version") is not None:
        user.version = payload["version"]
    audit.record(db, actor, "staff_update", "app_user", user.id, before=before, after=_user_view(db, user))
    db.commit()
    return _user_view(db, user)


def disable_user(db: Session, actor: dict, user_id: int) -> dict:
    user = get_or_404(db, AppUser, user_id, "员工不存在")
    if user.id == actor.get("id"):
        raise Conflict("CANNOT_DISABLE_SELF", "不能停用当前登录账号")
    if user.is_super_admin:
        raise Forbidden("不能停用超级管理员", "PERM_FORBIDDEN")
    user.status = "DISABLED"
    audit.record(db, actor, "staff_disable", "app_user", user.id)
    db.commit()
    return _user_view(db, user)


def _replace_roles(db: Session, actor: dict, user: AppUser, role_codes: list[str]) -> None:
    db.execute(AppUserRole.__table__.delete().where(AppUserRole.user_id == user.id))
    for code in role_codes:
        role = db.execute(select(AppRole).where(AppRole.tenant_id == settings.tenant_id, AppRole.code == code)).scalar_one_or_none()
        if role is None:
            raise NotFound(f"角色 {code} 不存在")
        db.add(AppUserRole(user_id=user.id, role_id=role.id, granted_by=actor.get("id")))


def _replace_scopes(db: Session, user: AppUser, channel_ids: list[int]) -> None:
    db.execute(StaffChannelScope.__table__.delete().where(StaffChannelScope.user_id == user.id))
    for cid in channel_ids:
        db.add(StaffChannelScope(user_id=user.id, channel_account_id=cid))


def set_roles(db: Session, actor: dict, user_id: int, role_codes: list[str]) -> dict:
    user = get_or_404(db, AppUser, user_id, "员工不存在")
    if user.is_super_admin and not actor.get("is_super_admin"):
        raise Forbidden("不能修改超级管理员角色", "PERM_FORBIDDEN")
    _replace_roles(db, actor, user, role_codes)
    audit.record(db, actor, "staff_set_roles", "app_user", user.id, after={"roles": role_codes})
    db.commit()
    return _user_view(db, user)


def set_channel_scopes(db: Session, actor: dict, user_id: int, channel_ids: list[int]) -> dict:
    user = get_or_404(db, AppUser, user_id, "员工不存在")
    _replace_scopes(db, user, channel_ids)
    audit.record(db, actor, "staff_set_scopes", "app_user", user.id, after={"channel_ids": channel_ids})
    db.commit()
    return _user_view(db, user)


def list_roles(db: Session) -> dict:
    rows = db.execute(select(AppRole).where(AppRole.tenant_id == settings.tenant_id).order_by(AppRole.id)).scalars().all()
    result = []
    for role in rows:
        perms = db.execute(select(AppPermission.code).join(AppRolePermission, AppRolePermission.permission_id == AppPermission.id)
                           .where(AppRolePermission.role_id == role.id)).scalars().all()
        result.append({"id": role.id, "code": role.code, "name": role.name, "description": role.description,
                       "is_system": role.is_system, "permissions": list(perms)})
    return list_payload(result)


def list_permissions(db: Session) -> dict:
    rows = db.execute(select(AppPermission).order_by(AppPermission.module, AppPermission.code)).scalars().all()
    return list_payload([{"id": p.id, "code": p.code, "name": p.name, "module": p.module} for p in rows])


def _channel_view(c: ChannelAccount) -> dict:
    return {"id": c.id, "code": c.code, "name": c.name, "platform_code": c.platform_code,
            "channel_type": c.channel_type, "external_account_id": c.external_account_id,
            "commerce_enabled": c.commerce_enabled, "status": c.status}


def list_channels(db: Session) -> dict:
    rows = db.execute(select(ChannelAccount).where(ChannelAccount.tenant_id == settings.tenant_id).order_by(ChannelAccount.id)).scalars().all()
    return list_payload([_channel_view(c) for c in rows])


def create_channel(db: Session, actor: dict, payload: dict) -> dict:
    channel = ChannelAccount(tenant_id=settings.tenant_id, code=payload["code"], name=payload["name"],
                             platform_code=payload.get("platform_code") or payload["code"],
                             channel_type=payload.get("channel_type", "OTHER"),
                             external_account_id=payload.get("external_account_id"),
                             commerce_enabled=payload.get("commerce_enabled", True))
    db.add(channel)
    db.flush()
    audit.record(db, actor, "channel_create", "channel_account", channel.id, after={"code": channel.code})
    db.commit()
    return _channel_view(channel)


def update_channel(db: Session, actor: dict, channel_id: int, payload: dict) -> dict:
    channel = get_or_404(db, ChannelAccount, channel_id, "渠道不存在")
    before = _channel_view(channel)
    for field in ("name", "external_account_id", "commerce_enabled", "status", "platform_code"):
        if payload.get(field) is not None:
            setattr(channel, field, payload[field])
    audit.record(db, actor, "channel_update", "channel_account", channel.id, before=before, after=_channel_view(channel))
    db.commit()
    return _channel_view(channel)


def list_audit_logs(db: Session, *, page: int, page_size: int, resource_type: str | None = None,
                    action: str | None = None, actor_id: int | None = None) -> dict:
    stmt = select(AuditLog).where(AuditLog.tenant_id == settings.tenant_id)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    offset, limit = page_offset(page, page_size)
    rows = db.execute(stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(offset).limit(limit)).scalars().all()
    return {"page": page, "page_size": page_size, "total": total, "meta": {"page": page, "page_size": page_size, "total": total},
            "items": [
        {"id": a.id, "actor_type": a.actor_type, "actor_id": a.actor_id, "actor_label": a.actor_label,
         "action": a.action, "resource_type": a.resource_type, "resource_id": a.resource_id,
         "channel_account_id": a.channel_account_id, "before": a.before_data, "after": a.after_data,
         "before_data": a.before_data, "after_data": a.after_data,
         "ip": str(a.ip) if a.ip else None, "user_agent": a.user_agent,
         "request_id": a.request_id, "created_at": a.created_at.isoformat()} for a in rows]}


def list_public_channels(db: Session) -> list[dict]:
    """C 端可见渠道：仅返回启用且开启电商的渠道，供前端选择默认下单渠道。"""
    rows = db.execute(select(ChannelAccount).where(ChannelAccount.tenant_id == settings.tenant_id,
                                                   ChannelAccount.status == "ACTIVE",
                                                   ChannelAccount.commerce_enabled.is_(True))
                      .order_by(ChannelAccount.id)).scalars().all()
    return [{"id": row.id, "code": row.code, "name": row.name, "platform_code": row.platform_code,
             "channel_type": row.channel_type, "status": row.status,
             "is_default": row.code == "OFFICIAL_MALL"} for row in rows]
