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
    value_text: str = ""  # 非整数值（如百分比 96.7%）优先展示；空则回退 value
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
    overdueDev: int = 0  # 开发中且建单超20天的需求数
    devCount: int = 0  # 开发中数量


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
    researchTotal: int = 0  # 其中一线调研工单数（口径标注「含一线调研 X + Y」）


class ModuleStatsMeetings(BaseModel):
    totalThisWeek: int = 0
    today: int = 0
    upcoming: int = 0
    pendingMinutes: int = 0  # 已召开但未写纪要的会议数


class ModuleStatsKnowledge(BaseModel):
    total: int = 0
    thisWeek: int = 0
    domainCount: int = 0  # 启用的业务领域数


class ModuleStatsAiCenter(BaseModel):
    """AI 中心（AI 总结 + 可用大模型）。"""

    total: int = 0  # AI 总结累计篇数
    thisWeek: int = 0  # 本周新增篇数
    modelCount: int = 0  # 启用的大模型数


class ModuleStatsMaterials(BaseModel):
    """业务资料库。"""

    total: int = 0
    thisWeek: int = 0
    categoryCount: int = 0


class ModuleStatsEmails(BaseModel):
    todaySent: int = 0
    weekSent: int = 0
    successRate: float = 0.0


class ModuleStatsActiveOptimization(BaseModel):
    total: int = 0
    pending: int = 0
    adopted: int = 0
    rejected: int = 0
    thisWeek: int = 0


class ModuleStats(BaseModel):
    requirements: ModuleStatsRequirements = ModuleStatsRequirements()
    tickets: ModuleStatsTickets = ModuleStatsTickets()
    issues: ModuleStatsIssues = ModuleStatsIssues()
    meetings: ModuleStatsMeetings = ModuleStatsMeetings()
    knowledge: ModuleStatsKnowledge = ModuleStatsKnowledge()
    emails: ModuleStatsEmails = ModuleStatsEmails()
    activeOptimization: ModuleStatsActiveOptimization = ModuleStatsActiveOptimization()
    aiCenter: ModuleStatsAiCenter = ModuleStatsAiCenter()
    materials: ModuleStatsMaterials = ModuleStatsMaterials()


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
    color: str = "green"  # red | amber | green | blue
    text: str = ""
    time: str = ""
    source: str = ""  # 来源徽标：调研/运营/会议/需求/知识


class FocusItem(BaseModel):
    """首页「今日聚焦」条目：个人待办 + 任务中心今日到期/超期合并排序。"""

    priority: str = "P3"  # P0 | P1 | P2 | P3
    title: str = ""
    date_text: str = ""  # 超期 N 天 / 今日 / MM-DD
    overdue: bool = False  # True=红色超期文案，False=中性日期
    source_url: str = ""


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


class TaskCenterDistItem(BaseModel):
    """任务中心分布单项。"""

    name: str = ""
    value: int = 0


class TaskCenterDist(BaseModel):
    """看板「任务中心」分布卡片。"""

    total: int = 0
    overdue: int = 0
    due_soon: int = 0
    due_today: int = 0  # 今日到期（未完成）
    by_source: List[TaskCenterDistItem] = []
    by_priority: List[TaskCenterDistItem] = []
    by_status: List[TaskCenterDistItem] = []
    overdue_items: List[TodoCardItem] = []


class PersonnelStats(BaseModel):
    """看板「人员中台」统计卡片。"""

    org_count: int = 0
    staff_count: int = 0
    enabled_staff: int = 0
    org_list: List[str] = []


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
    user_name: str = "老大"
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
    focus_items: List[FocusItem] = []  # 今日聚焦（个人待办+任务中心合并排序）

    # —— db-2 看板重构扩展字段 ——
    module_stats: Optional[ModuleStats] = None
    trend_charts: Optional[Dict[str, List[TrendPoint]]] = None
    distribution_charts: Optional[Dict[str, List[DistributionItem]]] = None
    progress_items: Optional[Dict[str, List[ProgressItem]]] = None
    pending_minutes_meetings: List[dict] = []  # 待处理会议纪要列表（held 且 summary 空）

    # —— 看板重构：任务中心高颗粒度分布 / 人员中台概览 ——
    task_center_dist: Optional[TaskCenterDist] = None
    personnel: Optional[PersonnelStats] = None
