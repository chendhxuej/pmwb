from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ResearchSubType(str, Enum):
    """调研工单子类。"""

    leader_research = "leader_research"  # 领导调研
    frontline_station = "frontline_station"  # 一线驻点


class ResearchStatus(str, Enum):
    """调研工单状态。"""

    pending = "pending"  # 待处理
    processing = "processing"  # 处理中
    verify = "verify"  # 验证中
    resolved = "resolved"  # 已解决
    closed = "closed"  # 已关闭
    suspended = "suspended"  # 已挂起


class ResearchIssueNature(str, Enum):
    """问题性质。"""

    bug = "bug"  # BUG
    optimization = "optimization"  # 优化
    invalid = "invalid"  # 非有效问题


class CityCode(str, Enum):
    """江苏省地市枚举。"""

    nanjing = "nanjing"
    suzhou = "suzhou"
    wuxi = "wuxi"
    changzhou = "changzhou"
    zhenjiang = "zhenjiang"
    yangzhou = "yangzhou"
    taizhou = "taizhou"
    nantong = "nantong"
    yancheng = "yancheng"
    huaian = "huaian"
    suqian = "suqian"
    xuzhou = "xuzhou"
    lianyungang = "lianyungang"


CITY_LABELS = {
    "nanjing": "南京",
    "suzhou": "苏州",
    "wuxi": "无锡",
    "changzhou": "常州",
    "zhenjiang": "镇江",
    "yangzhou": "扬州",
    "taizhou": "泰州",
    "nantong": "南通",
    "yancheng": "盐城",
    "huaian": "淮安",
    "suqian": "宿迁",
    "xuzhou": "徐州",
    "lianyungang": "连云港",
}


SUB_TYPE_LABELS = {
    "leader_research": "领导调研",
    "frontline_station": "一线驻点",
}


STATUS_LABELS = {
    "pending": "待处理",
    "processing": "处理中",
    "verify": "验证中",
    "resolved": "已解决",
    "closed": "已关闭",
    "suspended": "已挂起",
}


NATURE_LABELS = {
    "bug": "BUG",
    "optimization": "优化",
    "invalid": "非有效问题",
}


class ResearchIssueBase(BaseModel):
    issue_no: str = Field(..., max_length=64, description="调研工单编号")
    title: str = Field(..., max_length=255, description="工单标题")
    sub_type: ResearchSubType = Field(ResearchSubType.leader_research, description="子类")
    status: ResearchStatus = Field(ResearchStatus.pending, description="状态")
    city: Optional[CityCode] = Field(None, description="地市")
    basic_info: Optional[str] = Field(None, description="基本信息")
    situation_desc: Optional[str] = Field(None, description="情况说明")
    city_suggestion: Optional[str] = Field(None, description="地市建议")
    feedback_name: Optional[str] = Field(None, max_length=128, description="反馈人姓名")
    feedback_phone: Optional[str] = Field(None, max_length=64, description="联系电话")
    case_info: Optional[str] = Field(None, description="案例信息")
    source: Optional[str] = Field(None, max_length=128, description="信息来源")
    feedback_deadline: Optional[date] = Field(None, description="反馈截止日期")
    remark: Optional[str] = Field(None, description="备注")
    vendor_handlers: Optional[str] = Field(None, max_length=512, description="厂家责任人（逗号分隔）")
    assessment_result: Optional[str] = Field(None, description="评估结果")
    issue_nature: Optional[ResearchIssueNature] = Field(None, description="问题性质")
    solution: Optional[str] = Field(None, description="解决方案")
    business_admin: Optional[str] = Field(None, max_length=512, description="业务管理员（逗号分隔）")
    related_req_id: Optional[str] = Field(None, max_length=64, description="关联需求编号")
    related_issue_id: Optional[int] = Field(None, description="关联运营/调研工单ID")
    related_meeting_id: Optional[int] = Field(None, description="关联会议ID")
    version_plan: Optional[str] = Field(None, max_length=128, description="版本计划")
    official_feedback: Optional[str] = Field(None, description="正式反馈信息")
    domain_code: Optional[str] = Field(None, max_length=64, description="关联业务领域编码")
    impact_level: str = Field("P2", description="影响等级")
    go_live_date: Optional[date] = Field(None, description="计划完成时间")
    resolve_date: Optional[datetime] = Field(None, description="解决时间")
    is_overdue: int = Field(0, description="是否超期")
    obsidian_path: Optional[str] = Field(None, max_length=512, description="沉淀知识条目路径")
    attachments: Optional[str] = Field(None, description="附件元信息(JSON 数组字符串)")

    @field_validator("feedback_deadline", "go_live_date", mode="before")
    @classmethod
    def _empty_to_none(cls, v):
        if v is None or v == "":
            return None
        return v


class ResearchIssueCreate(ResearchIssueBase):
    pass


class ResearchIssueUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    sub_type: Optional[ResearchSubType] = None
    status: Optional[ResearchStatus] = None
    city: Optional[CityCode] = None
    basic_info: Optional[str] = None
    situation_desc: Optional[str] = None
    city_suggestion: Optional[str] = None
    feedback_name: Optional[str] = Field(None, max_length=128)
    feedback_phone: Optional[str] = Field(None, max_length=64)
    case_info: Optional[str] = None
    source: Optional[str] = Field(None, max_length=128)
    feedback_deadline: Optional[date] = None
    remark: Optional[str] = None
    vendor_handlers: Optional[str] = Field(None, max_length=512)
    assessment_result: Optional[str] = None
    issue_nature: Optional[ResearchIssueNature] = None
    solution: Optional[str] = None
    business_admin: Optional[str] = Field(None, max_length=512)
    related_req_id: Optional[str] = Field(None, max_length=64)
    related_issue_id: Optional[int] = None
    related_meeting_id: Optional[int] = None
    version_plan: Optional[str] = Field(None, max_length=128)
    official_feedback: Optional[str] = None
    domain_code: Optional[str] = Field(None, max_length=64)
    impact_level: Optional[str] = None
    go_live_date: Optional[date] = None
    resolve_date: Optional[datetime] = None
    is_overdue: Optional[int] = None
    obsidian_path: Optional[str] = Field(None, max_length=512)
    attachments: Optional[str] = None

    @field_validator("feedback_deadline", "go_live_date", mode="before")
    @classmethod
    def _empty_to_none(cls, v):
        if v is None or v == "":
            return None
        return v


class ResearchIssueOut(ResearchIssueBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResearchIssueListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int
    items: List[ResearchIssueOut]


class IssueStatsItem(BaseModel):
    name: str
    value: int


class ResearchIssueStats(BaseModel):
    total: int
    pending: int
    processing: int
    verify: int
    resolved: int
    closed: int
    suspended: int
    overdue: int
    closed_loop_rate: float = 0
    by_sub_type: List[IssueStatsItem]
    by_city: List[IssueStatsItem]
    by_nature: List[IssueStatsItem]
    by_status: List[IssueStatsItem] = []
