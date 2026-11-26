"""接口压测：并发打 N 个请求，统计 p50 / p95 / 平均耗时 / RPS / 错误率。

用法（在 fastapi-starter 目录）：
    # 拿 token 后压测
    uv run python scripts/bench_api.py --token <TOKEN> --n 300 --concurrency 30

    # 降级场景（Redis 停掉）建议把客户端超时放宽，否则会误判成"服务挂了"
    uv run python scripts/bench_api.py --token <TOKEN> --n 300 --concurrency 30 --timeout 60

为什么用 p95 而不是平均值：
    平均值会被"大多数很快"掩盖掉少数很慢的请求。
    p95 = 95% 的请求都在这个时间内 —— 更接近用户体验。

为什么并发用 Semaphore：
    一次发 300 个请求会把本机端口打满，反而测不准。
    限制"同时在飞"的数量，才是真实的并发模型（和 W2 学的 Semaphore 一样）。
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx


async def hit(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    sem: asyncio.Semaphore,
) -> tuple[float, int]:
    """发一个请求，返回 (耗时ms, 状态码)。

    状态码 0 表示"请求本身失败"（超时/连接被拒），用来算错误率。
    """
    async with sem:                       # 拿到许可才能发，限制并发数
        start = time.perf_counter()
        try:
            resp = await client.get(url, headers=headers)
            return (time.perf_counter() - start) * 1000, resp.status_code
        except httpx.HTTPError as exc:    # 超时、连接错误都不该中断整次压测
            cost = (time.perf_counter() - start) * 1000
            _ = exc
            return cost, 0


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/v1/todos/stats")
    parser.add_argument("--token", default="", help="登录拿到的 access_token")
    parser.add_argument("--n", type=int, default=100, help="总请求数")
    parser.add_argument("--concurrency", type=int, default=10, help="同时并发数")
    parser.add_argument(
        "--timeout",
        type=float,
        default=30,
        help="客户端单请求超时（秒）。压测时要比平时宽，否则会误判",
    )
    args = parser.parse_args()

    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}
    sem = asyncio.Semaphore(args.concurrency)

    async with httpx.AsyncClient(timeout=args.timeout) as client:
        # 预热一次（建立连接，避免把 TCP 握手算进第一批）
        await hit(client, args.url, headers, sem)

        started = time.perf_counter()
        results = await asyncio.gather(
            *[hit(client, args.url, headers, sem) for _ in range(args.n)]
        )
        wall_ms = (time.perf_counter() - started) * 1000

    costs = sorted(c for c, _ in results)
    codes: dict[int, int] = {}
    for _, code in results:
        codes[code] = codes.get(code, 0) + 1

    ok_count = codes.get(200, 0)
    err_count = args.n - ok_count

    def pct(p: float) -> float:
        idx = min(len(costs) - 1, int(len(costs) * p))
        return costs[idx]

    print(f"请求数 {args.n} | 并发 {args.concurrency} | 客户端超时 {args.timeout}s | 总耗时 {wall_ms:.0f}ms")
    print(f"  p50  {pct(0.50):7.1f} ms")
    print(f"  p95  {pct(0.95):7.1f} ms")
    print(f"  max  {costs[-1]:7.1f} ms")
    print(f"  avg  {statistics.mean(costs):7.1f} ms")
    print(f"  RPS  {args.n / (wall_ms / 1000):7.1f} 次/秒")
    print(f"  成功 {ok_count} | 失败 {err_count} | 状态码 {codes}")


if __name__ == "__main__":
    asyncio.run(main())
