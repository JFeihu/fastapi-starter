"""任务（Todo）相关业务逻辑：所有查询都带 owner_id，从根上防水平越权。"""

from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.db.models import Todo, Tag
from app.schemas import tag
from app.schemas.todo import TodoCreate, TodoUpdate


async def list_todos(
    db: AsyncSession,
    *,
    owner_id: int,
    page: int,
    size: int,
    done: bool | None = None,
    keyword: str | None = None,
) -> tuple[list[Todo], int]:
    conditions = [Todo.owner_id == owner_id]
    if done is not None:
        conditions.append(Todo.done.is_(done))
    if keyword:
        conditions.append(Todo.title.ilike(f"%{keyword}%"))

    total = await db.scalar(select(func.count()).select_from(Todo).where(*conditions))
    result = await db.execute(
        select(Todo)
        .where(*conditions)
        .order_by(Todo.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .options(selectinload(Todo.tags))
    )
    return list(result.scalars().all()), int(total or 0)


async def get_owned_todo(db: AsyncSession, todo_id: int, owner_id: int) -> Todo:
    result = await db.execute(
        select(Todo).where(Todo.id == todo_id, Todo.owner_id == owner_id).options(selectinload(Todo.tags))
    )
    todo = result.scalar_one_or_none()
    # 别人的资源统一返回 404，不暴露"存在但无权访问"
    if todo is None or todo.owner_id != owner_id:
        raise NotFoundError("任务不存在")
    return todo


async def create_todo(db: AsyncSession, payload: TodoCreate, owner_id: int) -> Todo:
    tags: list[Tag] = []
    if payload.tag_ids:
        result = await db.execute(
            select(Tag).where(Tag.id.in_(payload.tag_ids), Tag.owner_id == owner_id)
        )
        tags = list(result.scalars().all())
        if len(tags) != len(set(payload.tag_ids)):
            raise  NotFoundError("标签不存在")  # 别人的标签
    todo = Todo(
        title=payload.title,
        description=payload.description,
        done= payload.done,
        owner_id=owner_id,
        tags=tags
    )
    # todo = Todo(title=..., description=)
    db.add(todo)
    await db.flush()
    await db.refresh(todo, ["id", "created_at", "updated_at", "tags"])
    return todo


async def update_todo(db: AsyncSession, todo: Todo, payload: TodoUpdate) -> Todo:
    data = payload.model_dump(exclude_unset=True)  # 只更新客户端真正传了的字段
    for field, value in data.items():
        setattr(todo, field, value)
    await db.flush()
    await db.refresh(todo, ["id", "created_at", "updated_at", "tags"])
    return todo


async def delete_todo(db: AsyncSession, todo: Todo) -> None:
    await db.delete(todo)
    await db.flush()


# 获取 项目完成状态的数量
async def get_stats(db: AsyncSession, *, owner_id: int) -> dict:
    stmt = select(
        func.count(Todo.id),  # 统计数量
        func.sum(case((Todo.done.is_(True), 1), else_=0)),  # done=True的数量
    ).where(Todo.owner_id == owner_id)

    total, done = (await db.execute(stmt)).one()
    total = int(total or 0)
    done = int(done or 0)

    return {
        "total": total,
        "done": done,
        "pending": total - done,
        "completion_rate": round(done / total, 4) if total else 0.0,
    }
