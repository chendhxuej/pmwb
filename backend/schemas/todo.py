from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class TodoCategory(str, Enum):
    requirement = "requirement"
    ticket = "ticket"
    operation = "operation"
    meeting = "meeting"
    study = "study"
    other = "other"


class TodoStatus(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"
    cancelled = "cancelled"


class TodoPriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class TodoRepeatType(str, Enum):
    none = "none"
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class TodoBase(BaseModel):
    title: str = Field(..., max_length=255, description="待办标题")
    content: Optional[str] = Field(None, description="待办内容")
    category: TodoCategory = Field(TodoCategory.other, description="分类")
    priority: TodoPriority = Field(TodoPriority.P2, description="优先级")
    status: TodoStatus = Field(TodoStatus.todo, description="状态")
    due_date: Optional[date] = Field(None, description="截止日期")
    due_time: Optional[str] = Field(None, max_length=8, description="截止时间")
    remind_at: Optional[datetime] = Field(None, description="提醒时间")
    repeat_type: TodoRepeatType = Field(TodoRepeatType.none, description="重复类型")
    related_type: Optional[str] = Field(None, max_length=64, description="关联对象类型")
    related_id: Optional[str] = Field(None, max_length=64, description="关联对象ID")
    source: str = Field("manual", max_length=64, description="来源")


class TodoCreate(TodoBase):
    pass


class TodoUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = None
    category: Optional[TodoCategory] = None
    priority: Optional[TodoPriority] = None
    status: Optional[TodoStatus] = None
    due_date: Optional[date] = None
    due_time: Optional[str] = Field(None, max_length=8)
    remind_at: Optional[datetime] = None
    repeat_type: Optional[TodoRepeatType] = None
    related_type: Optional[str] = Field(None, max_length=64)
    related_id: Optional[str] = Field(None, max_length=64)


class TodoOut(TodoBase):
    id: int
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    is_overdue: bool

    class Config:
        from_attributes = True


class TodoListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int
    items: List[TodoOut]


class TodoStats(BaseModel):
    total: int
    todo: int
    in_progress: int
    done: int
    cancelled: int
    overdue: int
    today: int
