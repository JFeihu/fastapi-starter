import logging
import time
import uuid

from fastapi import FastAPI, Request, Response

logger = logging.getLogger(__name__)


def register_middleware(app: FastAPI) -> None:

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
