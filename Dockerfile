# syntax=docker/dockerfile:1

# ============================================================
# 构建阶段：只装依赖 + 装项目
# ============================================================
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# uv 从 PyPI 装（不用 ghcr.io，国内更稳）
RUN pip install --no-cache-dir uv

WORKDIR /app

# ---- 关键：先只复制依赖清单 ----
# 这两个文件不变，下面的 uv sync 就能命中缓存
COPY pyproject.toml uv.lock ./

# 只装第三方依赖，不装项目本身（项目代码还没复制进来）
RUN uv sync --frozen --no-dev --no-install-project

# ---- 再复制代码，装项目本身 ----
COPY app ./app
RUN uv sync --frozen --no-dev

# ============================================================
# 运行阶段：只带 venv + 代码，不带编译工具
# ============================================================
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    # 容器里用绝对路径的数据文件（相对路径 "./app.db" 会落到 WORKDIR，权限容易出问题）
    DATABASE_URL="sqlite+aiosqlite:////app/data/app.db"

RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

# venv 和代码一起从 builder 复制（含 .venv/app/pyproject/uv.lock）
COPY --from=builder --chown=appuser:appuser /app /app

# 迁移需要的东西（运行 alembic upgrade head 时用）
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser migrations ./migrations

# ---- 关键：/app 目录本身是 root 建的，非 root 用户写不了 ----
# 只 chown 目录、不递归（递归会对 .venv 几千个文件做 chown，多花 6 秒）
RUN mkdir -p /app/data && chown appuser:appuser /app /app/data

# 声明数据目录（compose 里挂卷，容器重建数据不丢）
VOLUME ["/app/data"]

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
