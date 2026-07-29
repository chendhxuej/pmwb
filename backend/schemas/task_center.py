"""任务中心 Schema：全系统待办类任务统一聚合模型。"""

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# 任务来源枚举（六大来源）
TASK_SOURCES = [
    "todo",              # 个人待办 pmwb_todo
    "operation_issue",   # 运营问题 pmwb_operation_issue
    "dev_ticket",        # 开发工单 pmwb_dev_ticket
    "meeting_action",    # 会议行动项 pmwb_meeting_action
    "key_work",          # 重点工作（成员任务/里程碑/主项）
    "requirement_urge",  # 待催办需求（sent_emails 派生）
]

SOURCE_LABELS = {
    "todo": "个人待办",
    "operation_issue": "运营问题",
    "dev_ticket": "开发工单",
    "meeting_action": "会议行动项",
    "key_work": "重点工作",
    "requirement_urge": "需求催办",
}

# 统一状态枚举
UNIFIED_STATUSES = ["pending", "in_progress", "done", "blocked"]

STATUS_LABELS = {
    "pending": "待处理",
    "in_progress": "进行中",
    "done": "已完成",
    "blocked": "阻塞/挂起",
}


class TaskItem(BaseModel):
    """统一任务 DTO。"""

    task_id: str = Field(..., description="复合键 source:source_id")
    source: str = Field(..., description="来源标识")
    source_label: str = Field("", description="来源中文名")
    source_id: str = Field(..., description="源表主键/编号")
    title: str = Field("", description="任务标题")
    status: str = Field("pending", description="统一状态")
    status_label: str = Field("", description="统一状态中文名")
    raw_status: str = Field("", description="源表原始状态")
    owner: str = Field("", description="负责人")
    priority: Optional[str] = Field(None, description="优先级(如有)")
    due_date: Optional[date] = Field(None, description="截止日期")
    is_overdue: bool = Field(False, description="是否超期")
    is_due_soon: bool = Field(False, description="是否临期(3天内)")
    source_url: str = Field("", description="前端跳转源模块路由")
    synced_to_todo: bool = Field(False, description="会议行动项是否已同步为个人待办")
    detail: Dict[str, Any] = Field(default_factory=dict, description="源模块关键字段摘要")


class TaskStats(BaseModel):
    """任务中心统计。"""

    total: int = 0
    overdue: int = 0
    due_soon: int = 0
    by_source: Dict[str, int] = Field(default_factory=dict)
    by_status: Dict[str, int] = Field(default_factory=dict)


class TaskRef(BaseModel):
    """任务引用（发邮件用）。"""

    source: str
    source_id: str


class TaskSendRequest(BaseModel):
    """任务通知/催办邮件请求。"""

    tasks: List[TaskRef] = Field(default_factory=list, description="关联任务列表")
    to: str = Field(..., description="收件人，多个逗号/分号分隔")
    cc: Optional[str] = Field(None, description="抄送")
    subject: str = Field(..., description="邮件主题")
    body: str = Field(..., description="邮件正文")
    send_type: str = Field("urge", description="notify=通知 / urge=催办")
    operator: Optional[str] = Field(None, description="操作人")


class TaskSendResponse(BaseModel):
    success: bool
    record_ids: List[int] = Field(default_factory=list)
    message: str = ""
