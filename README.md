# FastAPI Starter（求职练手参考项目）

一个**分层清晰、能跑、能测、能部署**的 FastAPI 后端样例：异步 SQLAlchemy 2.0 + JWT 认证 + 统一异常 + pytest + Docker。
配套文档：仓库根目录的 `roadmap-12-weeks.md`（W3~W9 就是照着它练）。

> 这不是让你抄的模板，而是给你一个「对照答案」：先自己写，卡住了再看这里怎么处理。

## 技术栈

| 层 | 选型 |
| --- | --- |
| Web 框架 | FastAPI 0.115+ |
| 校验/序列化 | Pydantic v2 + pydantic-settings |
| ORM | SQLAlchemy 2.0（async）+ Alembic |
| 数据库 | 开发 SQLite（零配置）/ 生产 PostgreSQL 16 |
| 认证 | OAuth2 密码流 + JWT（PyJWT）+ bcrypt |
| 测试 | pytest + pytest-asyncio + httpx.AsyncClient |
| 质量 | ruff + pre-commit |
| 部署 | Docker 多阶段构建 + docker compose |

## 目录结构

```text
fastapi-starter/
├── app/
│   ├── main.py                 # create_app 工厂、lifespan、中间件、异常注册
│   ├── core/
│   │   ├── config.py           # pydantic-settings，配置只从这里来
│   │   ├── security.py         # 密码哈希 + JWT
│   │   ├── exceptions.py       # 业务异常 + 全局异常处理器
│   │   └── logging.py          # 日志格式
│   ├── db/
│   │   ├── base.py             # Base / 约束命名规范 / 时间戳 Mixin
│   │   ├── models.py           # User、Todo
│   │   └── session.py          # async engine、sessionmaker、get_db
│   ├── schemas/                # 出入参（UserRead 永不包含密码）
│   ├── services/               # 业务逻辑（不 import FastAPI）
│   └── api/
│       ├── deps.py             # 会话、当前用户、分页依赖
│       └── v1/                 # auth / users / todos 路由
├── tests/                      # 26 个用例：正常、边界、越权
├── scripts/seed.py             # 演示数据
├── migrations/                 # Alembic 迁移
├── Dockerfile / docker-compose.yml
└── pyproject.toml              # 依赖 + ruff + pytest 配置
```

## 快速开始

### 方式一：uv（推荐，快 10 倍）

```bash
uv sync --extra dev
cp .env.example .env
uv run uvicorn app.main:app --reload
```

### 方式二：venv + pip

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux
pip install -e ".[dev]"
copy .env.example .env            # Windows
# cp .env.example .env            # macOS / Linux
uvicorn app.main:app --reload
```

打开：

- Swagger：<http://127.0.0.1:8000/docs>（点右上角 Authorize 可带 token 调试）
- ReDoc：<http://127.0.0.1:8000/redoc>
- 健康检查：<http://127.0.0.1:8000/health>

首次启动会自动建表并生成 `app.db`。想先有数据：

```bash
python -m scripts.seed   # 账号 demo / demo12345，含 3 条任务
```

## 接口一览

| 方法 | 路径 | 说明 | 需要登录 |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/register` | 注册 | 否 |
| POST | `/api/v1/auth/login` | 登录（`application/x-www-form-urlencoded`） | 否 |
| POST | `/api/v1/auth/refresh` | 用 refresh token 换新 token | 否 |
| GET | `/api/v1/users/me` | 当前用户 | 是 |
| GET | `/api/v1/todos` | 我的任务，支持 `page/size/done/keyword` | 是 |
| POST | `/api/v1/todos` | 创建任务 | 是 |
| GET | `/api/v1/todos/{id}` | 任务详情 | 是 |
| PATCH | `/api/v1/todos/{id}` | 局部更新 | 是 |
| DELETE | `/api/v1/todos/{id}` | 删除 | 是 |
| GET | `/health` | 健康检查（含 DB 连通性） | 否 |

命令行试一遍：

```bash
# 注册
curl -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"alice\",\"email\":\"alice@example.com\",\"password\":\"S3cret-pass\"}"

# 登录（注意是表单格式）
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -d "username=alice&password=S3cret-pass"

# 带 token 访问
curl http://127.0.0.1:8000/api/v1/todos -H "Authorization: Bearer <access_token>"
```

## 测试与代码质量

```bash
pytest                       # 全部用例
pytest -v tests/test_todos.py
pytest --cov=app --cov-report=term-missing   # 需要 pip install pytest-cov
ruff check . --fix
ruff format .
```

测试设计上的三个关键点（面试可以直接讲）：

1. **依赖覆盖**：`app.dependency_overrides[get_db]` 换成内存库，业务代码零改动；
2. **内存库必须 `StaticPool`**：否则连接池里每个连接是独立的空库，表都看不见；
3. **不启端口**：`httpx.AsyncClient(transport=ASGITransport(app))` 直接进 ASGI，快且稳。

## 数据库迁移

开发期靠 `AUTO_CREATE_TABLES=true` 自动建表，**上线必须关掉**，改用 Alembic：

```bash
alembic revision --autogenerate -m "add something"   # 生成迁移，务必人工 review
alembic upgrade head                                  # 应用
alembic downgrade -1                                  # 回滚一步
alembic history                                       # 历史
```

## Docker 部署

```bash
docker compose up -d --build     # api + postgres + redis 一起起
docker compose logs -f api
docker compose down              # 停止（数据在 volume 里，不会丢）
```

访问 <http://127.0.0.1:8000/docs>。换成 PostgreSQL 后，`DATABASE_URL` 用 `postgresql+asyncpg://...`。

## 几个设计决策（面试会被问）

| 决策 | 原因 |
| --- | --- |
| 路由 → service → model 分层 | 业务与 HTTP 解耦，service 可单测、可被定时任务复用；路由层不出现 SQL |
| 请求级 Session + 依赖里 commit | 一个请求一个事务，异常自动回滚，业务代码不用到处 `commit()` |
| `expire_on_commit=False` | 异步下访问过期属性会触发隐式 IO 直接报错，关掉更安全 |
| 别人的资源返回 404 而不是 403 | 避免通过状态码枚举「资源是否存在」 |
| 错误统一 `{code, message, detail}` | 前端只需判断业务码，HTTP 状态码保持不变 |
| `EmailStr` + 长度/正则约束 | 校验放在 schema 层，进到 service 的数据一定是干净的 |
| 分页封装成依赖 | 参数约束只写一次，Swagger 文档自动带说明 |

## 用它学习的正确姿势（三遍法）

1. **第一遍（读懂）**：跑起来，打开 `/docs` 把每个接口点一遍；画出「请求 → 依赖 → service → ORM」的调用链。
2. **第二遍（重写）**：删掉 `app/`，只留 `tests/`，照着测试把代码重新写出来。写不出来的地方就是没懂的地方。
3. **第三遍（扩展）**：按下面的练习清单加功能，每加一个都要补测试。

## 练习清单（按路线图周次）

- [ ] W5：加 `role` 字段 + `require_role("admin")` 依赖工厂，实现管理员删除任意任务
- [ ] W5：refresh token 存 Redis 白名单，支持"登出即失效"
- [ ] W6：列表接口加 Redis 缓存（key 含用户与分页参数），写缓存失效逻辑
- [ ] W6：登录限流（同 IP 每分钟 10 次），超限返回 429
- [ ] W6：报表导出改成后台任务 + 轮询 `task_id`
- [ ] W7：把 `todos.py` 里的查询抽到 `repositories/`，service 只依赖仓储接口
- [ ] W7：覆盖率补到 85%，CI 跑 ruff + pytest
- [ ] W8：加 Nginx 反代 + HTTPS，写一份 `docs/deploy.md`
- [ ] W11：给列表接口加 `EXPLAIN` 分析，补索引并记录优化前后 P95
- [ ] W11：加 WebSocket `/ws/notifications`，创建任务时推送
