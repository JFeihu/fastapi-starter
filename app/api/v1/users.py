"""用户接口。"""

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.schemas.user import UserRead

router = APIRouter(prefix="/users", tags=["用户"])


@router.get("/me", response_model=UserRead, summary="当前登录用户")
async def read_me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)
