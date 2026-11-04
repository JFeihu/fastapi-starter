"""应用入口：create_app 工厂 + lifespan + 中间件 + 异常处理 + 路由挂载。

为什么用工厂函数？测试里可以 create_app() 造出干净实例；
为什么用 lifespan？启动/关闭时的资源（连接池、Redis、HTTP 客户端）有明确边界。
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.deps import DBSession
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.db.session import engine, init_models

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    if settings.auto_create_tables:
        # 仅开发用；生产靠 alembic upgrade head，避免"代码改了表没改"
        await init_models()
    logger.info("%s 启动完成，环境 debug=%s", settings.app_name, settings.debug)
    yield
    await engine.dispose()
    logger.info("资源已释放")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="FastAPI 求职练手项目：异步 SQLAlchemy + JWT + 统一异常 + pytest",
        lifespan=lifespan,
        # /docs 和 /redoc 默认从 cdn.jsdelivr.net 加载 JS/CSS，国内常被墙，
        # 这里关掉默认的，改用本地静态资源自己渲染（见下面 custom_docs）
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json",
    )

    # ---- 静态资源：Swagger UI 的 JS/CSS 放在 app/static/swagger/ ----
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/docs", include_in_schema=False)
    async def custom_docs() -> HTMLResponse:
        """自托管版 Swagger UI：不依赖外网 CDN，内网/离线环境也能用。"""
        return get_swagger_ui_html(
            openapi_url=app.openapi_url or "/openapi.json",
            title=f"{settings.app_name} - 接口文档",
            swagger_js_url="/static/swagger/swagger-ui-bundle.js",
            swagger_css_url="/static/swagger/swagger-ui.css",
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,  # 生产环境写白名单，不要用 ["*"] + credentials
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next) -> Response:
        """给每个请求打上 request id，并记录耗时。

        面试可讲：日志里靠 request_id 把一次请求的所有日志串起来，
        排查线上问题（尤其是并发场景）必备。
        """
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            cost = (time.perf_counter() - start) * 1000
            logger.exception(
                "request failed %s %s cost=%.1fms rid=%s",
                request.method,
                request.url.path,
                cost,
                request_id,
            )
            raise
        cost = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{cost:.1f}ms"
        logger.info(
            "%s %s -> %s %.1fms rid=%s",
            request.method,
            request.url.path,
            response.status_code,
            cost,
            request_id,
        )
        return response

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["运维"], summary="健康检查（含数据库连通性）")
    async def health(db: DBSession) -> dict[str, str]:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "app": settings.app_name}

    @app.get("/", include_in_schema=False)
    async def index() -> dict[str, str]:
        return {"message": "FastAPI Starter", "docs": "/docs"}

    return app


app = create_app()
