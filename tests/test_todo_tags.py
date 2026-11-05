"""Day 4 Part A 的测试：任务挂标签（多对多）

要改的地方：
    app/db/models.py       → todo_tags 中间表 + Todo.tags / Tag.todos 关系
    app/schemas/todo.py    → TodoCreate.tag_ids、TodoRead.tags
    app/services/todo_service.py → 创建时关联标签；查询时预加载 tags
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import event

TODOS = "/api/v1/todos"
TAGS = "/api/v1/tags"


async def _tag(client: AsyncClient, headers: dict[str, str], name: str) -> int:
    resp = await client.post(TAGS, json={"name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_create_todo_with_tags(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    work = await _tag(client, auth_headers, "工作")
    urgent = await _tag(client, auth_headers, "紧急")

    resp = await client.post(
        TODOS,
        json={"title": "修 bug", "tag_ids": [work, urgent]},
        headers=auth_headers,
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert sorted(tag["name"] for tag in body["tags"]) == ["工作", "紧急"]


async def test_todo_without_tags(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    resp = await client.post(TODOS, json={"title": "无标签"}, headers=auth_headers)

    assert resp.status_code == 201
    assert resp.json()["tags"] == []


async def test_cannot_attach_others_tag(
    client: AsyncClient, auth_headers: dict[str, str], other_headers: dict[str, str]
) -> None:
    """用别人的标签 id 创建任务 → 404（不能因为猜 id 就把别人的标签挂上）。"""
    other_tag = await _tag(client, other_headers, "别人的")

    resp = await client.post(
        TODOS, json={"title": "越权", "tag_ids": [other_tag]}, headers=auth_headers
    )

    assert resp.status_code == 404


async def test_unknown_tag_returns_404(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.post(
        TODOS, json={"title": "x", "tag_ids": [99999]}, headers=auth_headers
    )

    assert resp.status_code == 404


async def test_list_todos_includes_tags(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    tag_id = await _tag(client, auth_headers, "工作")
    await client.post(
        TODOS, json={"title": "带标签", "tag_ids": [tag_id]}, headers=auth_headers
    )

    resp = await client.get(TODOS, headers=auth_headers)

    assert resp.status_code == 200
    items = resp.json()["items"]
    assert [tag["name"] for tag in items[0]["tags"]] == ["工作"]


async def test_detail_includes_tags(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    tag_id = await _tag(client, auth_headers, "工作")
    created = await client.post(
        TODOS, json={"title": "详情", "tag_ids": [tag_id]}, headers=auth_headers
    )
    todo_id = created.json()["id"]

    resp = await client.get(f"{TODOS}/{todo_id}", headers=auth_headers)

    assert resp.status_code == 200
    assert [tag["name"] for tag in resp.json()["tags"]] == ["工作"]


async def test_list_todos_avoids_n_plus_1(
    client: AsyncClient, auth_headers: dict[str, str], session_factory
) -> None:
    """列出 5 个带标签的任务，SQL 条数不能随任务数增长（防 N+1 回归）。

    预期：登录查用户 1 条 + 总数 1 条 + 任务 1 条 + 标签 1 条 = 4 条 SELECT。
    如果去掉 selectinload，会变成 4 + 5 = 9 条，这个测试就会失败。
    """
    tag_id = await _tag(client, auth_headers, "工作")
    for i in range(5):
        await client.post(
            TODOS, json={"title": f"t{i}", "tag_ids": [tag_id]}, headers=auth_headers
        )

    statements: list[str] = []

    def record(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        statements.append(statement)

    engine = session_factory.kw["bind"].sync_engine
    event.listen(engine, "before_cursor_execute", record)
    try:
        statements.clear()
        resp = await client.get(TODOS, headers=auth_headers)
    finally:
        event.remove(engine, "before_cursor_execute", record)

    assert resp.status_code == 200
    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    assert len(selects) <= 5, (
        f"疑似 N+1：{len(selects)} 条 SELECT\n" + "\n".join(selects)
    )
