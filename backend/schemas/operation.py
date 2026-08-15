from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class IssueType(str, Enum):
    """工单子类（细分类型）。2026-07-16 优化重定义。"""

    bug = "bug"  # BUG
    data_abnormal = "data_abnormal"  # 数据异常
    topic_analysis = "topic_analysis"  # 专题分析
    spot_event = "spot_event"  # 投点事件
    temp_task = "temp_task"  # 临时任务
    other = "other"  # 其他


class WorkOrderCategory(str, Enum):
    """工单大类。"""
    bug = "bug"            # BUG管理
    data = "data"          # 数据异常管理
    prod = "prod"          # 主动运营分析
    task = "task"          # 临时交办任务
    complaint = "complaint"  # 热点投诉


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
    issue_no: str = Field(..., max_length=64, description="工单编号")
    title: str = Field(..., max_length=255, description="工单标题")
    category: WorkOrderCategory = Field(WorkOrderCategory.prod, description="工单大类")
    domain_code: Optional[str] = Field(None, max_length=64, description="关联业务领域编码")
    issue_type: IssueType = Field(IssueType.other, description="问题子类(细分类型)")
    status: IssueStatus = Field(IssueStatus.pending, description="状态")
    source: str = Field("manual", max_length=64, description="来源")
    discovery_date: Optional[datetime] = Field(None, description="发现时间")
    resolve_date: Optional[datetime] = Field(None, description="解决时间")
    handler: Optional[str] = Field(None, max_length=512, description="处理人(多选,逗号分隔)")
    situation_desc: Optional[str] = Field(None, description="情况说明")
    impact_level: ImpactLevel = Field(ImpactLevel.P2, description="影响等级")
    root_cause: Optional[str] = Field(None, description="根因分析")
    solution: Optional[str] = Field(None, description="解决方案")
    related_req_id: Optional[str] = Field(None, max_length=64, description="关联需求编号")
    related_ticket_no: Optional[str] = Field(None, max_length=64, description="关联开发工单编号")
    related_system: Optional[str] = Field(None, max_length=128, description="关联系统")
    obsidian_path: Optional[str] = Field(None, max_length=512, description="沉淀知识条目路径")
    is_overdue: int = Field(0, description="是否超期")
    go_live_date: Optional[datetime] = Field(None, description="计划完成时间")
    result_feedback: Optional[str] = Field(None, description="处理结果反馈")
    attachments: Optional[str] = Field(None, description="附件元信息(JSON 数组字符串)")
    root_cause_type: Optional[str] = Field(None, max_length=64, description="根因分类：system_config/business_rule/data_issue/process_gap/external_dependency/other")
    impact_scope: Optional[str] = Field(None, max_length=64, description="影响范围：single_customer/partial_region/full_region/business_line/platform")
    solution_type: Optional[str] = Field(None, max_length=64, description="解决方案类型：config_fix/code_fix/data_repair/process_optimization/training/escalation/other")
    lesson_learned: Optional[str] = Field(None, description="经验总结/防止复发措施")

    @field_validator("discovery_date", "resolve_date", "go_live_date", mode="before")
    @classmethod
    def _empty_to_none(cls, v):
        if v is None or v == "":
            return None
        return v


class OperationIssueCreate(OperationIssueBase):
    pass


class OperationIssueUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    category: Optional[WorkOrderCategory] = None
    domain_code: Optional[str] = Field(None, max_length=64)
    issue_type: Optional[IssueType] = None
    status: Optional[IssueStatus] = None
    discovery_date: Optional[datetime] = None
    resolve_date: Optional[datetime] = None
    handler: Optional[str] = Field(None, max_length=512)
    situation_desc: Optional[str] = None
    impact_level: Optional[ImpactLevel] = None
    root_cause: Optional[str] = None
    solution: Optional[str] = None
    related_req_id: Optional[str] = Field(None, max_length=64)
    related_ticket_no: Optional[str] = Field(None, max_length=64)
    related_system: Optional[str] = Field(None, max_length=128)
    obsidian_path: Optional[str] = Field(None, max_length=512)
    is_overdue: Optional[int] = None
    go_live_date: Optional[datetime] = None
    result_feedback: Optional[str] = None
    attachments: Optional[str] = None
    root_cause_type: Optional[str] = Field(None, max_length=64)
    impact_scope: Optional[str] = Field(None, max_length=64)
    solution_type: Optional[str] = Field(None, max_length=64)
    lesson_learned: Optional[str] = None

    @field_validator("discovery_date", "resolve_date", "go_live_date", mode="before")
    @classmethod
    def _empty_to_none(cls, v):
        if v is None or v == "":
            return None
        return v


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
    closed_loop_rate: float = 0  # 闭环率(%) = (已解决+已关闭)/总数
    by_type: List[IssueStatsItem]
    by_category: List[IssueStatsItem] = []
