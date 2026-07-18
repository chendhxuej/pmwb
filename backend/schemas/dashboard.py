from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class TodoSummaryItem(BaseModel):
    id: int
    title: str
    category: str
    priority: str
    status: str
    due_date: Optional[str]
    is_overdue: bool


class TodoCardItem(BaseModel):
    """看板「我的待办」卡片项（前端 mergeDashboard 契约）。"""

    priority: str = "中等"  # 紧急 | 高优 | 中等 | 低优
    title: str = ""
    deadline: str = ""
    owner: str = ""
    overdue: bool = False


class MeetingSummaryItem(BaseModel):
    id: int
    meeting_id: str
    title: str
    meeting_type: str
    start_time: Optional[str]
    status: str


class IssueSummaryItem(BaseModel):
    id: int
    issue_no: str
    title: str
    issue_type: str
    status: str
    impact_level: str


class KpiItem(BaseModel):
    value: int = 0
    color: str = "blue"
    label: str = ""
    delta: str = ""
    delta_type: str = "neutral"  # up | down | neutral


class RequirementSummaryItem(BaseModel):
    name: str = ""
    owner: str = ""
    status: str = ""
    date: str = ""


class AlertItem(BaseModel):
    severity: str = "提醒"  # 严重 | 警告 | 正常 | 提醒
    msg: str = ""
    count: str = ""


class ScheduleItem(BaseModel):
    time: str = ""
    title: str = ""
    loc: str = ""


class LiveItem(BaseModel):
    color: str = "green"  # red | amber | green
    text: str = ""
    time: str = ""


class TicketStatus(BaseModel):
    total: int = 0
    pending: int = 0
    processing: int = 0
    resolved: int = 0
    closed: int = 0


class GreetStat(BaseModel):
    value: str = ""
    key: str = ""
    cls: str = "accent"  # up | down | accent | neutral


class DashboardStats(BaseModel):
    todo_total: int
    todo_today: int
    todo_overdue: int
    meeting_this_week: int
    meeting_today: int
    issue_total: int
    issue_pending: int
    issue_processing: int
    issue_resolved: int
    issue_overdue: int
    knowledge_total: int


class DashboardData(BaseModel):
    stats: DashboardStats
    recent_todos: List[TodoSummaryItem]
    recent_meetings: List[MeetingSummaryItem]
    recent_issues: List[IssueSummaryItem]

    # —— 前端看板契约字段（真实数据，避免回退 demo）——
    user_name: str = "陈工"
    greeting_sub: str = ""
    efficiency: float = 0
    greet_stats: List[GreetStat] = []
    live_status: List[LiveItem] = []
    kpis: List[KpiItem] = []
    trend: List[int] = []
    trend_labels: List[str] = []
    ticket_status: TicketStatus = TicketStatus()
    todos: List[TodoCardItem] = []
    alerts: List[AlertItem] = []
    recent_requirements: List[RequirementSummaryItem] = []
    schedule: List[ScheduleItem] = []
