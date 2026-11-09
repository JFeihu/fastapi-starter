"""在 app.db 上直接执行 SQL，替代 sqlite3 命令行。

用法：
    uv run python scripts/sql.py "SELECT COUNT(*) FROM todos"
    uv run python scripts/sql.py            # 交互模式（输入 exit 退出）

为什么需要：练 SQL 应该"写一句看一句结果"，而不是改一次 Python 文件跑一次。
"""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "app.db"


def run(conn: sqlite3.Connection, sql: str) -> None:
    start = time.perf_counter()
    try:
        cursor = conn.execute(sql)
        rows = cursor.fetchall()
    except sqlite3.Error as exc:
        print(f"SQL 错误: {exc}")
        return
    cost = (time.perf_counter() - start) * 1000

    if cursor.description is None:  # INSERT / UPDATE / DELETE
        conn.commit()
        print(f"影响行数: {cursor.rowcount}  ({cost:.1f} ms)")
        return

    headers = [col[0] for col in cursor.description]
    print(" | ".join(headers))
    print("-" * (len(" | ".join(headers)) or 10))
    for row in rows:
        print(" | ".join("NULL" if v is None else str(v) for v in row))
    print(f"({len(rows)} 行, {cost:.1f} ms)")


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"找不到 {DB_PATH}，先跑一次 scripts/seed_data.py")

    conn = sqlite3.connect(DB_PATH)
    # 分组/排序默认要建临时文件；磁盘满或临时目录不可写时会报
    # "unable to open database file"。放内存就没这个问题（10 万条量级完全够）。
    conn.execute("PRAGMA temp_store = MEMORY")
    try:
        if len(sys.argv) > 1:
            run(conn, " ".join(sys.argv[1:]))
            return

        print(f"已连接 {DB_PATH.name}，输入 SQL 回车执行，输入 exit 退出")
        while True:
            try:
                sql = input("sql> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not sql:
                continue
            if sql.lower() in {"exit", "quit", ".q"}:
                break
            run(conn, sql)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
