"""任务标签（Tag）出入参"""

from pydantic import BaseModel, ConfigDict, Field


# 输入模型
class TagCreate(BaseModel):
    """用于接收前端创建标签时的请求体"""

    # 自动去除字符串首尾空格
    model_config = ConfigDict(str_strip_whitespace=True)
    # 必须输入不为空
    name: str = Field(..., min_length=1, max_length=32)


class TagRead(BaseModel):
    """用于返回给前端的标签数据"""

    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
