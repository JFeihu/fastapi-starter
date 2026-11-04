"""任务接口：路由只做「收参数 → 调 service → 返回」。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, DBSession, PageParams
from app.schemas.common import Page
from app.schemas.todo import TodoCreate, TodoRead, TodoUpdate, TodoStats
from app.services import todo_service

router = APIRouter(prefix="/todos", tags=["任务"])


@router.post("", response_model=TodoRead, status_code=status.HTTP_201_CREATED, summary="创建任务")
async def create_todo(payload: TodoCreate, db: DBSession, current_user: CurrentUser) -> TodoRead:
    todo = await todo_service.create_todo(db, payload, owner_id=current_user.id)
    return TodoRead.model_validate(todo)


@router.get("", response_model=Page[TodoRead], summary="我的任务（分页/过滤/搜索）")
async def list_todos(
    db: DBSession,
    current_user: CurrentUser,
    pagination: PageParams,
    done: Annotated[bool | None, Query(description="按完成状态过滤")] = None,
    keyword: Annotated[str | None, Query(max_length=50, description="按标题模糊搜索")] = None,
) -> Page[TodoRead]:
    items, total = await todo_service.list_todos(
        db,
        owner_id=current_user.id,
        page=pagination.page,
        size=pagination.size,
        done=done,
        keyword=keyword,
    )
    return Page[TodoRead](
        items=[TodoRead.model_validate(item) for item in items],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.get("/stats", response_model=TodoStats, summary="任务统计")
async def get_todo_stats(db: DBSession, current_user: CurrentUser) -> TodoStats:
    data = await todo_service.get_stats(db, owner_id=current_user.id)
    return TodoStats(**data)


@router.get("/{todo_id}", response_model=TodoRead, summary="任务详情")
async def get_todo(todo_id: int, db: DBSession, current_user: CurrentUser) -> TodoRead:
    todo = await todo_service.get_owned_todo(db, todo_id, current_user.id)
    return TodoRead.model_validate(todo)


@router.patch("/{todo_id}", response_model=TodoRead, summary="局部更新任务")
async def update_todo(
    todo_id: int, payload: TodoUpdate, db: DBSession, current_user: CurrentUser
) -> TodoRead:
    todo = await todo_service.get_owned_todo(db, todo_id, current_user.id)
    todo = await todo_service.update_todo(db, todo, payload)
    return TodoRead.model_validate(todo)


@router.delete(
    "/{todo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除任务",
)
async def delete_todo(todo_id: int, db: DBSession, current_user: CurrentUser) -> Response:
    todo = await todo_service.get_owned_todo(db, todo_id, current_user.id)
    await todo_service.delete_todo(db, todo)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

