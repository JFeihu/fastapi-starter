"""日志配置：开发看彩色可读日志，生产建议换成 JSON 便于采集（structlog / python-json-logger）。"""

from __future__ import annotations

import logging
import sys

from app.core.config import settings


def setup_logging() -> None:
    level = logging.DEBUG if settings.debug else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # 第三方库的噪音日志统一降级，否则 debug 模式下一条 SQL 会刷十几行
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "aiosqlite", "asyncio", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
