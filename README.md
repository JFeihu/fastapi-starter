# FastAPI Starter（求职练手项目）

## 这是什么

一个基于 FastAPI 的任务清单（Todo）后端：JWT 登录、异步 SQLAlchemy、统一异常处理、完整的测试。

在参考脚手架上，我实现了这些功能：

- **任务统计**：`GET /todos/stats`，用聚合查询（`count` + 条件 `sum`）一次算出总数/完成数/完成率
- **标签功能**：任务与标签多对多，支持创建/查询标签、创建任务时关联标签
- **批量创建**：`POST /todos/bulk`，提供“原子”和“部分成功”两种事务模式
- **错误契约测试**：覆盖 4 类异常（业务/校验/HTTP/兜底），锁住统一错误格式

当前：**56 个测试全绿，覆盖率 92%**。

## 技术栈

| 层 | 选型 |
| --- | --- |
| Web 框架 | FastAPI 0.115+（ASGI） |
| 校验 / 序列化 | Pydantic v2 + pydantic-settings |
| ORM | SQLAlchemy 2.0（async）+ Alembic |
| 数据库 | SQLite（开发）/ 可切 PostgreSQL（`DATABASE_URL`） |
| 认证 | JWT（access + refresh），`OAuth2PasswordBearer` |
| 测试 | pytest + pytest-asyncio + httpx.AsyncClient + pytest-cov |
| 工具 | uv（依赖）、ruff（lint/format） |

## 快速开始

```powershell
uv sync
Copy-Item .env.example .env
uv run pytest -q
uv run uvicorn app.main:app --reload
```

启动后打开 <http://127.0.0.1:8000/docs>（Swagger UI 已自托管，不依赖外网 CDN）。

## 接口清单

| 方法 | 路径 | 说明 | 需要登录 |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/register` | 注册 | 否 |
| POST | `/api/v1/auth/login` | 登录（`application/x-www-form-urlencoded`） | 否 |
| POST | `/api/v1/auth/refresh` | 用 refresh token 换新 token | 否 |
| GET | `/api/v1/users/me` | 当前用户 | 是 |
| GET | `/api/v1/todos` | 我的任务，支持 `page/size/done/keyword` | 是 |
| POST | `/api/v1/todos` | 创建任务（可带 `tag_ids`） | 是 |
| GET | `/api/v1/todos/{id}` | 任务详情 | 是 |
| PATCH | `/api/v1/todos/{id}` | 局部更新 | 是 |
| DELETE | `/api/v1/todos/{id}` | 删除 | 是 |
| GET | `/api/v1/todos/stats` | 任务统计 | 是 |
| POST | `/api/v1/todos/bulk` | 批量创建（`atomic` 控制事务模式） | 是 |
| POST | `/api/v1/tags` | 创建标签 | 是 |
| GET | `/api/v1/tags` | 我的标签 | 是 |
| GET | `/health` | 健康检查（含 DB 连通性） | 否 |

> 注意：`/todos/stats` 和 `/todos/bulk` 必须写在 `/todos/{id}` 之前，否则会被当成 id 解析。

## 错误码约定

所有错误响应格式统一：

```json
{"code": 40400, "message": "任务不存在", "detail": null}
```

| code | HTTP | 含义 |
| --- | --- | --- |
| 40000 | 400 | 参数错误 |
| 40100 | 401 | 未认证或凭证已失效 |
| 40300 | 403 | 没有执行权限 |
| 40400 | 404 | 资源不存在 |
| 40900 | 409 | 资源冲突（重名等） |
| 42200 | 422 | 参数校验失败（`detail` 是字段错误列表） |
| 50000 | 500 | 服务器内部错误（不返回任何细节） |

实现方式：`AppError` 基类 + 一个 `@app.exception_handler(AppError)`，靠异常的 MRO 自动匹配所有子类；新增错误类型只需加一个类，不写新 handler。

## 我做的设计决策

**为什么批量创建要提供 atomic 和 partial 两种模式？**

不同业务语义：转账要原子（要么全成功，要么全失败）；导入通讯录要部分成功（坏的那条跳过，好的留下）。实现上，partial 模式用 `SAVEPOINT`（`db.begin_nested()`）隔离单条失败——回滚一条不会牵连已经成功的那些。

**为什么用 `response_model` 而不是在函数里手动删字段？**

模型即白名单：没声明的字段不可能输出，后续给 ORM 加敏感字段也不用回头改每个接口。代价是接口返回的字段由 schema 决定，service 多算的字段会被裁掉（所以加字段要先改 schema）。

**为什么资源不存在时返回 404 而不是 403？**

如果用 403 说“无权访问”，攻击者就能靠 403/404 的差异探测“这个 id 是否存在”（资源枚举）。统一返回 404，让“不存在”和“不是你的”看起来完全一样。

## 开发

```powershell
uv run pytest -q                                    # 跑测试
uv run pytest --cov=app --cov-report=term-missing   # 看覆盖率
uv run ruff check app tests                         # lint
uv run ruff format app tests                        # 格式化
```
