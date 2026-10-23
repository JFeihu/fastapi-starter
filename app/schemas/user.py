"""用户与 token 的出入参。

约定：所有 *Create / *Update 是入参，*Read 是出参；
出参永远不包含 hashed_password —— response_model 会做字段裁剪，这是防泄露的第一道闸。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

USERNAME_PATTERN = r"^[A-Za-z0-9_]{3,32}$"


class UserCreate(BaseModel):
    username: str = Field(pattern=USERNAME_PATTERN, examples=["alice"])
    email: EmailStr = Field(examples=["alice@example.com"])
    # bcrypt 最多处理 72 字节，超出会被静默截断，所以这里直接限制长度
    password: str = Field(min_length=8, max_length=72, examples=["S3cret-pass"])


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="access_token 有效期（秒）")


class TokenRefresh(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    sub: str
    type: str
    exp: int
