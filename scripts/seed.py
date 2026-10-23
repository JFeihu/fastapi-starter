"""造一批演示数据，方便打开 Swagger 就能试接口。

用法：python -m scripts.seed
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import Todo, User
from app.db.session import SessionLocal, init_models

DEMO_USER = {
    "username": "demo",
    "email": "demo@example.com",
    "password": "demo12345",
}


async def main() -> None:
    await init_models()
    async with SessionLocal() as db:
        exists = await db.scalar(select(User).where(User.username == DEMO_USER["username"]))
        if exists:
            print("演示用户已存在，跳过")
            return

        user = User(
            username=DEMO_USER["username"],
            email=DEMO_USER["email"],
            hashed_password=hash_password(DEMO_USER["password"]),
        )
        db.add(user)
        await db.flush()

        db.add_all(
            [
                Todo(title="读完 FastAPI 依赖注入章节", owner_id=user.id),
                Todo(title="把项目换成 PostgreSQL", owner_id=user.id, done=True),
                Todo(title="给列表接口加 Redis 缓存", owner_id=user.id),
            ]
        )
        await db.commit()
        print(f"已创建演示用户 {DEMO_USER['username']} / {DEMO_USER['password']}，含 3 条任务")


if __name__ == "__main__":
    asyncio.run(main())
