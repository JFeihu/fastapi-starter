"""Day 2 的测试：GET /api/v1/todos/stats（统计接口）

先让这些测试红着，再去实现三个地方：
    app/schemas/todo.py      → TodoStats 模型
    app/services/todo_service.py → get_stats()
    app/api/v1/todos.py      → @router.get("/stats")
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

API = "/api/v1/todos"


async def _create(client: AsyncClient, headers: dict[str, str], title: str) -> dict:
    resp = await client.post(API, json={"title": title}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_stats_empty(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    """没有任务时：全 0，完成率 0.0（不能除零崩掉）。"""
    resp = await client.get(f"{API}/stats", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json() == {"total": 0, "done": 0, "pending": 0, "completion_rate": 0.0}


async def test_stats_counts(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    first = await _create(client, auth_headers, "a")
    await _create(client, auth_headers, "b")
    await _create(client, auth_headers, "c")
    await client.patch(f"{API}/{first['id']}", json={"done": True}, headers=auth_headers)

    body = (await client.get(f"{API}/stats", headers=auth_headers)).json()

    assert body["total"] == 3
    assert body["done"] == 1
    assert body["pending"] == 2
    assert body["completion_rate"] == pytest.approx(1 / 3, rel=1e-3)


async def test_stats_only_counts_my_todos(
    client: AsyncClient, auth_headers: dict[str, str], other_headers: dict[str, str]
) -> None:
    """别人的任务不能算进来。"""
    await _create(client, auth_headers, "mine")
    await _create(client, other_headers, "his")
    await _create(client, other_headers, "his-2")

    body = (await client.get(f"{API}/stats", headers=auth_headers)).json()

    assert body["total"] == 1


async def test_stats_requires_auth(client: AsyncClient) -> None:
    resp = await client.get(f"{API}/stats")

    assert resp.status_code == 401


async def test_stats_not_shadowed_by_id_route(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """/stats 必须写在 /{todo_id} 之前，否则 "stats" 会被当成 id 解析 → 422。"""
    resp = await client.get(f"{API}/stats", headers=auth_headers)

    assert resp.status_code == 200, f"路由顺序错了：{resp.status_code} {resp.text}"
