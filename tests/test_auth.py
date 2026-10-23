"""认证相关用例：正常、边界、异常三类都要覆盖。"""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import TEST_PASSWORD, login_headers, register_user


async def test_register_success(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "carol", "email": "carol@example.com", "password": TEST_PASSWORD},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "carol"
    assert "hashed_password" not in body  # response_model 裁剪敏感字段
    assert "password" not in body


async def test_register_duplicate_username(client: AsyncClient) -> None:
    await register_user(client, username="dave")
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "dave", "email": "other@example.com", "password": TEST_PASSWORD},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == 40900


async def test_register_weak_password(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "weak", "email": "weak@example.com", "password": "123"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == 42200
    assert resp.json()["detail"][0]["field"] == "password"


async def test_login_success(client: AsyncClient) -> None:
    await register_user(client)
    resp = await client.post(
        "/api/v1/auth/login", data={"username": "alice", "password": TEST_PASSWORD}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]


async def test_login_wrong_password(client: AsyncClient) -> None:
    await register_user(client)
    resp = await client.post(
        "/api/v1/auth/login", data={"username": "alice", "password": "wrong-password"}
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == 40100


async def test_me_requires_token(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401


async def test_me_with_token(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    resp = await client.get("/api/v1/users/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "alice"


async def test_me_with_invalid_token(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/users/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 401


async def test_refresh_token(client: AsyncClient) -> None:
    await register_user(client)
    login = await client.post(
        "/api/v1/auth/login", data={"username": "alice", "password": TEST_PASSWORD}
    )
    refresh_token = login.json()["refresh_token"]

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    new_access = resp.json()["access_token"]

    me = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me.status_code == 200


async def test_access_token_cannot_be_used_to_refresh(client: AsyncClient) -> None:
    """access token 拿来刷新必须失败：靠 payload 里的 type 字段区分。"""
    await register_user(client)
    login = await client.post(
        "/api/v1/auth/login", data={"username": "alice", "password": TEST_PASSWORD}
    )
    access = login.json()["access_token"]
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": access})
    assert resp.status_code == 401


async def test_login_with_nonexistent_user(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/login", data={"username": "nobody", "password": TEST_PASSWORD}
    )
    assert resp.status_code == 401


async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_request_id_header(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert len(resp.headers["X-Request-ID"]) == 32
    assert resp.headers["X-Process-Time"].endswith("ms")


async def test_login_headers_helper(client: AsyncClient) -> None:
    await register_user(client)
    headers = await login_headers(client)
    assert headers["Authorization"].startswith("Bearer ")
