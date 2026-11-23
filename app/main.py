"""应用入口：create_app 工厂 + lifespan + 中间件 + 异常处理 + 路由挂载。

为什么用工厂函数？测试里可以 create_app() 造出干净实例；
为什么用 lifespan？启动/关闭时的资源（连接池、Redis、HTTP 客户端）有明确边界。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.docs import register_docs
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import register_middleware
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


    register_docs(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,  # 生产环境写白名单，不要用 ["*"] + credentials
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_middleware(app)
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    app.include_router(health_router)

    return app


app = create_app()
