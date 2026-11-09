"""事务演示：用两个连接观察「提交 / 回滚 / 写锁」。

用法：
    uv run python scripts/tx_demo.py

会依次演示：
    A. 没提交的写，另一个连接看不见
    B. 回滚后数据回到原样
    C. 两个连接同时写 → 后写的被锁住（database is locked）
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "app.db"


def connect(timeout: float = 1.0) -> sqlite3.Connection:
    conn = sqlite3.connect(DB, timeout=timeout, isolation_level=None)  # 手动控制事务
    conn.execute("PRAGMA temp_store = MEMORY")
    return conn


def count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM todos").fetchone()[0]


def demo_a() -> None:
    print("=== A. 未提交的写，另一个连接看不见 ===")
    writer = connect()
    reader = connect()

    before = count(reader)
    writer.execute("BEGIN")
    writer.execute(
        "INSERT INTO todos (title, done, owner_id, created_at, updated_at) "
        "VALUES ('事务测试A', 0, 1, datetime('now'), datetime('now'))"
    )
    print("  writer 写入 1 条（未提交）")
    print(f"  reader 看到: {count(reader)} 条（写入前 {before} 条）→ 看不到")
    writer.execute("COMMIT")
    print(f"  writer COMMIT 之后 reader 看到: {count(reader)} 条 → 看到了")

    writer.execute("DELETE FROM todos WHERE title = '事务测试A'")
    writer.close()
    reader.close()


def demo_b() -> None:
    print("\n=== B. 回滚：数据回到原样 ===")
    conn = connect()
    todo_id = conn.execute("SELECT id FROM todos ORDER BY id LIMIT 1").fetchone()[0]
    original = conn.execute("SELECT title FROM todos WHERE id = ?", (todo_id,)).fetchone()[0]

    conn.execute("BEGIN")
    conn.execute("UPDATE todos SET title = '被改坏了' WHERE id = ?", (todo_id,))
    inside = conn.execute("SELECT title FROM todos WHERE id = ?", (todo_id,)).fetchone()[0]
    print(f"  事务内读到: {inside}")
    conn.execute("ROLLBACK")
    now = conn.execute("SELECT title FROM todos WHERE id = ?", (todo_id,)).fetchone()[0]
    print(f"  ROLLBACK 之后: {now}")
    print(f"  和原来一样吗: {now == original}")
    conn.close()


def demo_c() -> None:
    print("\n=== C. 两个连接同时写：后写的被锁住 ===")
    first = connect()
    second = connect(timeout=1.0)

    first.execute("BEGIN IMMEDIATE")
    first.execute("UPDATE todos SET done = done WHERE id = 1")
    print("  first 拿到写锁（BEGIN IMMEDIATE）")

    start = time.perf_counter()
    try:
        second.execute("BEGIN IMMEDIATE")
        second.execute("UPDATE todos SET done = done WHERE id = 1")
        print("  second 居然成功了？（不该发生）")
    except sqlite3.OperationalError as exc:
        cost = (time.perf_counter() - start) * 1000
        print(f"  second 失败: {exc}（等待了 {cost:.0f} ms）")
    finally:
        first.execute("ROLLBACK")
        first.close()
        second.close()
    print("  first 释放锁之后，second 就能写入了")


if __name__ == "__main__":
    demo_a()
    demo_b()
    demo_c()
