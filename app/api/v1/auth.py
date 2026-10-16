from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.errors import ValidationError
from app.models import AppUser
from app.schemas.views import (
    CurrentUser,
    PasswordChangeResult,
    TokenBundle,
    TokenPair,
)
from app.services import identity

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    """登录：username 或 mobile 至少提供一个（C 端前端使用 mobile）。"""

    username: str | None = Field(default=None, max_length=64)
    mobile: str | None = Field(default=None, max_length=32)
    password: str = Field(min_length=1, max_length=128)
    otp_code: str | None = None

    @property
    def identifier(self) -> str:
        value = self.username or self.mobile or ""
        if not value:
            raise ValidationError("缺少用户名或手机号")
        return value


class RegisterRequest(BaseModel):
    """客户注册：username/mobile 二选一，sms_code 仅开发环境忽略校验。"""

    username: str | None = Field(default=None, max_length=64)
    mobile: str | None = Field(default=None, max_length=32)
    phone: str | None = None
    password: str = Field(min_length=8, max_length=128)
    sms_code: str | None = None
    nickname: str | None = None
    display_name: str | None = None
    email: str | None = None
    channel_account_id: int | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class GuestRequest(BaseModel):
    display_name: str | None = None


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/staff/login", response_model=TokenPair)
def staff_login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    return identity.login_staff(db, payload.identifier, payload.password, request.headers.get("user-agent"))


@router.post("/customer/login", response_model=TokenPair)
def customer_login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    return identity.login_customer(db, payload.identifier, payload.password, request.headers.get("user-agent"))


@router.post("/customer/register", response_model=TokenPair)
def customer_register(payload: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    return identity.register_customer(db, payload.model_dump())


@router.post("/guest-session", response_model=TokenBundle)
def guest_session(payload: GuestRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    return identity.guest_session(db, payload.display_name, request.headers.get("user-agent"))


@router.post("/refresh", response_model=TokenBundle)
def refresh_token(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    return identity.refresh(db, payload.refresh_token, request.headers.get("user-agent"))


@router.post("/logout")
def logout(db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)) -> dict:
    return identity.logout(db, user)


@router.get("/me", response_model=CurrentUser)
def me(db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)) -> dict:
    return identity.me(db, user)


@router.post("/password/change", response_model=PasswordChangeResult)
def change_password(payload: PasswordChangeRequest, db: Session = Depends(get_db),
                    user: AppUser = Depends(get_current_user)) -> dict:
    return identity.change_password(db, user, payload.old_password, payload.new_password)
