from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from db.models import (
    PmwbDevTicket,
    PmwbKnowledgeItem,
    PmwbMeeting,
    PmwbOperationIssue,
    PmwbRequirementExt,
    PmwbTodo,
    SentEmail,
)
from schemas.dashboard import (
    AlertItem,
    DashboardData,
    DashboardStats,
    GreetStat,
    KpiItem,
    LiveItem,
    RequirementSummaryItem,
    ScheduleItem,
    TicketStatus,
    TodoCardItem,
)

# 中国时区（UTC+8）。看板按中国本地日期统计，避免 UTC 在晚间把"今天/本周"算错。
CST = timezone(timedelta(hours=8))

_WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _now_cst() -> datetime:
    return datetime.now(CST)


def _cst_date() -> datetime.date:
    return _now_cst().date()


def _week_bounds_cst():
    today = _cst_date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)
    return today, week_start, week_end


def _cst_day_utc_bounds(day: datetime.date):
    """中国本地某日 00:00 对应的 UTC naive 上下界（库表 DateTime 以 UTC 存储）。"""
    start = datetime(day.year, day.month, day.day) - timedelta(hours=8)
    return start, start + timedelta(days=1)


def _weekday_cn(day: datetime.date) -> str:
    return _WEEKDAY_CN[day.weekday()]


def _rel_time(dt: Optional[datetime]) -> str:
    """相对时间文案（库表为 UTC，与 datetime.utcnow() 对齐）。"""
    if not dt:
        return "—"
    delta = datetime.utcnow() - dt
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
        ws_utc, _ = _cst_day_utc_bounds(week_start)
        we_utc = _cst_day_utc_bounds(week_end)[0]
        today_start_utc, today_end_utc = _cst_day_utc_bounds(today)

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

        meeting_this_week = (
            self.db.query(func.count(PmwbMeeting.id))
            .filter(PmwbMeeting.start_time >= ws_utc, PmwbMeeting.start_time < we_utc)
            .scalar()
        )
        meeting_today = (
            self.db.query(func.count(PmwbMeeting.id))
            .filter(PmwbMeeting.start_time >= today_start_utc, PmwbMeeting.start_time < today_end_utc)
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

    def get_kpis(self, stats: DashboardStats) -> List[KpiItem]:
        _, week_start, week_end = _week_bounds_cst()
        ws_utc, _ = _cst_day_utc_bounds(week_start)
        we_utc = _cst_day_utc_bounds(week_end)[0]

        req_this_week = (
            self.db.query(func.count(PmwbRequirementExt.id))
            .filter(PmwbRequirementExt.created_at >= ws_utc, PmwbRequirementExt.created_at < we_utc)
            .scalar()
        )
        req_in_review = (
            self.db.query(func.count(PmwbRequirementExt.id))
            .filter(PmwbRequirementExt.status.in_(["proposed", "accepted"]))
            .scalar()
        )
        dev_in_progress = (
            self.db.query(func.count(PmwbDevTicket.id))
            .filter(PmwbDevTicket.status.in_(["created", "design_reviewed", "dev_completed", "test_completed"]))
            .scalar()
        )
        dev_done_this_week = (
            self.db.query(func.count(PmwbDevTicket.id))
            .filter(PmwbDevTicket.go_live_date >= week_start, PmwbDevTicket.go_live_date < week_end)
            .scalar()
        )

        return [
            KpiItem(
                value=stats.todo_total,
                color="blue",
                label="我的待办",
                delta=f"超期 {stats.todo_overdue} 条" if stats.todo_overdue else "无超期",
                delta_type="down" if stats.todo_overdue else "neutral",
            ),
            KpiItem(
                value=req_this_week,
                color="amber",
                label="本周新增需求",
                delta=f"跟踪中 {req_in_review}",
                delta_type="neutral",
            ),
            KpiItem(
                value=dev_in_progress,
                color="blue",
                label="进行中工单",
                delta=f"本周完成 {dev_done_this_week}",
                delta_type="up",
            ),
            KpiItem(
                value=stats.issue_overdue,
                color="red",
                label="运营预警",
                delta=f"待处理 {stats.issue_pending} 条",
                delta_type="down" if stats.issue_overdue else "neutral",
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
        ext_map = {
            ext.req_id: ext.status
            for ext in self.db.query(PmwbRequirementExt.req_id, PmwbRequirementExt.status).all()
        }
        items = (
            self.db.query(SentEmail)
            .order_by(SentEmail.created_at.desc())
            .limit(limit)
            .all()
        )
        result = []
        for se in items:
            st = ext_map.get(se.req_id, "proposed")
            date = ""
            if se.send_datetime:
                import re as _re

                m = _re.search(r"\d{4}[/-]\d{1,2}[/-]\d{1,2}", se.send_datetime)
                date = m.group(0) if m else se.send_datetime.strip()[:10]
            elif se.created_at:
                date = se.created_at.strftime("%Y-%m-%d")
            result.append(
                RequirementSummaryItem(
                    name=se.req_name or se.req_id or "未命名需求",
                    owner=se.proposer or "",
                    status=_REQ_STATUS_CN.get(st, "待排期"),
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
        # start_time 以 UTC 存储，按中国本地日期匹配今日日程
        today_cst = _now_cst().replace(hour=0, minute=0, second=0, microsecond=0)
        s = (today_cst - timedelta(hours=8)).replace(tzinfo=None)
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
                time=(item.start_time + timedelta(hours=8)).strftime("%H:%M") if item.start_time else "",
                title=item.title or "",
                loc=item.location or "待定",
            )
            for item in items
        ]

    def get_live_status(self, recent_issues: List[dict], limit: int = 5) -> List[LiveItem]:
        result = []
        for it in recent_issues[:limit]:
            lvl = it.get("impact_level")
            color = "red" if lvl in ("P0", "P1") else ("amber" if lvl in ("P2", "P3") else "green")
            result.append(
                LiveItem(
                    color=color,
                    text=f"{it.get('issue_no', '')} {it.get('title', '')}",
                    time=_rel_time(it.get("updated_at")),
                )
            )
        return result

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

    def get_greeting(self, stats: DashboardStats):
        efficiency = round(stats.issue_resolved / stats.issue_total * 100, 1) if stats.issue_total else 0.0
        sub = (
            f"本周共 {stats.meeting_this_week} 场会议，运营问题 {stats.issue_total} 条"
            f"（待处理 {stats.issue_pending}），我的待办 {stats.todo_total} 条。"
        )
        greet_stats = [
            GreetStat(value=str(stats.meeting_this_week), key="本周会议", cls="accent"),
            GreetStat(value=str(stats.issue_total), key="运营问题", cls="down"),
            GreetStat(value=str(stats.todo_total), key="我的待办", cls="up"),
            GreetStat(value=str(stats.knowledge_total), key="知识条目", cls="neutral"),
        ]
        return sub, efficiency, greet_stats

    def get_dashboard(self) -> DashboardData:
        stats = self.get_stats()
        recent_todos = self.get_recent_todos()
        recent_meetings = self.get_recent_meetings()
        recent_issues = self.get_recent_issues()

        trend_values, trend_labels = self.get_trend()
        sub, efficiency, greet_stats = self.get_greeting(stats)

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
            kpis=self.get_kpis(stats),
            trend=trend_values,
            trend_labels=trend_labels,
            ticket_status=self.get_ticket_status(),
            todos=self.get_todo_cards(),
            alerts=self.get_alerts(stats),
            recent_requirements=self.get_recent_requirements(),
            schedule=self.get_schedule(),
        )
