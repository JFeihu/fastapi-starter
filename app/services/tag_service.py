"""标签（Tag）相关业务逻辑"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models import Tag
from app.schemas.tag import TagCreate


async def create_tag(db: AsyncSession, tag_in: TagCreate, *, owner_id: int) -> Tag:

    # 查重（前置防御）
    stmt = select(Tag).where(Tag.owner_id == owner_id, Tag.name == tag_in.name)
    existing_tag = await db.scalar(stmt)
    if existing_tag:
        # 如果该标签已经存在，直接抛出错误
        raise ConflictError("该标签已经存在")

    # 插入数据
    # 实例化 ORM 对象。注意：owner_id 绝不能从前端传，而是从 Token 或路由解析后传进来！
    tag = Tag(name=tag_in.name, owner_id=owner_id)
    db.add(tag)
    try:
        # flush 发送SQL到数据库
        await db.flush()
    except IntegrityError as exc:
        # 兜底防御（后置防御）
        await db.rollback()
        raise ConflictError("标签已存在（并发冲突）") from exc

    # 刷新实例
    await db.refresh(tag)
    return tag


async def list_tags(db: AsyncSession, *, owner_id: int) -> list[Tag]:
    """获取我的标签列表（按创建顺序）。"""
    result = await db.execute(select(Tag).where(Tag.owner_id == owner_id).order_by(Tag.id))
    return list(result.scalars().all())
