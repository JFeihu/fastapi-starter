"""临时：对比两种 join 写法，看生成 SQL 和结果。"""

import asyncio

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Tag, Todo
from app.db.session import SessionLocal


async def yours(db: AsyncSession) -> None:
    print("=== 你的写法：join(Todo.tags) ===")
    stmt = (
        select(Tag.name, func.count(Todo.tags))
        .join(Todo.tags)
        .group_by(Tag.id, Tag.name)
        .order_by(func.count(Todo.tags).desc())
        .limit(5)
    )
    print(stmt.compile(compile_kwargs={"literal_binds": True}))
    try:
        rows = (await db.execute(stmt)).all()
        print("结果:", rows[:5])
    except Exception as exc:
        print("报错:", type(exc).__name__, exc)


async def reverse(db: AsyncSession) -> None:
    print("\n=== 反向关系：join(Tag.todos) ===")
    n = func.count().label("n")
    stmt = (
        select(Tag.name, n)
        .join(Tag.todos)
        .group_by(Tag.id, Tag.name)
        .order_by(n.desc())
        .limit(5)
    )
    print(stmt.compile(compile_kwargs={"literal_binds": True}))
    rows = (await db.execute(stmt)).all()
    print("结果:", rows)


async def main() -> None:
    async with SessionLocal() as db:
        await yours(db)
        await reverse(db)


asyncio.run(main())
