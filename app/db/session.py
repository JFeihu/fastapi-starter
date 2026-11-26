"""异步引擎与会话。

关键点：
- 一个请求一个 Session，请求结束由依赖统一 commit / rollback（工作单元模式）；
- expire_on_commit=False：commit 后对象属性仍可直接读，避免响应序列化时触发懒加载（异步下会报错）。
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# SQLite 用的是 NullPool，不支持 pool_size/max_overflow；
# 只有 PostgreSQL/MySQL 这类网络数据库才需要调池子。
_pool_kwargs: dict[str, int] = {}
if not settings.database_url.startswith("sqlite"):
    _pool_kwargs = {
        "pool_size": 10,       # 常驻连接（默认 5，并发下不够）
        "max_overflow": 20,    # 峰值可额外开 20 个
        "pool_timeout": 5,     # 拿不到连接最多等 5 秒 → 快速失败，比挂 10 秒好
    }

engine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo,
    pool_pre_ping=True,  # 取连接前先 ping，避免拿到已断开的连接
    **_pool_kwargs,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_conn, _record) -> None:
        # SQLite 默认不启用外键约束，必须每个连接手动打开
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：为每个请求提供一个会话，并负责事务边界。"""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_models() -> None:  # pragma: no cover
    """开发期兜底建表；生产环境请用 alembic upgrade head。"""
    from app.db import models  # noqa: F401  确保模型已注册到 Base.metadata
    from app.db.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
