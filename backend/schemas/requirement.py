from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class RequirementStatus(str):
    """需求个人跟踪状态。"""

    proposed = "proposed"
    accepted = "accepted"
    dev = "dev"
    closed = "closed"
    paused = "paused"


class RequirementPriority(str):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class RequirementExtBase(BaseModel):
    status: str = Field("proposed", description="个人跟踪状态")
    tags: Optional[str] = Field(None, description="个人标签，逗号分隔")
    personal_note: Optional[str] = Field(None, description="个人备注")
    priority: str = Field("P2", description="个人优先级")
    owner_note: Optional[str] = Field(None, description="负责人备忘")


class RequirementExtUpdate(BaseModel):
    status: Optional[str] = None
    tags: Optional[str] = None
    personal_note: Optional[str] = None
    priority: Optional[str] = None
    owner_note: Optional[str] = None


class EvaluationUpdate(BaseModel):
    """团队评估记录可编辑字段（全量可选，按传入字段更新）。"""

    sa_name: Optional[str] = Field(None, description="评估SA/团队负责人")
    system_name: Optional[str] = Field(None, description="负责系统")
    workload: Optional[float] = Field(None, description="工作量评估(人天)")
    review_workload: Optional[float] = Field(None, description="复核工作量(人天)")
    opinion: Optional[str] = Field(None, description="评估意见登记")
    dev_ticket_no: Optional[str] = Field(None, description="开发单号")


class EvaluationCreate(BaseModel):
    """新增团队评估记录。"""

    sa_name: str = Field(..., description="评估SA/团队负责人")
    system_name: Optional[str] = Field(None, description="负责系统")
    workload: Optional[float] = Field(None, description="工作量评估(人天)")
    review_workload: Optional[float] = Field(None, description="复核工作量(人天)")
    opinion: Optional[str] = Field(None, description="评估意见登记")
    dev_ticket_no: Optional[str] = Field(None, description="开发单号")


class EvaluationOut(BaseModel):
    """团队评估记录输出。"""

    id: int
    req_id: Optional[str] = None
    sent_email_id: Optional[int] = None
    sa_name: Optional[str] = None
    system_name: Optional[str] = None
    workload: Optional[float] = None
    review_workload: Optional[float] = None
    opinion: Optional[str] = None
    dev_ticket_no: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RequirementExtOut(RequirementExtBase):
    id: int
    req_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RequirementBase(BaseModel):
    req_id: str = Field(..., description="需求编号")
    req_name: Optional[str] = Field(None, description="需求名称")
    proposer: Optional[str] = None
    propose_time: Optional[str] = None
    background: Optional[str] = None
    description: Optional[str] = None
    clarification: Optional[str] = None
    system_name: Optional[str] = None
    sa_name: Optional[str] = None
    send_datetime: Optional[str] = None
    workload: Optional[float] = None
    is_involved: Optional[int] = 1
    dev_ticket_no: Optional[str] = None
    involve_dev: Optional[str] = None


class RequirementOut(RequirementBase):
    ext: Optional[RequirementExtOut] = None


class RequirementListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int
    items: List[RequirementOut]


class RequirementStats(BaseModel):
    total: int
    proposed: int
    accepted: int
    dev: int
    closed: int
    paused: int
    involved: int
