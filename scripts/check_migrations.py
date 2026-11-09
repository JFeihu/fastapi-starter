"""用全新数据库跑一遍所有迁移，验证「迁移能独立建出完整的库」。

为什么需要：开发库是 create_all + 迁移混出来的，可能比迁移历史「超前」。
只有从空库跑 `alembic upgrade head`，才能确认换台机器能建出一样的结构。

用法：
    uv run python scripts/check_migrations.py
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRESH_DB = ROOT / "_migration_check.db"
ALEMBIC = ROOT / ".venv" / "Scripts" / "alembic.exe"

EXPECTED_TABLES = {"users", "todos", "tags", "todo_tags", "alembic_version"}
EXPECTED_INDEXES = {
    "ix_todos_owner_id",
    "ix_todos_owner_done",
    "ix_todo_tags_tag_id",
    "ix_users_username",
    "ix_users_email",
}


def run_alembic(*args: str) -> int:
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///./{FRESH_DB.name}"
    env["AUTO_CREATE_TABLES"] = "false"  # 关键：不让 create_all 帮忙
    result = subprocess.run(
        [str(ALEMBIC), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    if result.returncode != 0:
        print(output[-800:])
    return result.returncode


def main() -> None:
    if FRESH_DB.exists():
        FRESH_DB.unlink()

    print(f"1) 在空库上跑 alembic upgrade head → {FRESH_DB.name}")
    if run_alembic("upgrade", "head") != 0:
        raise SystemExit("迁移执行失败（见上面的报错）")

    conn = sqlite3.connect(FRESH_DB)
    try:
        tables = {
            name for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        indexes = {
            name
            for (name,) in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
            )
        }
        columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
    finally:
        conn.close()

    print("\n2) 检查表：", "OK" if tables >= EXPECTED_TABLES else f"缺 {EXPECTED_TABLES - tables}")
    print("   实际:", sorted(tables))

    missing_ix = EXPECTED_INDEXES - indexes
    print("\n3) 检查索引：", "OK" if not missing_ix else f"缺 {missing_ix}")
    print("   实际:", sorted(indexes))

    print("\n4) 检查 users.role：", "OK" if "role" in columns else "缺 role 列")

    print("\n5) 验证回滚：downgrade base")
    if run_alembic("downgrade", "base") != 0:
        raise SystemExit("回滚失败")

    FRESH_DB.unlink(missing_ok=True)

    ok = tables >= EXPECTED_TABLES and not missing_ix and "role" in columns
    print(
        "\n结论:", "OK — 迁移可以独立建出完整的库" if ok else "FAIL — 迁移和模型不一致，需要补迁移"
    )


if __name__ == "__main__":
    main()
