from datetime import datetime
from typing import Dict, List, Optional

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


# ── 看板重构扩展 Schema（db-2）──


class ModuleStatsRequirements(BaseModel):
    total: int = 0
    thisWeek: int = 0
    inReview: int = 0
    completed: int = 0


class ModuleStatsTickets(BaseModel):
    total: int = 0
    pending: int = 0
    processing: int = 0
    resolved: int = 0
    closed: int = 0


class ModuleStatsIssues(BaseModel):
    total: int = 0
    pending: int = 0
    processing: int = 0
    resolved: int = 0
    overdue: int = 0


class ModuleStatsMeetings(BaseModel):
    totalThisWeek: int = 0
    today: int = 0
    upcoming: int = 0


class ModuleStatsKnowledge(BaseModel):
    total: int = 0
    thisWeek: int = 0


class ModuleStatsEmails(BaseModel):
    todaySent: int = 0
    weekSent: int = 0
    successRate: float = 0.0


class ModuleStats(BaseModel):
    requirements: ModuleStatsRequirements = ModuleStatsRequirements()
    tickets: ModuleStatsTickets = ModuleStatsTickets()
    issues: ModuleStatsIssues = ModuleStatsIssues()
    meetings: ModuleStatsMeetings = ModuleStatsMeetings()
    knowledge: ModuleStatsKnowledge = ModuleStatsKnowledge()
    emails: ModuleStatsEmails = ModuleStatsEmails()


class TrendPoint(BaseModel):
    label: str = ""
    value: int = 0


class DistributionItem(BaseModel):
    name: str = ""
    value: int = 0


class ProgressItem(BaseModel):
    name: str = ""
    current: int = 0
    total: int = 0
    percent: float = 0.0


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

    # —— db-2 看板重构扩展字段 ——
    module_stats: Optional[ModuleStats] = None
    trend_charts: Optional[Dict[str, List[TrendPoint]]] = None
    distribution_charts: Optional[Dict[str, List[DistributionItem]]] = None
    progress_items: Optional[Dict[str, List[ProgressItem]]] = None
