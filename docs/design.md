# 设计文档

> 这份文档回答面试官最常问的："你为什么这么设计？"
> 只写**做过的**；没做的写在最后「已知限制」。

## 1. 需求

一个任务管理后端（多用户）：

| 角色 | 能做什么 |
| --- | --- |
| 注册用户 | 登录、管自己的任务与标签、看自己的统计 |
| — | 看不到别人的数据（越权统一 404） |

**功能范围**：注册/登录/刷新、任务 CRUD、标签（多对多）、任务统计、批量创建（原子 / 部分成功）。

---

## 2. 表结构

```
users 1 ──< todos（owner_id）
todos >──< tags（todo_tags 中间表）
```

| 表 | 关键字段 | 约束 / 索引 |
| --- | --- | --- |
| `users` | `username` `email` `hashed_password` `role` `is_active` | `username`/`email` 唯一 |
| `todos` | `title` `description` `done` `owner_id` | FK `users.id` `ON DELETE CASCADE`；索引 `ix_todos_owner_id`、`ix_todos_owner_done` |
| `tags` | `name` `owner_id` | 唯一 `(owner_id, name)`（同一用户下标签不重名） |
| `todo_tags` | `todo_id` `tag_id` | 复合主键；索引 `ix_todo_tags_tag_id` |

**为什么只建这三个索引**

- `ix_todos_owner_id`：最高频查询是"我的任务"，必走
- `ix_todos_owner_done`：复合索引覆盖"我的未完成任务"（最左前缀能用 `owner_id` 单列）
- `ix_todo_tags_tag_id`：按标签反查任务
- **没给 `done` 单列建索引**：只有两个值，选择性太低，全表扫描更快（W4 用 `EXPLAIN QUERY PLAN` 验证过）

---

## 3. 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | 注册 |
| POST | `/api/v1/auth/login` | 登录（form 编码） |
| POST | `/api/v1/auth/refresh` | 刷新 token |
| GET | `/api/v1/users/me` | 当前用户 |
| GET/POST | `/api/v1/todos` | 列表（分页/筛选/搜索）/ 创建 |
| GET/PATCH/DELETE | `/api/v1/todos/{id}` | 详情 / 局部更新 / 删除 |
| GET | `/api/v1/todos/stats` | 统计（Redis 缓存 30s） |
| POST | `/api/v1/todos/bulk` | 批量创建（`atomic` 控制事务模式） |
| POST/GET | `/api/v1/tags` | 创建 / 列表 |
| GET | `/health` | 健康检查（含 DB 连通性） |

**路由顺序**：`/todos/stats`、`/todos/bulk` 必须写在 `/todos/{id}` 之前，否则会被当成 id（有测试锁住）。

---

## 4. 五个关键取舍

### 4.1 为什么用异步 SQLAlchemy

这个服务大部分时间在等数据库和 Redis，异步能提高并发。代价是**关系属性必须预加载**（`selectinload`），否则序列化时触发懒加载会报 `MissingGreenlet`。

### 4.2 为什么越权返回 404 而不是 403

403 会泄露"这个 id 存在"。统一 404 让"不存在"和"不是你的"对客户端完全一样，防止资源枚举。
代价：调试时分不清两种 404，所以日志里记 `404-because-not-owner`。

### 4.3 为什么缓存用"删"而不是"更新"

cache-aside：读先查缓存，未命中查库回填；写**先更新库、再删缓存**。

不更新缓存的原因：

1. 缓存值可能是聚合结果（统计接口是 `count` + 条件 `sum` 算出来的），更新要重写一遍业务
2. 并发写会互相覆盖
3. 删掉最简单：下次读自然重建

### 4.4 为什么批量创建有两种模式

不同业务语义：转账要原子（全成功/全失败），导入通讯录要部分成功（坏的跳过、好的留下）。
实现：非原子模式用 `SAVEPOINT`（`db.begin_nested()`）隔离单条失败。

### 4.5 为什么时间戳放 Python 侧生成

原本 `created_at` 是数据库 `server_default`，插入后要 `refresh` 回读，50 条记录产生 100 条额外 SELECT。
改成 Python 侧 `default=datetime.now` 后，插入前就有值，**回读全部消失**。

---

## 5. 性能数据（都是实测）

### 5.1 批量创建 N+1

```
改前：50 条记录 → 150 条 SQL（50 INSERT + 100 SELECT），66ms
改后：50 条记录 →  50 条 SQL，10ms
```

工具：`scripts/bench_bulk.py` 用 SQLAlchemy 的 `before_cursor_execute` 事件数语句。

### 5.2 Redis 缓存

```
命中 2.6ms / 未命中 7.6ms（/todos/stats，TTL 30s）
```

### 5.3 压测与降级

300 请求 / 并发 30：

| 场景 | p50 | p95 | RPS |
| --- | --- | --- | --- |
| 缓存正常（首次，刚启动） | 87ms | 113ms | **316** |
| 缓存正常（17 小时后） | 100ms | 518ms | 172.5 |
| 缓存正常（第三次复测） | 111ms | 370ms | 204.5 |
| Redis 停掉（并发 10） | 540ms | 570ms | 18.2 |
| Redis 停掉（并发 30） | 555ms | **12543ms** | **4.4** |

> **关于尾延迟抖动**（p95 在 113 / 370 / 518ms 之间波动）：排查后**排除了两个常见猜测**——
> `todos` 表当时是 0 条（不是数据量问题），容器 CPU 占用 < 1%（不是资源问题）。
> 剩下的嫌疑按可能性排序：
> 1. **连接池排队**：`pool_size=10 + max_overflow=20 = 30`，恰好等于压测并发 30，容易在峰值卡住
> 2. **Docker Desktop 端口转发**（Windows）：`localhost:8000` 的 NAT 在长时间运行后尾延迟变差
> 3. 客户端侧（httpx 连接池 + asyncio）在 30 并发下的调度抖动
>
> 尚未定论，验证方法记在下方「待验证」。**这属于真实工程里的"未结案"问题**，如实记录比编一个原因好。

**结论**：降级保功能（不 500），但吞吐掉 72 倍 → 还需要熔断/限流。
调优：Redis 客户端超时 2s→0.5s，单请求 2009ms→535ms；数据库连接池加 `pool_timeout=5` 快速失败。

**待验证（各 5 分钟）**

| 实验 | 如果 p95 明显下降，说明 |
| --- | --- |
| `--concurrency 5` vs `30` | 连接池排队（并发越高越慢） |
| 在容器内跑压测（`docker compose exec api`） | Docker 端口转发是主因 |
| 把 `pool_size` 调到 20 再压 | 池容量不够 |
| 连续跑 3 次取中位数 | 只是首次冷启动的抖动 |

### 5.4 容器重建

```
改代码后重建：60s → 10s（多阶段构建 + COPY 顺序：依赖在前、代码在后）
镜像体积：328MB → 309MB
```

---

## 6. 已知限制（面试主动说，比被问出来好）

| 限制 | 说明 |
| --- | --- |
| 没有公网部署 | 本地 `docker compose up` 起全套；没做 Nginx/HTTPS |
| 没有 MQ | 用 `BackgroundTasks`（进程内、不可靠）；要可靠得上 Celery/ARQ |
| token 不可撤销 | 只靠短有效期；黑名单/版本号未实现 |
| 没有限流 | 登录爆破防护未做 |
| 分页/搜索用 `ilike('%kw%')` | 前导通配符走不了索引；量大要上全文检索 |
| 单库单表 | 没做读写分离/分表 |
