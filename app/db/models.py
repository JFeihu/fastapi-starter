"""ORM 模型：只描述表结构，不写业务逻辑。"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    todos: Mapped[list[Todo]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:  # 调试时打印对象更友好
        return f"<User id={self.id} username={self.username!r}>"


class Todo(Base, TimestampMixin):
    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    owner: Mapped[User] = relationship(back_populates="todos")

    def __repr__(self) -> str:
        return f"<Todo id={self.id} title={self.title!r} done={self.done}>"
