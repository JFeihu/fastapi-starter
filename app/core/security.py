"""密码哈希与 JWT 签发/校验。

选型说明（面试常问）：
- 密码用 bcrypt：自带随机盐、可调 cost，慢哈希抗暴力破解；SHA256/MD5 不能用。
- token 用 PyJWT：比 python-jose 维护更活跃，API 更简单。
- bcrypt 只处理前 72 字节，超长密码要么限制长度（本项目 schema 已限制），要么先做 SHA256 预哈希。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import settings
from app.core.exceptions import UnauthorizedError

TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        # 数据库里的哈希格式损坏时不冒泡 500，按认证失败处理
        return False


def create_token(
    subject: str | int,
    token_type: TokenType = "access",
    expires_delta: timedelta | None = None,
) -> str:
    now = datetime.now(UTC)
    if expires_delta is None:
        expires_delta = (
            timedelta(minutes=settings.access_token_expire_minutes)
            if token_type == "access"
            else timedelta(days=settings.refresh_token_expire_days)
        )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str, expected_type: TokenType | None = None) -> dict[str, Any]:
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("登录已过期，请重新登录") from exc
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("无效的凭证") from exc

    if expected_type and payload.get("type") != expected_type:
        raise UnauthorizedError("凭证类型不正确")
    return payload
