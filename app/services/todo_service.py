"""任务（Todo）相关业务逻辑：所有查询都带 owner_id，从根上防水平越权。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models import Todo
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
    )
    return list(result.scalars().all()), int(total or 0)


async def get_owned_todo(db: AsyncSession, todo_id: int, owner_id: int) -> Todo:
    todo = await db.get(Todo, todo_id)
    # 别人的资源统一返回 404，不暴露"存在但无权访问"
    if todo is None or todo.owner_id != owner_id:
        raise NotFoundError("任务不存在")
    return todo


async def create_todo(db: AsyncSession, payload: TodoCreate, owner_id: int) -> Todo:
    todo = Todo(**payload.model_dump(), owner_id=owner_id)
    db.add(todo)
    await db.flush()
    await db.refresh(todo)
    return todo


async def update_todo(db: AsyncSession, todo: Todo, payload: TodoUpdate) -> Todo:
    data = payload.model_dump(exclude_unset=True)  # 只更新客户端真正传了的字段
    for field, value in data.items():
        setattr(todo, field, value)
    await db.flush()
    await db.refresh(todo)
    return todo


async def delete_todo(db: AsyncSession, todo: Todo) -> None:
    await db.delete(todo)
    await db.flush()
