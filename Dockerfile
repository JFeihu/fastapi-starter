# syntax=docker/dockerfile:1

# ---------- 构建阶段：只装依赖，利用层缓存 ----------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY pyproject.toml ./
COPY app ./app
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install .

# ---------- 运行阶段：不带编译产物、不用 root ----------
FROM python:3.12-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN useradd --create-home --uid 10001 appuser

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser migrations ./migrations

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

# 生产用 gunicorn + uvicorn worker 更稳（可平滑重启、进程管理）：
# CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "-w", "2", "-b", "0.0.0.0:8000"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
