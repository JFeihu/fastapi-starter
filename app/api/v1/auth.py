"""认证接口：注册、登录、刷新 token。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import DBSession
from app.core.config import settings
from app.core.security import create_token, decode_token
from app.schemas.user import Token, TokenRefresh, UserCreate, UserRead
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["认证"])

ACCESS_EXPIRES_IN = settings.access_token_expire_minutes * 60


def _build_token(user_id: int) -> Token:
    return Token(
        access_token=create_token(user_id, "access"),
        refresh_token=create_token(user_id, "refresh"),
        expires_in=ACCESS_EXPIRES_IN,
    )


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="注册",
)
async def register(payload: UserCreate, db: DBSession) -> UserRead:
    user = await user_service.create_user(db, payload)
    return UserRead.model_validate(user)


@router.post("/login", response_model=Token, summary="登录（表单格式，兼容 Swagger 授权）")
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DBSession,
) -> Token:
    user = await user_service.authenticate(db, form.username, form.password)
    return _build_token(user.id)


@router.post("/refresh", response_model=Token, summary="用 refresh token 换新 token")
async def refresh(payload: TokenRefresh, db: DBSession) -> Token:
    claims = decode_token(payload.refresh_token, expected_type="refresh")
    user = await user_service.get_user_by_id(db, int(claims["sub"]))
    return _build_token(user.id)
