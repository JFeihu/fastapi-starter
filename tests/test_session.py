"""get_db 依赖的提交/回滚行为。

为什么值得单测：
这个依赖决定了"一个请求一个事务"的边界——写错了就是数据丢失或脏数据，
而接口测试很难触发"业务代码抛异常"这种场景。
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.session import get_db, engine


async def test_get_db_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    # 1 建一个字典当计数器
    calls = {"commit": 0, "rollback": 0}

    # 2 伪造假的 commit / rollback
    async def fake_commit(self: AsyncSession) -> None:
        calls["commit"] += 1

    async def fake_rollback(self: AsyncSession) -> None:
        calls["rollback"] += 1

    # 3. 偷梁换柱：把 AsyncSession 的 commit 和 rollback 替换掉
    # 注意：这里是改的类（AsyncSession），而不是改的实例。所以 fake_commit 里必须有 self
    monkeypatch.setattr(AsyncSession, "commit", fake_commit)
    monkeypatch.setattr(AsyncSession, "rollback", fake_rollback)

    # 4.拿到生成器对象
    agen = get_db()
    # 5. 驱使它执行到 yield 处（此时把 session 交给业务代码）
    await anext(agen)            # 拿到 yield 出去的 session
    # 6. 继续驱使它往下走（因为我们在 yield 后没抛出异常，正常结束）
    # 走到 get_db 的结尾，会触发 await session.commit()
    await anext(agen, None)      # 继续跑完 → commit 分支

    # 7.断言
    assert calls["commit"] == 1
    assert calls["rollback"] == 0


async def test_get_db_rolls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"commit": 0, "rollback": 0}

    async def fake_commit(self: AsyncSession) -> None:
        calls["commit"] += 1

    async def fake_rollback(self: AsyncSession) -> None:
        calls["rollback"] += 1

    monkeypatch.setattr(AsyncSession, "commit", fake_commit)
    monkeypatch.setattr(AsyncSession, "rollback", fake_rollback)

    agen = get_db()
    await anext(agen)

    # 核心区别：向生成器内部抛出异常，模拟业务代码报错
    # get_db 内部的 try...except 会捕获这个异常，执行 rollback
    with pytest.raises(RuntimeError, match="boom"):
        await agen.athrow(RuntimeError("boom"))   # 在 yield 处抛异常

    assert calls["rollback"] == 1
    assert calls["commit"] == 0

async def test_sqlite_foreign_keys_enabled() -> None:
    """SQLite 默认不校验外键，必须每个连接 PRAGMA 打开。

    这条测试是"意图测试"：证明我们真的开了外键，而不是假设它开着。
    """
    async with engine.connect() as conn:
        value = await conn.scalar(text("PRAGMA foreign_keys"))
    assert value == 1
