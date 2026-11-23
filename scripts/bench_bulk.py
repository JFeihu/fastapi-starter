"""基准脚本：数一数批量创建到底发了几条 SQL（INSERT / SELECT 分开数）。

用法（在 fastapi-starter 目录）：
    uv run python scripts/bench_bulk.py          # 默认 50 条
    uv run python scripts/bench_bulk.py 500      # 指定条数

为什么要分开数：
    - INSERT 条数 = 你插了多少行（能不能批量，看这个）
    - SELECT 条数 = 你回读了多少次（refresh / 懒加载，看这个）

N+1 的代价是"往返次数"。本地 SQLite 快得看不出来，
但库在另一台机器时，每条语句就是一次网络往返。
"""

from __future__ import annotations

import asyncio
import sys
import time

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import User
from app.schemas.todo import TodoCreate
from app.services import todo_service

STATS = {"INSERT": 0, "SELECT": 0, "OTHER": 0}


def _count(conn, cursor, statement, params, context, executemany) -> None:  # noqa: ANN001
    """每条 SQL 发出前调用一次；executemany 时也只算一条。"""
    head = statement.lstrip().split(None, 1)[0].upper() if statement.strip() else ""
    STATS[head if head in STATS else "OTHER"] += 1


async def main(count: int) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    event.listens_for(engine.sync_engine, "before_cursor_execute")(_count)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        # 先造一个用户（todos.owner_id 有外键）
        owner = User(username="bench", email="bench@example.com", hashed_password="x" * 60)
        db.add(owner)
        await db.commit()
        await db.refresh(owner)

        items = [TodoCreate(title=f"任务 {i}") for i in range(count)]

        for key in STATS:
            STATS[key] = 0
        start = time.perf_counter()
        created, failed = await todo_service.bulk_create(
            db, items, owner_id=owner.id, atomic=True
        )
        await db.commit()
        cost = (time.perf_counter() - start) * 1000

        total = sum(STATS.values())
        print(
            f"条数 {count:<5} | 语句 {total:<5} | "
            f"INSERT {STATS['INSERT']:<4} | SELECT {STATS['SELECT']:<4} | "
            f"其他 {STATS['OTHER']:<3} | 耗时 {cost:7.1f}ms | "
            f"成功 {len(created)} 失败 {len(failed)}"
        )

    await engine.dispose()


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    asyncio.run(main(n))
