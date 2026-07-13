from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class IssueType(str, Enum):
    data_error = "data_error"
    system_failure = "system_failure"
    complaint = "complaint"
    process_block = "process_block"
    performance = "performance"
    other = "other"


class IssueStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    verify = "verify"
    resolved = "resolved"
    closed = "closed"
    suspended = "suspended"


class ImpactLevel(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class OperationIssueBase(BaseModel):
    issue_no: str = Field(..., max_length=64, description="问题编号")
    title: str = Field(..., max_length=255, description="问题标题")
    issue_type: IssueType = Field(IssueType.other, description="问题类型")
    status: IssueStatus = Field(IssueStatus.pending, description="状态")
    source: str = Field("manual", max_length=64, description="来源")
    discovery_date: Optional[datetime] = Field(None, description="发现时间")
    resolve_date: Optional[datetime] = Field(None, description="解决时间")
    handler: Optional[str] = Field(None, max_length=64, description="处理人")
    impact_scope: Optional[str] = Field(None, description="影响范围")
    impact_level: ImpactLevel = Field(ImpactLevel.P2, description="影响等级")
    root_cause: Optional[str] = Field(None, description="根因分析")
    solution: Optional[str] = Field(None, description="解决方案")
    related_req_id: Optional[str] = Field(None, max_length=64, description="关联需求编号")
    related_ticket_no: Optional[str] = Field(None, max_length=64, description="关联开发工单编号")
    related_system: Optional[str] = Field(None, max_length=128, description="关联系统")
    obsidian_path: Optional[str] = Field(None, max_length=512, description="沉淀知识条目路径")
    is_overdue: int = Field(0, description="是否超期")


class OperationIssueCreate(OperationIssueBase):
    pass


class OperationIssueUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    issue_type: Optional[IssueType] = None
    status: Optional[IssueStatus] = None
    discovery_date: Optional[datetime] = None
    resolve_date: Optional[datetime] = None
    handler: Optional[str] = Field(None, max_length=64)
    impact_scope: Optional[str] = None
    impact_level: Optional[ImpactLevel] = None
    root_cause: Optional[str] = None
    solution: Optional[str] = None
    related_req_id: Optional[str] = Field(None, max_length=64)
    related_ticket_no: Optional[str] = Field(None, max_length=64)
    related_system: Optional[str] = Field(None, max_length=128)
    obsidian_path: Optional[str] = Field(None, max_length=512)
    is_overdue: Optional[int] = None


class OperationIssueOut(OperationIssueBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OperationIssueListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int
    items: List[OperationIssueOut]


class IssueStatsItem(BaseModel):
    name: str
    value: int


class OperationIssueStats(BaseModel):
    total: int
    pending: int
    processing: int
    verify: int
    resolved: int
    closed: int
    suspended: int
    overdue: int
    by_type: List[IssueStatsItem]
