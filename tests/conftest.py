"""测试夹具：每个用例一个全新的内存数据库 + 独立 HTTP 客户端。

要点（面试常问「你怎么测接口」）：
1. 用 dependency_overrides 把 get_db 换成测试库，业务代码零改动；
2. SQLite 内存库必须用 StaticPool，否则每个连接看到的是不同的库；
3. 用 httpx.AsyncClient + ASGITransport，不需要真的起端口。
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app

TEST_PASSWORD = "S3cret-pass123"


@pytest_asyncio.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncClient]:
    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


async def register_user(
    client: AsyncClient,
    username: str = "alice",
    password: str = TEST_PASSWORD,
) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": password},
    )
    assert resp.status_code == 201, resp.text
    return {"username": username, "password": password}


async def login_headers(
    client: AsyncClient,
    username: str = "alice",
    password: str = TEST_PASSWORD,
) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    await register_user(client)
    return await login_headers(client)


@pytest_asyncio.fixture
async def other_headers(client: AsyncClient) -> dict[str, str]:
    await register_user(client, username="bob")
    return await login_headers(client, username="bob")
