"""任务（Todo）出入参。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200, examples=["看完 FastAPI 依赖注入"])
    description: str | None = Field(default=None, max_length=2000)
    done: bool = False


class TodoUpdate(BaseModel):
    """全部可选：PUT 在这里做成"局部更新"的语义，前端更好用。"""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    done: bool | None = None


class TodoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    done: bool
    owner_id: int
    created_at: datetime
    updated_at: datetime
