"""标签接口：路由只做「收参数 → 调 service → 返回」。"""

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DBSession
from app.schemas.tag import TagCreate, TagRead
from app.services import tag_service

router = APIRouter(prefix="/tags", tags=["标签"])


@router.post("", response_model=TagRead, status_code=status.HTTP_201_CREATED, summary="添加标签")
async def create_tag(payload: TagCreate, db: DBSession, current_user: CurrentUser) -> TagRead:
    tag = await tag_service.create_tag(db, payload, owner_id=current_user.id)
    return TagRead.model_validate(tag)


@router.get("", response_model=list[TagRead], summary="我的标签")
async def list_tags(db: DBSession, current_user: CurrentUser) -> list[TagRead]:
    tags = await tag_service.list_tags(db, owner_id=current_user.id)
    return [TagRead.model_validate(tag) for tag in tags]
