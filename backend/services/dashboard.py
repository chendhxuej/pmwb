from datetime import datetime, timedelta, timezone
from typing import List, Optional
import logging

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from db.models import (
    EmailRecord,
    PmwbActiveOptimization,
    PmwbBusinessDomain,
    PmwbDevTicket,
    PmwbKeyWork,
    PmwbKnowledgeItem,
    PmwbLlmProvider,
    PmwbMaterial,
    PmwbMaterialCategory,
    PmwbMeeting,
    PmwbOperationIssue,
    PmwbResearchIssue,
    PmwbRequirementExt,
    PmwbTodo,
    PmwbWorkReport,
    SentEmail,
)
from schemas.dashboard import (
    AlertItem,
    DashboardData,
    DashboardStats,
    DistributionItem,
    FocusItem,
    GreetStat,
    KpiItem,
    LiveItem,
    ModuleStats,
    ModuleStatsActiveOptimization,
    ModuleStatsAiCenter,
    ModuleStatsEmails,
    ModuleStatsIssues,
    ModuleStatsKnowledge,
    ModuleStatsMaterials,
    ModuleStatsMeetings,
    ModuleStatsRequirements,
    ModuleStatsTickets,
    ProgressItem,
    RequirementSummaryItem,
    ScheduleItem,
    TaskCenterDist,
    TaskCenterDistItem,
    PersonnelStats,
    TicketStatus,
    TodoCardItem,
    TrendPoint,
)
from schemas.task_center import SOURCE_LABELS, TASK_SOURCES
from services.task_center import TaskCenterService
from utils.master_service import master_service_client

# 中国时区（UTC+8）。看板按中国本地日期统计，避免 UTC 在晚间把"今天/本周"算错。
CST = timezone(timedelta(hours=8))

_WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

logger = logging.getLogger(__name__)


def _now_cst() -> datetime:
    return datetime.now(CST)


def _cst_date() -> datetime.date:
    return _now_cst().date()


def _week_bounds_cst():
    today = _cst_date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)
    return today, week_start, week_end


def _day_start(day: datetime.date) -> datetime:
    """本地日期 -> 当天 00:00 的 naive datetime。

    会议 start_time 按本地时间（Asia/Shanghai）naive 存储，统计须用本地日期口径。
    这里统一用 naive datetime 区间比较，而不是 cast(col, Date)：
    SQLite 下 CAST(x AS DATE) 走 numeric affinity（"2026-08-05 ..." -> 2026），
    与 date 比较恒不匹配，会让测试库统计恒为 0（MySQL 则正常）。
    """
    return datetime.combine(day, datetime.min.time())


def _cst_day_utc_bounds(day: datetime.date):
    """中国本地某日 00:00 ~ 次日 00:00 的 naive datetime 上下界。

    created_at/updated_at 已从 UTC 改为 UTC+8 存储，直接用本地日期边界。
    """
    start = _day_start(day)
    return start, start + timedelta(days=1)


def _weekday_cn(day: datetime.date) -> str:
    return _WEEKDAY_CN[day.weekday()]


def _rel_time(dt: Optional[datetime]) -> str:
    """相对时间文案（库表已统一 UTC+8 存储，与 datetime.now() 对齐）。"""
    if not dt:
        return "—"
    delta = datetime.now() - dt
    if delta < timedelta(minutes=1):
        return "刚刚"
    if delta < timedelta(hours=1):
        return f"{int(delta.total_seconds() // 60)} 分钟前"
    if delta < timedelta(days=1):
        return f"{int(delta.total_seconds() // 3600)} 小时前"
    if delta < timedelta(days=2):
        return "昨天"
    return f"{delta.days} 天前"


_PRIORITY_CN = {"P0": "紧急", "P1": "高优", "P2": "中等", "P3": "低优"}
_REQ_STATUS_CN = {
    "proposed": "待排期",
    "accepted": "评审中",
    "dev": "开发中",
    "closed": "已上线",
    "paused": "已暂停",
}


class DashboardService:
    """首页看板数据聚合 Service。"""

    def __init__(self, db: Session):
        self.db = db

    def get_stats(self) -> DashboardStats:
        today, week_start, week_end = _week_bounds_cst()

        todo_total = self.db.query(func.count(PmwbTodo.id)).scalar()
        todo_today = (
            self.db.query(func.count(PmwbTodo.id))
            .filter(PmwbTodo.due_date == today)
            .scalar()
        )
        todo_overdue = (
            self.db.query(func.count(PmwbTodo.id))
            .filter(PmwbTodo.due_date < today, PmwbTodo.status != "done")
            .scalar()
        )

        # 会议 start_time 按本地时间（Asia/Shanghai）naive 存储，用本地日期区间统计，避免 UTC 边界少算一天
        meeting_this_week = (
            self.db.query(func.count(PmwbMeeting.id))
            .filter(PmwbMeeting.start_time >= _day_start(week_start),
                    PmwbMeeting.start_time < _day_start(week_end))
            .scalar()
        )
        meeting_today = (
            self.db.query(func.count(PmwbMeeting.id))
            .filter(PmwbMeeting.start_time >= _day_start(today),
                    PmwbMeeting.start_time < _day_start(today + timedelta(days=1)))
            .scalar()
        )

        issue_total = self.db.query(func.count(PmwbOperationIssue.id)).scalar()
        issue_pending = (
            self.db.query(func.count(PmwbOperationIssue.id))
            .filter(PmwbOperationIssue.status == "pending")
            .scalar()
        )
        issue_processing = (
            self.db.query(func.count(PmwbOperationIssue.id))
            .filter(PmwbOperationIssue.status == "processing")
            .scalar()
        )
        issue_resolved = (
            self.db.query(func.count(PmwbOperationIssue.id))
            .filter(PmwbOperationIssue.status.in_(["resolved", "closed"]))
            .scalar()
        )
        issue_overdue = (
            self.db.query(func.count(PmwbOperationIssue.id))
            .filter(PmwbOperationIssue.is_overdue == 1)
            .scalar()
        )

        knowledge_total = self.db.query(func.count(PmwbKnowledgeItem.id)).scalar()

        return DashboardStats(
            todo_total=todo_total,
            todo_today=todo_today,
            todo_overdue=todo_overdue,
            meeting_this_week=meeting_this_week,
            meeting_today=meeting_today,
            issue_total=issue_total,
            issue_pending=issue_pending,
            issue_processing=issue_processing,
            issue_resolved=issue_resolved,
            issue_overdue=issue_overdue,
            knowledge_total=knowledge_total,
        )

    def get_recent_todos(self, limit: int = 5) -> List[dict]:
        today = _cst_date()
        has_due = case((PmwbTodo.due_date.isnot(None), 0), else_=1)
        items = (
            self.db.query(PmwbTodo)
            .filter(PmwbTodo.status != "done")
            .order_by(has_due.asc(), PmwbTodo.due_date.asc(), PmwbTodo.priority.asc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": item.id,
                "title": item.title,
                "category": item.category,
                "priority": item.priority,
                "status": item.status,
                "due_date": item.due_date.isoformat() if item.due_date else None,
                "is_overdue": bool(item.due_date and item.due_date < today and item.status != "done"),
            }
            for item in items
        ]

    def get_recent_meetings(self, limit: int = 5) -> List[dict]:
        items = (
            self.db.query(PmwbMeeting)
            .filter(PmwbMeeting.status == "planned")
            .order_by(PmwbMeeting.start_time.asc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": item.id,
                "meeting_id": item.meeting_id,
                "title": item.title,
                "meeting_type": item.meeting_type,
                "start_time": item.start_time.isoformat() if item.start_time else None,
                "status": item.status,
            }
            for item in items
        ]

    def get_recent_issues(self, limit: int = 5) -> List[dict]:
        items = (
            self.db.query(PmwbOperationIssue)
            .filter(PmwbOperationIssue.status.notin_(["resolved", "closed"]))
            .order_by(PmwbOperationIssue.updated_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": item.id,
                "issue_no": item.issue_no,
                "title": item.title,
                "issue_type": item.issue_type,
                "status": item.status,
                "impact_level": item.impact_level,
                "updated_at": item.updated_at,
            }
            for item in items
        ]

    # ───────────────── 看板契约字段（真实数据） ─────────────────

    def get_kpis(
        self,
        stats: DashboardStats,
        module_stats: Optional[ModuleStats] = None,
        task_center: Optional[TaskCenterDist] = None,
    ) -> List[KpiItem]:
        """首页 KPI 换血（2026-09-15 看板 2.0）：
        我的待办（任务中心口径）/ 本周会议 / 跟踪中需求 / 邮件 7 日成功率。
        旧「进行中工单」（查空表 PmwbDevTicket 恒 0）与「运营预警」（口径失真）废弃。
        """
        ms = module_stats or self.get_module_stats()
        tc = task_center or self.get_task_center_dist()

        # KPI1 我的待办（任务中心六源聚合口径）
        todo_delta = f"超期 {tc.overdue} · 今日到期 {tc.due_today}" if tc.overdue else f"今日到期 {tc.due_today}"
        # KPI2 本周会议
        pending_minutes = ms.meetings.pendingMinutes if ms else 0
        # KPI3 跟踪中需求（评审/待排期），附开发中与超期开发
        # KPI4 邮件 7 日成功率（非整数，走 value_text）
        sr = ms.emails.successRate if ms else 0.0

        return [
            KpiItem(
                value=tc.total,
                color="blue",
                label="我的待办（任务中心）",
                delta=todo_delta,
                delta_type="down" if tc.overdue else "neutral",
            ),
            KpiItem(
                value=stats.meeting_this_week,
                color="amber",
                label="本周会议",
                delta=f"待写纪要 {pending_minutes}" if pending_minutes else "纪要已清",
                delta_type="down" if pending_minutes else "neutral",
            ),
            KpiItem(
                value=ms.requirements.inReview if ms else 0,
                color="amber",
                label="跟踪中需求",
                delta=f"开发中 {ms.requirements.devCount} · 超期开发 {ms.requirements.overdueDev}" if ms else "",
                delta_type="neutral",
            ),
            KpiItem(
                value=round(sr),
                value_text=f"{sr}%",
                color="green",
                label="邮件 7 日成功率",
                delta=f"本周发送 {ms.emails.weekSent}" if ms else "",
                delta_type="neutral",
            ),
        ]

    def get_trend(self):
        """近 7 天（中国本地日）需求新增量。"""
        today = _cst_date()
        days = [today - timedelta(days=i) for i in range(6, -1, -1)]
        labels, values = [], []
        for d in days:
            s, e = _cst_day_utc_bounds(d)
            c = (
                self.db.query(func.count(PmwbRequirementExt.id))
                .filter(PmwbRequirementExt.created_at >= s, PmwbRequirementExt.created_at < e)
                .scalar()
            )
            labels.append(_weekday_cn(d))
            values.append(c)
        return values, labels

    def get_ticket_status(self) -> TicketStatus:
        pending = (
            self.db.query(func.count(PmwbDevTicket.id))
            .filter(PmwbDevTicket.status.in_(["created", "design_reviewed"]))
            .scalar()
        )
        processing = (
            self.db.query(func.count(PmwbDevTicket.id))
            .filter(PmwbDevTicket.status.in_(["dev_completed", "test_completed"]))
            .scalar()
        )
        resolved = (
            self.db.query(func.count(PmwbDevTicket.id))
            .filter(PmwbDevTicket.status == "live")
            .scalar()
        )
        closed = (
            self.db.query(func.count(PmwbDevTicket.id))
            .filter(PmwbDevTicket.status == "archived")
            .scalar()
        )
        return TicketStatus(
            total=pending + processing + resolved + closed,
            pending=pending,
            processing=processing,
            resolved=resolved,
            closed=closed,
        )

    def get_recent_requirements(self, limit: int = 5) -> List[RequirementSummaryItem]:
        """最近需求：直接查需求主表，按更新时间倒序。

        口径修正：原实现从已发邮件(sent_emails)倒推，只显示发过邮件的需求、
        且按发邮件时间排序，会漏掉未发邮件的需求。现改查需求主表 pmwb_requirement_ext。
        """
        items = (
            self.db.query(PmwbRequirementExt)
            .order_by(PmwbRequirementExt.updated_at.desc())
            .limit(limit)
            .all()
        )
        req_ids = [it.req_id for it in items if it.req_id]
        proposer_map = {}
        if req_ids:
            rows = (
                self.db.query(SentEmail.req_id, SentEmail.proposer)
                .filter(SentEmail.req_id.in_(req_ids))
                .all()
            )
            for r in rows:
                proposer_map.setdefault(r.req_id, r.proposer or "")
        result = []
        for it in items:
            date = ""
            if it.updated_at:
                date = it.updated_at.strftime("%Y-%m-%d") if it.updated_at else ""
            result.append(
                RequirementSummaryItem(
                    name=it.req_name or it.req_id or "未命名需求",
                    owner=proposer_map.get(it.req_id, ""),
                    status=_REQ_STATUS_CN.get(it.status, "待排期"),
                    date=date,
                )
            )
        return result

    def get_alerts(self, stats: DashboardStats) -> List[AlertItem]:
        alerts: List[AlertItem] = []
        if stats.issue_overdue > 0:
            alerts.append(AlertItem(severity="严重", msg="超期未处理运营问题", count=f"{stats.issue_overdue} 条"))
        if stats.issue_pending > 0:
            alerts.append(AlertItem(severity="警告", msg="待处理运营问题", count=f"{stats.issue_pending} 条"))
        if stats.issue_processing > 0:
            alerts.append(AlertItem(severity="提醒", msg="处理中运营问题", count=f"{stats.issue_processing} 条"))
        alerts.append(AlertItem(severity="正常", msg="系统巡检", count="所有服务运行正常"))
        return alerts

    def get_schedule(self, limit: int = 5) -> List[ScheduleItem]:
        # start_time 按本地时间（Asia/Shanghai）naive 存储，直接以本地日期匹配今日日程
        today_cst = _now_cst().replace(hour=0, minute=0, second=0, microsecond=0)
        s = today_cst.replace(tzinfo=None)
        e = s + timedelta(days=1)
        items = (
            self.db.query(PmwbMeeting)
            .filter(PmwbMeeting.start_time >= s, PmwbMeeting.start_time < e)
            .order_by(PmwbMeeting.start_time.asc())
            .limit(limit)
            .all()
        )
        return [
            ScheduleItem(
                time=item.start_time.strftime("%H:%M") if item.start_time else "",
                title=item.title or "",
                loc=item.location or "待定",
            )
            for item in items
        ]

    def get_live_status(self, recent_issues: List[dict], limit: int = 5) -> List[LiveItem]:
        """实时动态 · 多源聚合（2026-09-15 看板 2.0）：
        调研 / 运营 / 会议 / 需求 / 知识 各取最新 1 条，按时间倒序混排。
        """
        candidates: List[tuple] = []  # (排序时间, LiveItem)

        # 调研：最新超期调研工单优先，否则最新一条
        try:
            q = self.db.query(PmwbResearchIssue)
            ri = q.filter(PmwbResearchIssue.is_overdue == 1).order_by(
                PmwbResearchIssue.updated_at.desc()
            ).first() or q.order_by(PmwbResearchIssue.updated_at.desc()).first()
            if ri is not None:
                _t = ri.updated_at or ri.created_at
                candidates.append((_t, LiveItem(
                    color="red" if ri.is_overdue else "amber",
                    text=f"{ri.issue_no or ''} {(ri.title or '').strip()}".strip() or "一线调研工单更新",
                    time=_rel_time(_t),
                    source="调研",
                )))
        except Exception as e:  # noqa: BLE001
            logger.warning("实时动态-调研源失败: %s", e)

        # 运营：最新未完结工单
        for it in recent_issues[:2]:
            candidates.append((it.get("updated_at"), LiveItem(
                color="red" if it.get("impact_level") in ("P0", "P1") else "amber",
                text=f"{it.get('issue_no', '')} {it.get('title', '')}".strip(),
                time=_rel_time(it.get("updated_at")),
                source="运营",
            )))

        # 会议：最新待写纪要
        try:
            m = (
                self.db.query(PmwbMeeting)
                .filter(PmwbMeeting.status == "held")
                .order_by(PmwbMeeting.start_time.desc())
                .first()
            )
            if m is not None and (m.summary is None or m.summary == ""):
                candidates.append((m.start_time, LiveItem(
                    color="amber",
                    text=f"「{m.title}」已召开，纪要待补",
                    time=m.start_time.strftime("%m-%d") if m.start_time else "—",
                    source="会议",
                )))
        except Exception as e:  # noqa: BLE001
            logger.warning("实时动态-会议源失败: %s", e)

        # 需求：最新已上线
        try:
            r = (
                self.db.query(PmwbRequirementExt)
                .filter(PmwbRequirementExt.status == "closed")
                .order_by(PmwbRequirementExt.updated_at.desc())
                .first()
            )
            if r is not None:
                candidates.append((r.updated_at, LiveItem(
                    color="green",
                    text=f"{(r.req_name or '').strip()} 已上线",
                    time=r.updated_at.strftime("%m-%d") if r.updated_at else "—",
                    source="需求",
                )))
        except Exception as e:  # noqa: BLE001
            logger.warning("实时动态-需求源失败: %s", e)

        # 知识：最新归档条目
        try:
            k = (
                self.db.query(PmwbKnowledgeItem)
                .order_by(PmwbKnowledgeItem.created_at.desc())
                .first()
            )
            if k is not None:
                candidates.append((k.created_at, LiveItem(
                    color="blue",
                    text=f"{(k.title or '').strip()} 已归档至领域库",
                    time=k.created_at.strftime("%m-%d") if k.created_at else "—",
                    source="知识",
                )))
        except Exception as e:  # noqa: BLE001
            logger.warning("实时动态-知识源失败: %s", e)

        # 按时间倒序（None 排最后），截取 limit 条
        candidates.sort(key=lambda x: x[0] or datetime.min, reverse=True)
        return [item for _, item in candidates[:limit]]

    def get_focus_items(self, limit: int = 6) -> List[FocusItem]:
        """今日聚焦（2026-09-15 看板 2.0）：个人待办 + 任务中心今日到期/超期/临期合并智能排序。

        排序规则：超期优先（超期越久越靠前）→ 今日到期 → 3 日内临期 → 本周。
        优先级取统一任务 priority（P0-P3，无则 P3）。
        """
        today = _cst_date()
        try:
            items = TaskCenterService()._collect(self.db)
        except Exception as e:  # noqa: BLE001
            logger.warning("今日聚焦-任务中心聚合失败: %s", e)
            return []

        selected = []
        for t in items:
            if t.status == "done":
                continue
            if not (t.is_overdue or t.due_date == today or t.is_due_soon):
                continue
            overdue_days = (today - t.due_date).days if (t.is_overdue and t.due_date) else 0
            if t.is_overdue:
                date_text = f"超期 {max(overdue_days, 1)} 天" if overdue_days > 0 else "已超期"
            elif t.due_date == today:
                date_text = "今日"
            else:
                date_text = t.due_date.strftime("%m-%d") if t.due_date else ""
            selected.append((t.is_overdue, t.due_date or today, FocusItem(
                priority=t.priority or "P3",
                title=(t.title or "未命名任务").strip(),
                date_text=date_text,
                overdue=t.is_overdue,
                source_url=t.source_url or "",
            )))

        # 超期在前；同为超期按截止日期升序（超期越久越靠前）；非超期按截止日期升序
        selected.sort(key=lambda x: (not x[0], x[1]))
        return [item for _, _, item in selected[:limit]]

    def get_todo_cards(self, limit: int = 5) -> List[TodoCardItem]:
        raw = self.get_recent_todos(limit)
        cards = []
        for it in raw:
            priority = _PRIORITY_CN.get(it["priority"], "中等")
            due = it.get("due_date")
            deadline = f"{due} 截止" if due else ""
            cards.append(
                TodoCardItem(
                    priority=priority,
                    title=it["title"] or "未命名待办",
                    deadline=deadline,
                    owner="",
                    overdue=it["is_overdue"],
                )
            )
        return cards

    def get_greeting(
        self,
        stats: DashboardStats,
        module_stats: Optional[ModuleStats] = None,
        task_center: Optional[TaskCenterDist] = None,
    ):
        """问候区（2026-09-15 看板 2.0）：闭环率/文案与运营工单卡同口径（含一线调研）。"""
        ms = module_stats or self.get_module_stats()
        tc = task_center or self.get_task_center_dist()

        efficiency = round(ms.issues.resolved / ms.issues.total * 100, 1) if ms.issues.total else 0.0
        sub = (
            f"本周共 {stats.meeting_this_week} 场会议，运营问题 {ms.issues.total} 条"
            f"（含一线调研 {ms.issues.researchTotal}，待处理 {ms.issues.pending}），"
            f"我的待办 {tc.total} 条、{tc.overdue} 条超期。"
        )
        greet_stats = [
            GreetStat(value=str(stats.meeting_this_week), key="本周会议", cls="accent"),
            GreetStat(value=str(tc.overdue), key="超期任务", cls="down"),
            GreetStat(value=str(tc.due_soon), key="3日内到期", cls="up"),
            GreetStat(value=str(ms.meetings.pendingMinutes), key="待写纪要", cls="down"),
        ]
        return sub, efficiency, greet_stats

    def get_module_stats(self) -> ModuleStats:
        """db-2 扩展：各模块统计卡片。"""
        today, week_start, week_end = _week_bounds_cst()
        ws_utc, _ = _cst_day_utc_bounds(week_start)
        we_utc = _cst_day_utc_bounds(week_end)[0]
        today_start_utc, today_end_utc = _cst_day_utc_bounds(today)

        # 需求
        req_total = self.db.query(func.count(PmwbRequirementExt.id)).scalar() or 0
        req_this_week = self.db.query(func.count(PmwbRequirementExt.id)).filter(
            PmwbRequirementExt.created_at >= ws_utc,
            PmwbRequirementExt.created_at < we_utc,
        ).scalar() or 0
        req_in_review = self.db.query(func.count(PmwbRequirementExt.id)).filter(
            PmwbRequirementExt.status.in_(["proposed", "accepted"]),
        ).scalar() or 0
        req_completed = self.db.query(func.count(PmwbRequirementExt.id)).filter(
            PmwbRequirementExt.status == "closed",
        ).scalar() or 0
        # 需求开发超期：状态=开发中(dev) 且 建单时间超20天
        req_overdue_cutoff = datetime.now() - timedelta(days=20)
        req_overdue_dev = self.db.query(func.count(PmwbRequirementExt.id)).filter(
            PmwbRequirementExt.status == "dev",
            PmwbRequirementExt.created_at < req_overdue_cutoff,
        ).scalar() or 0
        req_dev_count = self.db.query(func.count(PmwbRequirementExt.id)).filter(
            PmwbRequirementExt.status == "dev",
        ).scalar() or 0

        # 工单
        ticket_total = self.db.query(func.count(PmwbDevTicket.id)).scalar() or 0
        ticket_pending = self.db.query(func.count(PmwbDevTicket.id)).filter(
            PmwbDevTicket.status.in_(["created", "design_reviewed"]),
        ).scalar() or 0
        ticket_processing = self.db.query(func.count(PmwbDevTicket.id)).filter(
            PmwbDevTicket.status.in_(["dev_completed", "test_completed"]),
        ).scalar() or 0
        ticket_resolved = self.db.query(func.count(PmwbDevTicket.id)).filter(
            PmwbDevTicket.status == "live",
        ).scalar() or 0
        ticket_closed = self.db.query(func.count(PmwbDevTicket.id)).filter(
            PmwbDevTicket.status == "archived",
        ).scalar() or 0

        # 运营问题（复用 get_stats）
        stats = self.get_stats()

        # 一线调研工单（与运营问题合并统计，统一展示在首页「运营工单」卡片）
        research_total = 0
        research_pending = 0
        research_overdue = 0
        try:
            research_total = self.db.query(func.count(PmwbResearchIssue.id)).scalar() or 0
            research_pending = self.db.query(func.count(PmwbResearchIssue.id)).filter(PmwbResearchIssue.status == "pending").scalar() or 0
            research_processing = self.db.query(func.count(PmwbResearchIssue.id)).filter(PmwbResearchIssue.status == "processing").scalar() or 0
            research_resolved = self.db.query(func.count(PmwbResearchIssue.id)).filter(PmwbResearchIssue.status.in_(["resolved", "closed"])).scalar() or 0
            research_overdue = self.db.query(func.count(PmwbResearchIssue.id)).filter(PmwbResearchIssue.is_overdue == 1).scalar() or 0
            # 合并统计：运营问题 + 一线调研
            issues_total = (stats.issue_total or 0) + research_total
            issues_pending = (stats.issue_pending or 0) + research_pending
            issues_processing = (stats.issue_processing or 0) + research_processing
            issues_resolved = (stats.issue_resolved or 0) + research_resolved
            issues_overdue = (stats.issue_overdue or 0) + research_overdue
        except Exception:  # noqa: BLE001
            issues_total = stats.issue_total or 0
            issues_pending = stats.issue_pending or 0
            issues_processing = stats.issue_processing or 0
            issues_resolved = stats.issue_resolved or 0
            issues_overdue = stats.issue_overdue or 0

        # 会议：start_time 按本地时间存储，用本地日期区间统计，避免 UTC 边界少算一天
        meeting_this_week = self.db.query(func.count(PmwbMeeting.id)).filter(
            PmwbMeeting.start_time >= _day_start(week_start),
            PmwbMeeting.start_time < _day_start(week_end),
        ).scalar() or 0
        meeting_today = self.db.query(func.count(PmwbMeeting.id)).filter(
            PmwbMeeting.start_time >= _day_start(today),
            PmwbMeeting.start_time < _day_start(today + timedelta(days=1)),
        ).scalar() or 0
        meeting_upcoming = self.db.query(func.count(PmwbMeeting.id)).filter(
            PmwbMeeting.start_time >= _day_start(today),
            PmwbMeeting.status == "planned",
        ).scalar() or 0
        # 待处理会议纪要：已召开(held) 但未写纪要摘要(summary 为空) 且需要纪要(minutes_required 非 False)
        _pending_minutes_filter = [
            PmwbMeeting.status == "held",
            or_(PmwbMeeting.summary.is_(None), PmwbMeeting.summary == ""),
            or_(PmwbMeeting.minutes_required.is_(None), PmwbMeeting.minutes_required == True),
        ]
        meeting_pending_minutes = (
            self.db.query(func.count(PmwbMeeting.id)).filter(*_pending_minutes_filter).scalar() or 0
        )

        # 知识
        kn_total = self.db.query(func.count(PmwbKnowledgeItem.id)).scalar() or 0
        kn_this_week = self.db.query(func.count(PmwbKnowledgeItem.id)).filter(
            PmwbKnowledgeItem.created_at >= ws_utc,
            PmwbKnowledgeItem.created_at < we_utc,
        ).scalar() or 0
        kn_domain_count = self.db.query(func.count(PmwbBusinessDomain.id)).filter(
            PmwbBusinessDomain.enabled == True,  # noqa: E712
        ).scalar() or 0

        # AI 中心：AI 总结（pmwb_work_report）+ 启用大模型数
        ai_total = self.db.query(func.count(PmwbWorkReport.id)).scalar() or 0
        ai_this_week = self.db.query(func.count(PmwbWorkReport.id)).filter(
            PmwbWorkReport.created_at >= ws_utc,
            PmwbWorkReport.created_at < we_utc,
        ).scalar() or 0
        ai_model_count = self.db.query(func.count(PmwbLlmProvider.id)).filter(
            PmwbLlmProvider.is_enabled == 1,
        ).scalar() or 0

        # 业务资料库：材料索引 + 启用分类数
        mat_total = self.db.query(func.count(PmwbMaterial.id)).scalar() or 0
        mat_this_week = self.db.query(func.count(PmwbMaterial.id)).filter(
            PmwbMaterial.created_at >= ws_utc,
            PmwbMaterial.created_at < we_utc,
        ).scalar() or 0
        mat_category_count = self.db.query(func.count(PmwbMaterialCategory.id)).filter(
            PmwbMaterialCategory.enabled == True,  # noqa: E712
        ).scalar() or 0

        # 邮件（从 EmailRecord 统计）
        email_today = self.db.query(func.count(EmailRecord.id)).filter(
            EmailRecord.created_at >= today_start_utc,
            EmailRecord.created_at < today_end_utc,
        ).scalar() or 0
        email_week = self.db.query(func.count(EmailRecord.id)).filter(
            EmailRecord.created_at >= ws_utc,
            EmailRecord.created_at < we_utc,
        ).scalar() or 0
        email_7d_start = ws_utc - timedelta(days=7 - (week_start - today).days)
        email_7d_total = self.db.query(func.count(EmailRecord.id)).filter(
            EmailRecord.created_at >= email_7d_start,
        ).scalar() or 0
        email_7d_ok = self.db.query(func.count(EmailRecord.id)).filter(
            EmailRecord.created_at >= email_7d_start,
            EmailRecord.send_status.in_(["success", "sent"]),
        ).scalar() or 0
        email_sr = round(email_7d_ok / email_7d_total * 100, 1) if email_7d_total > 0 else 0.0

        # 主动优化
        ao_total = self.db.query(func.count(PmwbActiveOptimization.id)).scalar() or 0
        ao_pending = self.db.query(func.count(PmwbActiveOptimization.id)).filter(
            PmwbActiveOptimization.status == "pending"
        ).scalar() or 0
        ao_adopted = self.db.query(func.count(PmwbActiveOptimization.id)).filter(
            PmwbActiveOptimization.status == "adopted"
        ).scalar() or 0
        ao_rejected = self.db.query(func.count(PmwbActiveOptimization.id)).filter(
            PmwbActiveOptimization.status == "rejected"
        ).scalar() or 0
        ao_this_week = self.db.query(func.count(PmwbActiveOptimization.id)).filter(
            PmwbActiveOptimization.created_at >= ws_utc,
            PmwbActiveOptimization.created_at < we_utc,
        ).scalar() or 0

        return ModuleStats(
            requirements=ModuleStatsRequirements(
                total=req_total, thisWeek=req_this_week, inReview=req_in_review, completed=req_completed,
                overdueDev=req_overdue_dev, devCount=req_dev_count,
            ),
            tickets=ModuleStatsTickets(
                total=ticket_total, pending=ticket_pending, processing=ticket_processing,
                resolved=ticket_resolved, closed=ticket_closed,
            ),
            issues=ModuleStatsIssues(
                total=issues_total, pending=issues_pending,
                processing=issues_processing, resolved=issues_resolved,
                overdue=issues_overdue, researchTotal=research_total,
            ),
            meetings=ModuleStatsMeetings(
                totalThisWeek=meeting_this_week, today=meeting_today, upcoming=meeting_upcoming,
                pendingMinutes=meeting_pending_minutes,
            ),
            knowledge=ModuleStatsKnowledge(total=kn_total, thisWeek=kn_this_week, domainCount=kn_domain_count),
            emails=ModuleStatsEmails(todaySent=email_today, weekSent=email_week, successRate=email_sr),
            activeOptimization=ModuleStatsActiveOptimization(
                total=ao_total, pending=ao_pending, adopted=ao_adopted, rejected=ao_rejected,
                thisWeek=ao_this_week,
            ),
            aiCenter=ModuleStatsAiCenter(total=ai_total, thisWeek=ai_this_week, modelCount=ai_model_count),
            materials=ModuleStatsMaterials(total=mat_total, thisWeek=mat_this_week, categoryCount=mat_category_count),
        )

    def get_trend_charts(self) -> dict:
        """db-2 扩展：各模块近7天趋势数据。"""
        today = _cst_date()
        days = [today - timedelta(days=i) for i in range(6, -1, -1)]

        def _daily_count(model_cls, field):
            values = []
            for d in days:
                s, e = _cst_day_utc_bounds(d)
                c = self.db.query(func.count(model_cls.id)).filter(
                    field >= s, field < e,
                ).scalar() or 0
                values.append(c)
            return [TrendPoint(label=_weekday_cn(d), value=v) for d, v in zip(days, values)]

        return {
            "requirementsTrend": _daily_count(PmwbRequirementExt, PmwbRequirementExt.created_at),
            "issuesTrend": _daily_count(PmwbOperationIssue, PmwbOperationIssue.created_at),
            "ticketsTrend": _daily_count(PmwbDevTicket, PmwbDevTicket.go_live_date),
            "activeOptimizationTrend": _daily_count(PmwbActiveOptimization, PmwbActiveOptimization.created_at),
        }

    def get_distribution_charts(self) -> dict:
        """db-2 扩展：分布数据。"""
        req_status_counts = (
            self.db.query(PmwbRequirementExt.status, func.count(PmwbRequirementExt.id))
            .group_by(PmwbRequirementExt.status)
            .all()
        )
        _REQ_STATUS_LABEL = {
            "proposed": "待排期", "accepted": "评审中", "dev": "开发中",
            "closed": "已上线", "paused": "已暂停",
        }
        req_dist = [DistributionItem(name=_REQ_STATUS_LABEL.get(s, s), value=c) for s, c in req_status_counts]

        issue_type_counts = (
            self.db.query(PmwbOperationIssue.issue_type, func.count(PmwbOperationIssue.id))
            .group_by(PmwbOperationIssue.issue_type)
            .all()
        )
        _ISSUE_TYPE_LABEL = {
            "data_abnormal": "数据异常", "system_error": "系统错误",
            "process_block": "流程阻塞", "requirement_change": "需求变更",
            "other": "其他",
        }
        issue_dist = [DistributionItem(name=_ISSUE_TYPE_LABEL.get(t, t), value=c) for t, c in issue_type_counts]

        ticket_pri_counts = (
            self.db.query(PmwbDevTicket.priority, func.count(PmwbDevTicket.id))
            .group_by(PmwbDevTicket.priority)
            .all()
        )
        ticket_dist = [DistributionItem(name=p or "未指定", value=c) for p, c in ticket_pri_counts]

        return {
            "requirementStatusDist": req_dist,
            "issueTypeDist": issue_dist,
            "ticketPriorityDist": ticket_dist,
        }

    def get_progress_items(self) -> dict:
        """db-2 扩展：重点任务进度（从重点工作模块获取）。"""
        projects = (
            self.db.query(PmwbKeyWork)
            .filter(PmwbKeyWork.status.in_(["planning", "in_progress"]))
            .order_by(PmwbKeyWork.priority.asc(), PmwbKeyWork.created_at.desc())
            .limit(10)
            .all()
        )
        items = []
        for kw in projects:
            stored_pct = kw.progress or 0
            current = 0
            total = 0
            if stored_pct > 0:
                pct = stored_pct
            else:
                # 优先按里程碑完成度计算（里程碑表有 status 字段）
                milestones = kw.milestones or []
                if milestones:
                    total = len(milestones)
                    current = sum(
                        1 for m in milestones if getattr(m, "status", None) == "completed"
                    )
                    pct = round(current / total * 100, 1) if total > 0 else 0
                else:
                    # 无里程碑时，按目标指标 current_value/target_value 估算
                    goals = kw.goals or []
                    for g in goals:
                        tv = getattr(g, "target_value", None)
                        cv = getattr(g, "current_value", None)
                        try:
                            if tv not in (None, "") and cv not in (None, ""):
                                t = float(tv)
                                c = float(cv)
                                if t > 0:
                                    total += 1
                                    if c >= t:
                                        current += 1
                                    continue
                        except (ValueError, TypeError):
                            pass
                        # 非数值型指标：只要有当前值即视为有进展
                        total += 1
                        if cv not in (None, ""):
                            current += 1
                    pct = round(current / total * 100, 1) if total > 0 else 0
            items.append(ProgressItem(
                name=kw.title,
                current=current,
                total=total,
                percent=pct,
            ))
        return {"keyProjects": items}

    def get_task_center_dist(self) -> TaskCenterDist:
        """看板「任务中心」卡片：复用任务中心聚合，输出高颗粒度分布（来源/优先级/状态）+ 超期明细。"""
        try:
            svc = TaskCenterService()
            stats = svc.get_stats(self.db)
            items = svc._collect(self.db)

            # 按来源（分类）分布，按 TASK_SOURCES 固定顺序，仅保留 >0
            src_items = [
                TaskCenterDistItem(name=SOURCE_LABELS.get(s, s), value=stats.by_source.get(s, 0))
                for s in TASK_SOURCES if stats.by_source.get(s, 0) > 0
            ]

            # 按统一状态分布
            _STATUS_LABEL = {
                "pending": "待处理",
                "in_progress": "进行中",
                "done": "已完成",
                "blocked": "已阻塞",
            }
            st_items = [
                TaskCenterDistItem(name=_STATUS_LABEL.get(k, k), value=v)
                for k, v in stats.by_status.items()
            ]

            # 按优先级分布（统一模型自带 priority）
            prio: Dict[str, int] = {}
            for t in items:
                p = t.priority or "未分级"
                prio[p] = prio.get(p, 0) + 1
            prio_order = ["紧急", "高优", "中等", "低优", "未分级"]
            prio_items = [
                TaskCenterDistItem(name=p, value=prio.get(p, 0))
                for p in prio_order if prio.get(p, 0) > 0
            ]

            # 超期任务明细
            overdue_items = [
                TodoCardItem(
                    priority=t.priority or "中等",
                    title=t.title or "未命名待办",
                    deadline=(str(t.due_date) if t.due_date else ""),
                    owner="",
                    overdue=True,
                )
                for t in items if t.is_overdue
            ]

            return TaskCenterDist(
                total=stats.total,
                overdue=stats.overdue,
                due_soon=stats.due_soon,
                due_today=sum(
                    1 for t in items if t.due_date == _cst_date() and t.status != "done"
                ),
                by_source=src_items,
                by_priority=prio_items,
                by_status=st_items,
                overdue_items=overdue_items,
            )
        except Exception as e:
            logger.warning("任务中心分布统计失败: %s", e)
            return TaskCenterDist()

    def get_personnel_stats(self) -> PersonnelStats:
        """看板「人员中台」卡片：组织 / 人员规模概览（异常时降级为空）。"""
        try:
            orgs = master_service_client.list_orgs() or []
            staffs = master_service_client.list_staffs() or []
            enabled = sum(1 for s in staffs if s.get("enabled", True))
            return PersonnelStats(
                org_count=len(orgs),
                staff_count=len(staffs),
                enabled_staff=enabled,
                org_list=[o.get("name", "") for o in orgs if o.get("name")],
            )
        except Exception as e:
            logger.warning("人员中台统计失败: %s", e)
            return PersonnelStats()

    def get_dashboard(self) -> DashboardData:
        stats = self.get_stats()
        recent_todos = self.get_recent_todos()
        recent_meetings = self.get_recent_meetings()
        recent_issues = self.get_recent_issues()

        # db-2 看板重构扩展（先聚合，供 greeting/kpis 复用同一份数据，避免口径分叉）
        module_stats = self.get_module_stats()
        trend_charts = self.get_trend_charts()
        distribution_charts = self.get_distribution_charts()
        progress_items = self.get_progress_items()
        task_center_dist = self.get_task_center_dist()
        personnel = self.get_personnel_stats()

        trend_values, trend_labels = self.get_trend()
        sub, efficiency, greet_stats = self.get_greeting(stats, module_stats, task_center_dist)

        # 待处理会议纪要列表（held 且 summary 为空），供会议卡片展示
        pending_minutes_meetings = (
            self.db.query(PmwbMeeting)
            .filter(
                PmwbMeeting.status == "held",
                or_(PmwbMeeting.summary.is_(None), PmwbMeeting.summary == ""),
            )
            .order_by(PmwbMeeting.start_time.desc())
            .limit(5)
            .all()
        )
        pending_minutes_data = [
            {
                "title": m.title,
                "meeting_id": m.meeting_id,
                "start_time": (m.start_time + timedelta(hours=8)).strftime("%Y-%m-%d") if m.start_time else "",
            }
            for m in pending_minutes_meetings
        ]

        return DashboardData(
            stats=stats,
            recent_todos=recent_todos,
            recent_meetings=recent_meetings,
            recent_issues=recent_issues,
            # 看板契约字段
            greeting_sub=sub,
            efficiency=efficiency,
            greet_stats=greet_stats,
            live_status=self.get_live_status(recent_issues),
            kpis=self.get_kpis(stats, module_stats, task_center_dist),
            focus_items=self.get_focus_items(),
            trend=trend_values,
            trend_labels=trend_labels,
            ticket_status=self.get_ticket_status(),
            todos=self.get_todo_cards(),
            alerts=self.get_alerts(stats),
            recent_requirements=self.get_recent_requirements(),
            schedule=self.get_schedule(),
            # db-2 看板重构扩展
            module_stats=module_stats,
            trend_charts=trend_charts,
            distribution_charts=distribution_charts,
            progress_items=progress_items,
            pending_minutes_meetings=pending_minutes_data,
            task_center_dist=task_center_dist,
            personnel=personnel,
        )
