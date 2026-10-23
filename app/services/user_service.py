"""用户相关业务逻辑。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import hash_password, verify_password
from app.db.models import User
from app.schemas.user import UserCreate


async def get_user_by_id(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        # 用户不存在/被禁用，对外都是"凭证无效"，不区分
        raise UnauthorizedError("用户不存在或已被禁用")
    return user


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, payload: UserCreate) -> User:
    # 先查一次给出友好提示；真正的唯一性由数据库唯一索引保证（并发下也安全）
    exists = await db.execute(
        select(User.id).where((User.username == payload.username) | (User.email == payload.email))
    )
    if exists.first():
        raise ConflictError("用户名或邮箱已被注册")

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    try:
        await db.flush()  # 拿到自增 id，事务由依赖层统一提交
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("用户名或邮箱已被注册") from exc
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, username: str, password: str) -> User:
    user = await get_user_by_username(db, username)
    # 用户不存在时也执行一次哈希校验，避免通过响应时间枚举用户名
    if user is None or not verify_password(password, user.hashed_password):
        raise UnauthorizedError("用户名或密码错误")
    if not user.is_active:
        raise UnauthorizedError("用户已被禁用")
    return user
