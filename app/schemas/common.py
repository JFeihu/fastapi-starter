"""通用 schema。"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """统一分页结构。"""

    items: list[T]
    total: int = Field(description="总条数")
    page: int = Field(description="当前页码，从 1 开始")
    size: int = Field(description="每页条数")

    @property
    def pages(self) -> int:
        return (self.total + self.size - 1) // self.size if self.size else 0


class Message(BaseModel):
    message: str
