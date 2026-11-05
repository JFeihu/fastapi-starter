"""Day 3 Part 1 的测试：标签的创建与查询（四层都要动）

要改的地方：
    app/db/models.py       → 新表 tags（含 owner_id、唯一约束）
    app/schemas/tags.py     → 新建：TagCreate / TagRead
    app/services/tag_service.py → 新建：create_tag / list_tags
    app/api/v1/tags.py     → 新建：POST /tags、GET /tags
    app/api/v1/router.py   → 把 tags 路由挂上去
"""

from __future__ import annotations

from httpx import AsyncClient

API = "/api/v1/tags"


async def _create(client: AsyncClient, headers: dict[str, str], name: str):
    return await client.post(API, json={"name": name}, headers=headers)


async def test_create_tag(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    resp = await _create(client, auth_headers, "工作")

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "工作"
    assert body["id"] > 0


async def test_duplicate_tag_name_conflicts(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """同一个用户不能有两个同名标签 → 409（不是 422，不是 500）。"""
    assert (await _create(client, auth_headers, "工作")).status_code == 201

    resp = await _create(client, auth_headers, "工作")

    assert resp.status_code == 409
    assert resp.json()["code"] == 40900


async def test_same_name_allowed_for_different_users(
    client: AsyncClient, auth_headers: dict[str, str], other_headers: dict[str, str]
) -> None:
    """标签属于个人，不同用户可以各有一个“工作”。"""
    assert (await _create(client, auth_headers, "工作")).status_code == 201
    assert (await _create(client, other_headers, "工作")).status_code == 201


async def test_list_tags_only_mine(
    client: AsyncClient, auth_headers: dict[str, str], other_headers: dict[str, str]
) -> None:
    await _create(client, auth_headers, "我的标签")
    await _create(client, other_headers, "别人的标签")

    resp = await client.get(API, headers=auth_headers)

    assert resp.status_code == 200
    assert [tag["name"] for tag in resp.json()] == ["我的标签"]


async def test_tags_require_auth(client: AsyncClient) -> None:
    assert (await client.get(API)).status_code == 401
    assert (await client.post(API, json={"name": "x"})).status_code == 401


async def test_tag_name_is_trimmed(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    """前后空格应被去掉：" 工作 " 存成 "工作"。"""
    resp = await _create(client, auth_headers, "  工作  ")

    assert resp.status_code == 201
    assert resp.json()["name"] == "工作"
