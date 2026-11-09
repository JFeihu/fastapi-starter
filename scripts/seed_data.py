"""造练习数据：往 app.db 里灌 10 万条任务 + 标签。

为什么需要：SQL 要练"查得快不快"，数据太少（几十条）索引和不索引没区别。
10 万条能让 `全表扫描` 和 `走索引` 的差异肉眼可见。

用法：
    uv run python scripts/seed_data.py          # 空库时灌数据
    uv run python scripts/seed_data.py --reset  # 先清空再灌（会删掉现有任务/标签）

注意：只用标准库 sqlite3，直接写 SQL —— 顺便让你看看"不用 ORM 也能操作数据库"。
"""

from __future__ import annotations

import argparse
import random
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "app.db"
TOTAL_TODOS = 100_000
RANDOM_SEED = 42
DEV_PASSWORD = "Password123"   # 种子用户的密码（仅开发用）

TITLE_POOL = [
    "修复登录 bug",
    "写周报",
    "复习 SQL 索引",
    "整理接口文档",
    "重构统计接口",
    "看看 N+1 问题",
    "补测试用例",
    "评审同事的 PR",
    "学习 asyncio",
    "优化慢查询",
    "写迁移脚本",
    "排查 500 错误",
    "设计标签系统",
    "读 FastAPI 源码",
    "整理数据库笔记",
]
FEATURES = ["首页", "详情页", "统计页", "搜索", "导出", "登录", "标签", "批量操作"]


def build_titles(rng: random.Random) -> list[str]:
    titles = []
    for _ in range(TOTAL_TODOS):
        base = rng.choice(TITLE_POOL)
        feature = rng.choice(FEATURES)
        titles.append(f"{base} - {feature} #{rng.randint(1, 9999)}")
    return titles


def reset_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DELETE FROM todo_tags;
        DELETE FROM todos;
        DELETE FROM tags;
        DELETE FROM users;
        """
    )
    conn.commit()


def seed(conn: sqlite3.Connection) -> None:
    rng = random.Random(RANDOM_SEED)
    now = datetime.now(UTC)

    # --- 用户：alice 占 70%，bob 占 30%（便于练"只查自己的"） ---
    # 密码用真实的 bcrypt 哈希，否则无法在 /docs 里登录（bcrypt 校验假哈希会报错）
    from app.core.security import hash_password

    conn.executemany(
        """
        INSERT INTO users (username, email, hashed_password, is_active, created_at, updated_at)
        VALUES (?, ?, ?, 1, datetime('now'), datetime('now'))
        """,
        [
            ("alice", "alice@example.com", hash_password(DEV_PASSWORD)),
            ("bob", "bob@example.com", hash_password(DEV_PASSWORD)),
        ],
    )
    print(f"种子用户密码都是: {DEV_PASSWORD}")


    # --- 标签：alice 20 个，bob 10 个 ---
    tag_rows = []
    for uid, count in ((1, 20), (2, 10)):
        for i in range(count):
            tag_rows.append((f"标签{uid}-{i:02d}", uid))
    conn.executemany(
        "INSERT INTO tags (name, owner_id, created_at, updated_at) "
        "VALUES (?, ?, datetime('now'), datetime('now'))",
        tag_rows,
    )

    # --- 任务：10 万条 ---
    titles = build_titles(rng)
    todo_rows = []
    for i, title in enumerate(titles):
        owner_id = 1 if rng.random() < 0.7 else 2
        done = 1 if rng.random() < 0.4 else 0
        created = now - timedelta(days=rng.randint(0, 365), minutes=rng.randint(0, 1440))
        created_str = created.strftime("%Y-%m-%d %H:%M:%S")
        description = None if rng.random() < 0.7 else f"备注 #{i}"
        todo_rows.append((title, description, done, owner_id, created_str, created_str))

    conn.executemany(
        """
        INSERT INTO todos
            (title, description, done, owner_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        todo_rows,
    )

    # --- 标签关联：30% 的任务挂 1~3 个标签（同一个人自己的标签） ---
    alice_tags = [row[0] for row in conn.execute("SELECT id FROM tags WHERE owner_id = 1")]
    bob_tags = [row[0] for row in conn.execute("SELECT id FROM tags WHERE owner_id = 2")]
    links = []
    for todo_id, (owner_id,) in enumerate(
        conn.execute("SELECT owner_id FROM todos ORDER BY id"), start=1
    ):
        if rng.random() < 0.3:
            pool = alice_tags if owner_id == 1 else bob_tags
            for tag_id in rng.sample(pool, k=rng.randint(1, 3)):
                links.append((todo_id, tag_id))
    conn.executemany("INSERT INTO todo_tags (todo_id, tag_id) VALUES (?, ?)", links)
    conn.commit()

    print(f"用户: 2，标签: {len(tag_rows)}，任务: {len(todo_rows)}，标签关联: {len(links)}")


def report(conn: sqlite3.Connection) -> None:
    print("\n--- 数据概览 ---")
    for label, sql in [
        ("任务总数", "SELECT COUNT(*) FROM todos"),
        ("alice 的任务", "SELECT COUNT(*) FROM todos WHERE owner_id = 1"),
        ("已完成任务", "SELECT COUNT(*) FROM todos WHERE done = 1"),
        ("标签关联", "SELECT COUNT(*) FROM todo_tags"),
        ("最早创建", "SELECT MIN(created_at) FROM todos"),
        ("最新创建", "SELECT MAX(created_at) FROM todos"),
    ]:
        print(f"{label:<12} {conn.execute(sql).fetchone()[0]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="先清空再灌")
    args = parser.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"找不到数据库 {DB_PATH}，先启动一次应用让它建表")

    conn = sqlite3.connect(DB_PATH)
    try:
        existing = conn.execute("SELECT COUNT(*) FROM todos").fetchone()[0]
        if existing and not args.reset:
            print(f"库里已有 {existing} 条任务，跳过。要重灌加 --reset")
            report(conn)
            return

        if args.reset:
            print("清空旧数据...")
            reset_tables(conn)

        print("开始灌数据（约 10 万条）...")
        seed(conn)
        report(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
