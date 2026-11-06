"""Day 5：错误契约测试

验证"所有错误响应长一个样"：{"code": 业务码, "message": 人话, "detail": 可选}。

覆盖 FastAPI 的四层异常链：
    ① AppError                → 业务异常（404/409/...）
    ② RequestValidationError  → 参数校验失败（422）
    ③ StarletteHTTPException  → 框架级（404 路由不存在、405 方法不对）
    ④ Exception               → 兜底（500，且不泄露内部信息）
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

API = "/api/v1/todos"


async def test_unknown_route_returns_404_envelope(client: AsyncClient) -> None:
    """③ 路由不存在：走 Starlette 的 HTTPException，code = 状态码 × 100。"""
    resp = await client.get("/api/v1/does-not-exist")

    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == 40400
    assert body["message"]


async def test_method_not_allowed_returns_405_envelope(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """③ 路径存在、方法不支持 → 405。

    注意带 token：不带的话会先撞 401，测不到 405。
    """
    resp = await client.delete(API, headers=auth_headers)

    assert resp.status_code == 405
    assert resp.json()["code"] == 40500


async def test_missing_token_returns_401_envelope(client: AsyncClient) -> None:
    """缺少 Authorization 头 → 401，走统一信封。"""
    resp = await client.get(API)

    assert resp.status_code == 401
    assert resp.json()["code"] == 40100


async def test_validation_error_lists_fields(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """② 参数校验失败：422 + 把 pydantic 的报错压平成 field/msg。"""
    resp = await client.post(API, json={"title": ""}, headers=auth_headers)

    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == 42200
    assert body["detail"][0]["field"] == "title"
    assert "msg" in body["detail"][0]


async def test_business_not_found_has_message(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """① 业务异常：NotFoundError 自带人话 "任务不存在"。

    和上面 404 的区别：那条是"路由都没有"，这条是"路由有、资源没有"。
    """
    resp = await client.get(f"{API}/99999", headers=auth_headers)

    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == 40400
    assert body["message"] == "任务不存在"


async def test_unhandled_exception_hides_details(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """④ 未捕获异常 → 500 + 统一信封，且堆栈/内部信息不能出现在响应里。"""

    async def boom(*args, **kwargs):
        raise RuntimeError("数据库密码是 hunter2")

    monkeypatch.setattr("app.api.v1.todos.todo_service.get_stats", boom)

    # 默认 transport 会把异常直接抛给测试；关掉才能看到"真实服务器"会返回什么
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as raw:
        resp = await raw.get(f"{API}/stats", headers=auth_headers)

    assert resp.status_code == 500
    body = resp.json()
    assert body["code"] == 50000
    assert body["message"] == "服务器内部错误"
    assert "hunter2" not in resp.text
    assert "Traceback" not in resp.text
