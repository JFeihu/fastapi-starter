"""
@Author: JH9
@Time: 2026/11/26
@Desc:
"""

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from redis import RedisError
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


async def cache_aside(
    redis: Redis,
    key: str,
    ttl: int,
    loader: Callable[[], Awaitable[Any]],
) -> Any:
    """先查缓存，未命中调 loader 并在回填。

    要求：
    1. redis.get(key) 命中 → json.loads 返回
    2. 未命中 → await loader()
    3. 结果不为 None → redis.set(key, json.dumps(...), ex=ttl)
    4. **Redis 异常时降级**：捕获 RedisError，直接返回 loader() 的结果
    5. 返回结果
    """
    # 1. 查缓存
    try:
        raw = await redis.get(key)
        if raw is not None:
            logger.info("缓存命中 key=%s", key)          # ← 可观测性：命中要能看见
            return json.loads(raw)
        logger.info("缓存未命中 key=%s", key)            # ← 未命中也要能看见
    except RedisError as exc:
        logger.warning("读缓存失败，降级查库 key=%s err=%s", key, exc)
        return await loader()  # Redis 挂了 → 直接查库

    # 2. 未命中 → 算
    row = await loader()

    # 3. 回填（失败也不影响返回）
    try:
        if row is not None:
            await redis.set(key, json.dumps(row), ex=ttl)
            logger.info("已回填缓存 key=%s ttl=%s", key, ttl)
    except RedisError as exc:
        logger.warning("写缓存失败（忽略） key=%s err=%s", key, exc)

    # 4. 返回
    return row
