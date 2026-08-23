from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ActiveOptimizationBase(BaseModel):
    title: str = Field(..., max_length=256, description="工单标题")
    current_situation: Optional[str] = Field(None, description="现状描述")
    suggestion: Optional[str] = Field(None, description="优化建议")
    admin_name: Optional[str] = Field(None, max_length=64, description="业务管理员")
    status: str = Field("pending", description="评估状态：pending/adopted/rejected")
    priority: Optional[str] = Field("P2", max_length=16, description="优先级：P0/P1/P2/P3")
    req_id: Optional[str] = Field(None, max_length=64, description="关联需求文号")
    note: Optional[str] = Field(None, description="备注说明")


class ActiveOptimizationCreate(ActiveOptimizationBase):
    pass


class ActiveOptimizationUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=256)
    current_situation: Optional[str] = None
    suggestion: Optional[str] = None
    admin_name: Optional[str] = Field(None, max_length=64)
    status: Optional[str] = None
    priority: Optional[str] = Field(None, max_length=16)
    req_id: Optional[str] = Field(None, max_length=64)
    note: Optional[str] = None


class ActiveOptimizationOut(ActiveOptimizationBase):
    id: int
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ActiveOptimizationListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int
    items: List[ActiveOptimizationOut]


class ActiveOptimizationStats(BaseModel):
    total: int
    pending: int
    adopted: int
    rejected: int
    this_week: int
