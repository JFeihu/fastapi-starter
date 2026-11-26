"""Redis 客户端：进程内单例 + 连接池。

为什么单独一个模块：
- 客户端要在 lifespan 里创建/关闭，不能每个请求新建（TCP 握手很贵）
- 业务代码通过依赖拿客户端，测试里可以替换成 fakeredis

注意：必须是 `redis.asyncio`。同步的 `redis` 会阻塞事件循环（W2 的坑）。
"""

from __future__ import annotations

import logging

from redis.asyncio import Redis, from_url

from app.core.config import settings

logger = logging.getLogger(__name__)

# 进程内单例（首次使用时创建）
_client: Redis | None = None


def get_client() -> Redis:
    """取（或创建）全局 Redis 客户端。"""
    global _client
    if _client is None:
        _client = from_url(
            settings.redis_url,
            # decode_responses=True：get 直接返回 str，不用每次 .decode()
            decode_responses=True,
            # ⚠️ 超时要短：缓存是"加速器"，不能让它拖慢主流程。
            # 0.5 秒拿不到就降级查库 —— 2 秒会让单请求慢 4 倍，并发下更致命。
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
            health_check_interval=30,
        )
    return _client


async def check_connection() -> bool:
    """启动时探活：连不上只告警，不阻止应用启动（缓存是可选的）。"""
    try:
        await get_client().ping()
        logger.info("redis 连接正常: %s", settings.redis_url)
        return True
    except Exception as exc:  # noqa: BLE001 - 启动阶段要捕获一切
        logger.warning("redis 连接失败（缓存将降级）: %s", exc)
        return False


async def close_client() -> None:
    """关闭连接池。不关的话进程退出时会报 unclosed connection 警告。"""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
        logger.info("redis 连接已关闭")
