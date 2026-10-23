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

engine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo,
    pool_pre_ping=True,  # 取连接前先 ping，避免拿到已断开的连接
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


async def init_models() -> None:
    """开发期兜底建表；生产环境请用 alembic upgrade head。"""
    from app.db import models  # noqa: F401  确保模型已注册到 Base.metadata
    from app.db.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
