"""Day 4 Part B 的测试：批量创建任务（原子 vs 部分成功）

接口：POST /api/v1/todos/bulk
请求：{"items": [{"title": "...", "tag_ids": [1]}, ...], "atomic": false}
响应：{"created": [TodoRead, ...], "failed": [{"index": 1, "error": "标签不存在"}]}
"""

from __future__ import annotations

from httpx import AsyncClient

TODOS = "/api/v1/todos"
BULK = f"{TODOS}/bulk"
TAGS = "/api/v1/tags"


async def _tag(client: AsyncClient, headers: dict[str, str], name: str) -> int:
    resp = await client.post(TAGS, json={"name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_bulk_all_success(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    resp = await client.post(
        BULK,
        json={"items": [{"title": f"t{i}"} for i in range(3)]},
        headers=auth_headers,
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body["created"]) == 3
    assert body["failed"] == []


async def test_bulk_partial_success_keeps_good_ones(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """atomic=False：好的一条留下，坏的记进 failed，接口本身不报错。"""
    good = await _tag(client, auth_headers, "工作")

    resp = await client.post(
        BULK,
        json={
            "items": [
                {"title": "ok-1", "tag_ids": [good]},
                {"title": "bad", "tag_ids": [99999]},  # 不存在的标签
                {"title": "ok-2", "tag_ids": [good]},
            ],
            "atomic": False,
        },
        headers=auth_headers,
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert [t["title"] for t in body["created"]] == ["ok-1", "ok-2"]
    assert len(body["failed"]) == 1
    assert body["failed"][0]["index"] == 1

    # 关键：成功的那两条真的入库了
    listed = await client.get(TODOS, headers=auth_headers)
    assert sorted(item["title"] for item in listed.json()["items"]) == ["ok-1", "ok-2"]


async def test_bulk_atomic_rolls_back_everything(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """atomic=True：第 2 条失败 → 整体回滚，第 1 条也不能留下。"""
    good = await _tag(client, auth_headers, "工作")

    resp = await client.post(
        BULK,
        json={
            "items": [
                {"title": "ok-1", "tag_ids": [good]},
                {"title": "bad", "tag_ids": [99999]},
            ],
            "atomic": True,
        },
        headers=auth_headers,
    )

    assert resp.status_code == 404

    listed = await client.get(TODOS, headers=auth_headers)
    assert listed.json()["items"] == []  # 一条都没留下


async def test_bulk_rejects_empty_items(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    resp = await client.post(BULK, json={"items": []}, headers=auth_headers)

    assert resp.status_code == 422


async def test_bulk_rejects_too_many_items(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    items = [{"title": f"t{i}"} for i in range(51)]

    resp = await client.post(BULK, json={"items": items}, headers=auth_headers)

    assert resp.status_code == 422


async def test_bulk_not_shadowed_by_id_route(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """/bulk 必须写在 /{todo_id} 之前，否则 "bulk" 会被当成 id。"""
    resp = await client.post(BULK, json={"items": [{"title": "x"}]}, headers=auth_headers)

    assert resp.status_code == 201, f"路由顺序错了：{resp.status_code} {resp.text}"
