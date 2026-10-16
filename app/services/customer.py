from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import Forbidden, NotFound, ValidationError
from app.models import AppUser, CustomerAddress, CustomerProfile, Order
from app.services import audit
from app.services.common import get_or_404, money, now, page_offset


def mask_mobile(value: str | None) -> str | None:
    """手机号脱敏：138****0001。"""
    if not value:
        return None
    digits = str(value)
    if len(digits) < 7:
        return "***"
    return digits[:3] + "****" + digits[-4:]


def profile_of(db: Session, user: AppUser) -> CustomerProfile:
    profile = db.execute(select(CustomerProfile).where(CustomerProfile.user_id == user.id)).scalar_one_or_none()
    if profile is None:
        profile = CustomerProfile(tenant_id=settings.tenant_id, user_id=user.id, nickname=user.display_name, real_name=user.display_name)
        db.add(profile)
        db.commit()
    return profile


def _profile_view(db: Session, profile: CustomerProfile) -> dict:
    user = db.get(AppUser, profile.user_id)
    phone = user.phone if user else None
    return {
        "id": profile.id, "user_id": profile.user_id, "customer_no": f"CU{profile.id:06d}",
        "username": user.username if user else None,
        "display_name": user.display_name if user else None,
        "phone": phone, "phone_masked": mask_mobile(phone), "mobile_masked": mask_mobile(phone),
        "email": user.email if user else None, "nickname": profile.nickname, "real_name": profile.real_name,
        "gender": profile.gender, "birthday": profile.birthday.isoformat() if profile.birthday else None,
        "default_channel_id": profile.default_channel_id, "channel_account_id": profile.default_channel_id,
        "tags": profile.tags or [],
        "total_order_count": profile.total_order_count, "total_paid_amount": money(profile.total_paid_amount),
        "last_order_at": profile.last_order_at.isoformat() if profile.last_order_at else None,
        "remark": profile.remark, "status": "ACTIVE",
    }


def _address_view(a: CustomerAddress) -> dict:
    return {"id": a.id, "customer_id": a.customer_id, "receiver_name": a.receiver_name,
            "receiver_phone": a.receiver_phone, "receiver_mobile": a.receiver_phone,
            "receiver_mobile_masked": mask_mobile(a.receiver_phone),
            "province": a.province, "city": a.city, "district": a.district, "detail": a.detail,
            "postal_code": a.postal_code, "is_default": a.is_default, "status": a.status,
            "full_address": f"{a.province}{a.city}{a.district}{a.detail}"}


def list_customers(db: Session, *, page: int, page_size: int, keyword: str | None = None) -> dict:
    stmt = select(CustomerProfile, AppUser).join(AppUser, AppUser.id == CustomerProfile.user_id).where(CustomerProfile.tenant_id == settings.tenant_id)
    if keyword:
        stmt = stmt.where(or_(AppUser.username.ilike(f"%{keyword}%"), AppUser.phone.ilike(f"%{keyword}%"), AppUser.display_name.ilike(f"%{keyword}%")))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    offset, limit = page_offset(page, page_size)
    rows = db.execute(stmt.order_by(CustomerProfile.id.desc()).offset(offset).limit(limit)).all()
    return {"page": page, "page_size": page_size, "total": total, "meta": {"page": page, "page_size": page_size, "total": total},
            "items": [_profile_view(db, p) for p, _ in rows]}


def get_customer(db: Session, customer_id: int) -> dict:
    profile = get_or_404(db, CustomerProfile, customer_id, "客户不存在")
    data = _profile_view(db, profile)
    addresses = db.execute(select(CustomerAddress).where(CustomerAddress.customer_id == profile.id,
                                                        CustomerAddress.status == "ACTIVE").order_by(CustomerAddress.is_default.desc(), CustomerAddress.id)).scalars().all()
    data["addresses"] = [_address_view(a) for a in addresses]
    return data


def update_customer(db: Session, actor: dict, customer_id: int, payload: dict) -> dict:
    profile = get_or_404(db, CustomerProfile, customer_id, "客户不存在")
    before = _profile_view(db, profile)
    for field in ("nickname", "real_name", "remark", "gender", "birthday", "tags", "default_channel_id"):
        if payload.get(field) is not None:
            setattr(profile, field, payload[field])
    audit.record(db, actor, "customer_update", "customer", profile.id, before=before, after=_profile_view(db, profile))
    db.commit()
    return _profile_view(db, profile)


def list_addresses(db: Session, user: AppUser, customer_id: int | None = None) -> list[dict]:
    profile = profile_of(db, user) if customer_id is None else get_or_404(db, CustomerProfile, customer_id, "客户不存在")
    addresses = db.execute(select(CustomerAddress).where(CustomerAddress.customer_id == profile.id,
                                                        CustomerAddress.status == "ACTIVE").order_by(CustomerAddress.is_default.desc(), CustomerAddress.id)).scalars().all()
    return [_address_view(a) for a in addresses]


def create_address(db: Session, actor: dict, payload: dict, customer_id: int | None = None, user: AppUser | None = None) -> dict:
    profile = get_or_404(db, CustomerProfile, customer_id, "客户不存在") if customer_id else profile_of(db, user)
    if payload.get("is_default"):
        for a in db.execute(select(CustomerAddress).where(CustomerAddress.customer_id == profile.id, CustomerAddress.is_default.is_(True))).scalars().all():
            a.is_default = False
    phone = payload.get("receiver_mobile") or payload.get("receiver_phone")
    if not phone:
        raise ValidationError("缺少收件人手机号")
    address = CustomerAddress(
        tenant_id=settings.tenant_id, customer_id=profile.id, receiver_name=payload["receiver_name"],
        receiver_phone=phone, province=payload["province"], city=payload["city"],
        district=payload["district"], detail=payload["detail"], postal_code=payload.get("postal_code"),
        is_default=bool(payload.get("is_default")),
    )
    db.add(address)
    db.flush()
    audit.record(db, actor, "address_create", "customer_address", address.id, after=_address_view(address))
    db.commit()
    return _address_view(address)


def update_address(db: Session, actor: dict, address_id: int, payload: dict, *, customer_ids: list[int] | None = None) -> dict:
    address = get_or_404(db, CustomerAddress, address_id, "地址不存在")
    if customer_ids is not None and address.customer_id not in customer_ids:
        raise Forbidden("无权修改他人地址", "RESOURCE_FORBIDDEN")
    before = _address_view(address)
    if payload.get("is_default"):
        for a in db.execute(select(CustomerAddress).where(CustomerAddress.customer_id == address.customer_id, CustomerAddress.is_default.is_(True))).scalars().all():
            a.is_default = False
    if payload.get("receiver_mobile") is not None:
        address.receiver_phone = payload["receiver_mobile"]
    for field in ("receiver_name", "receiver_phone", "province", "city", "district", "detail", "postal_code", "is_default"):
        if payload.get(field) is not None:
            setattr(address, field, payload[field])
    audit.record(db, actor, "address_update", "customer_address", address.id, before=before, after=_address_view(address))
    db.commit()
    return _address_view(address)


def delete_address(db: Session, actor: dict, address_id: int, *, customer_ids: list[int] | None = None) -> dict:
    address = get_or_404(db, CustomerAddress, address_id, "地址不存在")
    if customer_ids is not None and address.customer_id not in customer_ids:
        raise Forbidden("无权删除他人地址", "RESOURCE_FORBIDDEN")
    address.status = "DELETED"
    address.is_default = False
    audit.record(db, actor, "address_delete", "customer_address", address.id)
    db.commit()
    return {"id": address_id, "deleted": True}


def customer_orders(db: Session, customer_id: int, *, page: int, page_size: int) -> dict:
    stmt = select(Order).where(Order.customer_id == customer_id).order_by(Order.created_at.desc())
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    offset, limit = page_offset(page, page_size)
    rows = db.execute(stmt.offset(offset).limit(limit)).scalars().all()
    return {"page": page, "page_size": page_size, "total": total, "meta": {"page": page, "page_size": page_size, "total": total},
            "items": [{"id": o.id, "order_no": o.order_no, "status": o.status, "payment_status": o.payment_status,
                       "fulfillment_status": o.fulfillment_status, "payable_amount": money(o.payable_amount),
                       "created_at": o.created_at.isoformat()} for o in rows]}


def touch_order_stats(db: Session, customer_id: int, paid_amount) -> None:
    profile = db.get(CustomerProfile, customer_id)
    if profile is None:
        return
    profile.total_order_count = (profile.total_order_count or 0) + 1
    profile.total_paid_amount = (profile.total_paid_amount or 0) + (paid_amount or 0)
    profile.last_order_at = now()
