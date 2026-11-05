"""公共依赖：数据库会话、当前用户、分页参数。

依赖注入的意义：路由只声明"我需要什么"，至于怎么造出来（查库、解析 token、校验）
全部交给依赖，测试时还能用 app.dependency_overrides 一键替换。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.db.models import Todo, User
from app.db.session import get_db
from app.services import todo_service, user_service

# tokenUrl 决定 Swagger UI 上「Authorize」按钮请求哪个地址
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")

DBSession = Annotated[AsyncSession, Depends(get_db)]
TokenStr = Annotated[str, Depends(oauth2_scheme)]


async def get_current_user(db: DBSession, token: TokenStr) -> User:
    payload = security.decode_token(token, expected_type="access")
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise UnauthorizedError("凭证内容不合法") from exc
    return await user_service.get_user_by_id(db, user_id)


CurrentUser = Annotated[User, Depends(get_current_user)]


class Pagination:
    """把分页参数收拢成一个依赖，避免每个接口重复写 Query(...)。"""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="页码，从 1 开始"),
        size: int = Query(10, ge=1, le=100, description="每页条数，最大 100"),
    ) -> None:
        self.page = page
        self.size = size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


async def get_owned_todo(todo_id: int, db: DBSession, current_user: CurrentUser) -> Todo:
    """取任务 + 校验归属：拿不到就 404，拿到就注入"""

    return await todo_service.get_owned_todo(db, todo_id, current_user.id)


OwnedTodo = Annotated[Todo, Depends(get_owned_todo)]

PageParams = Annotated[Pagination, Depends()]
