"""任务（Todo）出入参。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.tag import TagRead


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200, examples=["看完 FastAPI 依赖注入"])
    description: str | None = Field(default=None, max_length=2000)
    done: bool = False
    tag_ids: list[int] = Field(default_factory=list, max_length=10)  # 最多挂10个


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
    tags: list[TagRead] = Field(default_factory=list)  # 嵌套返回


class TodoStats(BaseModel):
    total: int
    done: int
    pending: int
    completion_rate: float


class BulkCreateRequest(BaseModel):
    items: list[TodoCreate] = Field(min_length=1, max_length=50)
    atomic: bool = False


class BulkItemError(BaseModel):
    index: int
    error: str


class BulkCreateResult(BaseModel):
    created: list[TodoRead]
    failed: list[BulkItemError]
