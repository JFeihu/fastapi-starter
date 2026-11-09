"""D6 练习：把前四天的手写 SQL，用 SQLAlchemy 2.0 写出来。

每道题都给了「手写 SQL」做对照，你要写的是等价的 ORM 代码。

用法：
    uv run python scripts/orm_practice.py            # 跑全部，看哪些还没做
    uv run python scripts/orm_practice.py 3          # 只跑第 3 题

写完之后建议打开 echo 看它生成的 SQL：
    $env:DB_ECHO="true"; uv run python scripts/orm_practice.py 3
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Tag, Todo
from app.db.session import SessionLocal


# ---------------------------------------------------------------- 练习 1
async def ex01(db: AsyncSession) -> int:
    """alice（owner_id=1）的已完成任务数。

    SQL: SELECT COUNT(*) FROM todos WHERE owner_id = 1 AND done = 1
    提示: select(func.count(Todo.id)).where(Todo.owner_id == 1, Todo.done.is_(True))
          → (await db.execute(stmt)).scalar_one()
    """
    stmt = select(func.count(Todo.id)).where(Todo.owner_id == 1, Todo.done.is_(True))
    return (await db.execute(stmt)).scalar_one()


# ---------------------------------------------------------------- 练习 2
async def ex02(db: AsyncSession) -> list[int]:
    """按 id 升序，第 11～20 条的 id 列表（分页）。

    SQL: SELECT id FROM todos ORDER BY id LIMIT 10 OFFSET 10
    提示: .order_by(Todo.id).offset(10).limit(10) → .scalars().all()
    """
    stmt = select(Todo.id).order_by(Todo.id).limit(10).offset(10)
    return (await db.execute(stmt)).scalars().all()


# ---------------------------------------------------------------- 练习 3
async def ex03(db: AsyncSession) -> list[tuple[int, int]]:
    """每个 owner_id 的任务数，按 owner_id 升序。

    SQL: SELECT owner_id, COUNT(*) FROM todos GROUP BY owner_id ORDER BY owner_id
    结果: [(1, 69721), (2, 30279)]
    提示: select(Todo.owner_id, func.count(Todo.id)).group_by(Todo.owner_id)
          → .all() 返回 Row 列表，转成 tuple
    """
    stmt = select(Todo.owner_id, func.count(Todo.id)).group_by(Todo.owner_id)
    rows = (await db.execute(stmt)).all()
    return [(row[0], row[1]) for row in rows]


# ---------------------------------------------------------------- 练习 4
async def ex04(db: AsyncSession) -> list[int]:
    """任务数超过 50000 的 owner_id 列表（HAVING）。

    SQL: SELECT owner_id FROM todos GROUP BY owner_id HAVING COUNT(*) > 50000
    结果: [1]
    提示: .having(func.count(Todo.id) > 50000)
    """
    stmt = select(Todo.owner_id).group_by(Todo.owner_id).having(func.count(Todo.owner_id) > 50000)
    return (await db.execute(stmt)).scalars().all()


# ---------------------------------------------------------------- 练习 5
async def ex05(db: AsyncSession) -> list[tuple[str, int]]:
    """被使用次数最多的 5 个标签：(标签名, 次数)。

    SQL: SELECT g.name, COUNT(*) AS n
         FROM tags g JOIN todo_tags tt ON tt.tag_id = g.id
         GROUP BY g.id, g.name ORDER BY n DESC LIMIT 5
    结果第一行: ("标签1-18", 2171)
    提示: Todo.tags 是 many-to-many 关系，可以直接 join(Todo.tags)；
          或直接 join Tag，手动指定 onclause。
    """
    stmt = (
        select(Tag.name, func.count())
        .join(Tag.todos)
        .group_by(Tag.id, Tag.name)
        .order_by(func.count().desc())
        .limit(5)
    )
    rows = (await db.execute(stmt)).all()
    return [(row[0], row[1]) for row in rows]


# ---------------------------------------------------------------- 练习 6
async def ex06(db: AsyncSession) -> list[tuple[str, list[str]]]:
    """id 最小的 3 条任务：(标题, 标签名列表)。

    SQL: SELECT t.title, g.name FROM todos t
         JOIN todo_tags tt ON tt.todo_id = t.id
         JOIN tags g ON g.id = tt.tag_id
         WHERE t.id <= 3 ORDER BY t.id
    结果: [("写迁移脚本 - 详情页 #410", ["标签1-13", "标签1-17"]),
           ("整理接口文档 - 统计页 #1680", ["标签1-06", "标签1-18", "标签1-02"])]  ← 只列前两条示意

    这题考「预加载」：异步下访问未加载的 todo.tags 会报 MissingGreenlet。
    提示: select(Todo).where(Todo.id <= 3).options(selectinload(Todo.tags)).order_by(Todo.id)
          注意标签顺序可能和 SQL 不同，比较时用集合。
    """
    stmt = select(Todo).where(Todo.id <= 3).options(selectinload(Todo.tags)).order_by(Todo.id)
    todos = (await db.execute(stmt)).scalars().all()
    return [(t.title, [tag.name for tag in t.tags]) for t in todos]


# ---------------------------------------------------------------- 练习 7
async def ex07(db: AsyncSession) -> int:
    """alice 已完成、且至少有一个标签的任务数。

    SQL: SELECT COUNT(DISTINCT t.id) FROM todos t
         JOIN todo_tags tt ON tt.todo_id = t.id
         JOIN tags g ON g.id = tt.tag_id
         WHERE t.owner_id = 1 AND t.done = 1
    结果: 8358
    提示: 用 Todo.tags.any()（EXISTS 子查询）或 join + distinct。
    """
    stmt = (
        select(func.count(distinct(Todo.id)))
        .join(Todo.tags)
        .where(Todo.owner_id == 1, Todo.done.is_(True))
    )
    return (await db.execute(stmt)).scalar_one()


# ---------------------------------------------------------------- 练习 8
async def ex08(db: AsyncSession) -> tuple[int, int]:
    """事务练习：批量插入 3 条任务，插入第 3 条时故意抛异常。

    要求：
    - 用 `async with db.begin_nested()`（SAVEPOINT）；
    - 异常之后回滚，**这 3 条都不能留在库里**；
    - 返回 (插入前数量, 异常后数量) —— 两个应该相等。

    提示：
        before = await db.scalar(select(func.count()).select_from(Todo))
        try:
            async with db.begin_nested():
                for i in range(3):
                    db.add(Todo(title=f"事务测试{i}", owner_id=1))
                    await db.flush()
                    if i == 2:
                        raise RuntimeError("故意失败")
        except RuntimeError:
            pass
        after = await db.scalar(select(func.count()).select_from(Todo))
        return before, after
    """
    before = await db.scalar(select(func.count()).select_from(Todo))
    try:
        async with db.begin_nested():
            for i in range(3):
                db.add(Todo(title=f"事务测试{i}", owner_id=1))
                await db.flush()
                if i == 2:
                    raise RuntimeError("故意失败")
    except RuntimeError:
        pass
    after = await db.scalar(select(func.count()).select_from(Todo))
    return before, after


# ---------------------------------------------------------------- 检查器
EXPECTED: dict[int, object] = {
    1: 27863,
    2: list(range(11, 21)),
    3: [(1, 69721), (2, 30279)],
    4: [1],
    5: [
        ("标签1-18", 2171),
        ("标签1-03", 2154),
        ("标签1-15", 2138),
        ("标签1-02", 2128),
        ("标签1-07", 2122),
    ],
    6: None,  # 用专门的比较函数
    7: 8358,
    8: None,  # before == after
}

EXERCISES: dict[int, Callable[[AsyncSession], Awaitable]] = {
    1: ex01,
    2: ex02,
    3: ex03,
    4: ex04,
    5: ex05,
    6: ex06,
    7: ex07,
    8: ex08,
}

EX06_EXPECTED = {
    "写迁移脚本 - 详情页 #410": {"标签1-13", "标签1-17"},
    "排查 500 错误 - 导出 #4013": set(),
    "整理接口文档 - 统计页 #1680": {"标签1-06", "标签1-18", "标签1-02"},
}

# 结构类题目的「期望形状」提示（结果对不上时打印，避免只看到 None）
SHAPE_HINT = {
    6: "[(标题, [标签名, ...]), ...]  —— 每个元素必须是「二元组」，第二个是列表",
    8: "(插入前数量, 异常后数量) —— 两个数应该相等",
}


def check(number: int, got: object) -> bool:
    try:
        if number == 6:
            data = dict(got)  # 元素不是二元组时这里会抛 ValueError
            return {k: set(v) for k, v in data.items()} == EX06_EXPECTED
        if number == 8:
            before, after = got  # type: ignore[misc]
            return before == after
    except (TypeError, ValueError):
        return False
    return got == EXPECTED[number]


async def main(only: int | None) -> None:
    numbers = [only] if only else list(EXERCISES)
    passed = 0
    async with SessionLocal() as db:
        for number in numbers:
            func_ = EXERCISES[number]
            title = (func_.__doc__ or "").strip().splitlines()[0]
            try:
                got = await func_(db)
            except NotImplementedError:
                print(f"  [TODO] 练习 {number}: 还没做 —— {title}")
                continue
            except Exception as exc:  # noqa: BLE001
                print(f"  [FAIL] 练习 {number}: 抛异常 {type(exc).__name__}: {exc}")
                continue

            if check(number, got):
                print(f"  [OK]   练习 {number}: {title}")
                passed += 1
            else:
                print(f"  [FAIL] 练习 {number}: 结果不对")
                if number in SHAPE_HINT:
                    print(f"      期望形状: {SHAPE_HINT[number]}")
                print(f"      你的: {got}")
                if number not in SHAPE_HINT:
                    print(f"      期望: {EXPECTED[number]}")

    print(f"\n{passed}/{len(numbers)} 通过")


if __name__ == "__main__":
    arg = int(sys.argv[1]) if len(sys.argv) > 1 else None
    asyncio.run(main(arg))
