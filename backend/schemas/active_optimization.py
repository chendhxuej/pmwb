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
    req_ids: Optional[List[str]] = Field(None, description="关联需求文号列表（一对多，全量覆盖）")


class ActiveOptimizationUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=256)
    current_situation: Optional[str] = None
    suggestion: Optional[str] = None
    admin_name: Optional[str] = Field(None, max_length=64)
    status: Optional[str] = None
    priority: Optional[str] = Field(None, max_length=16)
    req_id: Optional[str] = Field(None, max_length=64)
    req_ids: Optional[List[str]] = Field(None, description="关联需求文号列表（一对多，全量覆盖）")
    note: Optional[str] = None


class ActiveOptReqLinkOut(BaseModel):
    """主动优化 × 需求文号 关联项输出。"""

    id: int
    opt_id: int
    req_id: str
    req_name: Optional[str] = None
    req_exists: bool = True
    created_at: Optional[datetime] = None


class ActiveOptimizationReqLinkIn(BaseModel):
    """关联需求文号写入入参（PUT=全量覆盖 / POST=增量添加）。"""

    req_ids: List[str] = Field(default_factory=list, description="需求文号列表")
    strict: bool = Field(False, description="True=任一文号无效则整体拒绝；False=部分成功")


class ActiveOptimizationOut(ActiveOptimizationBase):
    id: int
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    req_ids: List[str] = Field(default_factory=list, description="关联需求文号列表（一对多）")
    req_links: List[ActiveOptReqLinkOut] = Field(
        default_factory=list, description="关联需求明细（含需求名与有效性）"
    )

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
