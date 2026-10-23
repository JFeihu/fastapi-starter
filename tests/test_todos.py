"""任务接口用例：CRUD、分页、过滤、权限隔离。"""

from __future__ import annotations

from httpx import AsyncClient

API = "/api/v1/todos"


async def _create(client: AsyncClient, headers: dict[str, str], title: str = "task-1") -> dict:
    resp = await client.post(API, json={"title": title}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_todo(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    todo = await _create(client, auth_headers)
    assert todo["title"] == "task-1"
    assert todo["done"] is False
    assert todo["id"] > 0


async def test_create_todo_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(API, json={"title": "x"})
    assert resp.status_code == 401


async def test_create_todo_empty_title(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    resp = await client.post(API, json={"title": ""}, headers=auth_headers)
    assert resp.status_code == 422


async def test_list_with_pagination(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    for i in range(15):
        await _create(client, auth_headers, title=f"task-{i}")

    resp = await client.get(API, params={"page": 2, "size": 10}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 15
    assert body["page"] == 2
    assert len(body["items"]) == 5
    # 按 id 倒序：15 条数据第 2 页是 5,4,3,2,1
    assert [item["id"] for item in body["items"]] == [5, 4, 3, 2, 1]


async def test_list_filter_by_done(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    first = await _create(client, auth_headers, title="done-task")
    await _create(client, auth_headers, title="open-task")
    await client.patch(f"{API}/{first['id']}", json={"done": True}, headers=auth_headers)

    resp = await client.get(API, params={"done": "true"}, headers=auth_headers)
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["title"] == "done-task"


async def test_list_search_by_keyword(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    await _create(client, auth_headers, title="学习 FastAPI")
    await _create(client, auth_headers, title="写周报")

    resp = await client.get(API, params={"keyword": "fastapi"}, headers=auth_headers)
    assert resp.json()["total"] == 1


async def test_update_partial(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    todo = await _create(client, auth_headers, title="old")
    resp = await client.patch(f"{API}/{todo['id']}", json={"done": True}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["done"] is True
    assert resp.json()["title"] == "old"  # 未传的字段保持不变


async def test_delete_todo(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    todo = await _create(client, auth_headers)
    resp = await client.delete(f"{API}/{todo['id']}", headers=auth_headers)
    assert resp.status_code == 204

    resp = await client.get(f"{API}/{todo['id']}", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["code"] == 40400


async def test_cannot_read_other_users_todo(
    client: AsyncClient, auth_headers: dict[str, str], other_headers: dict[str, str]
) -> None:
    todo = await _create(client, auth_headers, title="alice-only")

    resp = await client.get(f"{API}/{todo['id']}", headers=other_headers)
    assert resp.status_code == 404  # 不返回 403，避免暴露资源是否存在


async def test_cannot_delete_other_users_todo(
    client: AsyncClient, auth_headers: dict[str, str], other_headers: dict[str, str]
) -> None:
    todo = await _create(client, auth_headers)
    resp = await client.delete(f"{API}/{todo['id']}", headers=other_headers)
    assert resp.status_code == 404

    # 原主人仍然能读到
    assert (await client.get(f"{API}/{todo['id']}", headers=auth_headers)).status_code == 200


async def test_list_only_returns_own_todos(
    client: AsyncClient, auth_headers: dict[str, str], other_headers: dict[str, str]
) -> None:
    await _create(client, auth_headers, title="alice-task")
    await _create(client, other_headers, title="bob-task")

    resp = await client.get(API, headers=auth_headers)
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["title"] == "alice-task"


async def test_size_limit(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    resp = await client.get(API, params={"size": 1000}, headers=auth_headers)
    assert resp.status_code == 422
