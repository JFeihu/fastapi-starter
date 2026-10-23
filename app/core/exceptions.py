"""业务异常 + 全局异常处理器。

原则：
1. 业务代码只抛 AppError 子类，不关心 HTTP 细节；
2. 错误响应统一为 {"code": 业务码, "message": 人话, "detail": 可选细节}；
3. 未捕获异常由兜底处理器转 500，绝不把堆栈返回给客户端。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """所有业务异常的基类。"""

    code: int = 40000
    status_code: int = 400
    message: str = "请求错误"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: int | None = None,
        detail: Any = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.detail = detail
        super().__init__(self.message)


class BadRequestError(AppError):
    code = 40000
    status_code = 400
    message = "参数错误"


class UnauthorizedError(AppError):
    code = 40100
    status_code = 401
    message = "未认证或凭证已失效"


class ForbiddenError(AppError):
    code = 40300
    status_code = 403
    message = "没有权限执行该操作"


class NotFoundError(AppError):
    code = 40400
    status_code = 404
    message = "资源不存在"


class ConflictError(AppError):
    code = 40900
    status_code = 409
    message = "资源冲突"


def _error_body(code: int, message: str, detail: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if detail is not None:
        body["detail"] = detail
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message, exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        # 把 pydantic 的报错压平成前端好用的结构
        errors = [
            {"field": ".".join(str(x) for x in err["loc"][1:]), "msg": err["msg"]}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_error_body(42200, "参数校验失败", errors),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.status_code * 100, str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("未捕获异常 path=%s", request.url.path)
        return JSONResponse(status_code=500, content=_error_body(50000, "服务器内部错误"))
