from datetime import datetime, timedelta
from typing import List

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from db.models import PmwbKnowledgeItem, PmwbMeeting, PmwbOperationIssue, PmwbTodo
from schemas.dashboard import DashboardData, DashboardStats


class DashboardService:
    """首页看板数据聚合 Service。"""

    def __init__(self, db: Session):
        self.db = db

    def get_stats(self) -> DashboardStats:
        today = datetime.utcnow().date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=7)

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
            .filter(PmwbMeeting.start_time >= week_start, PmwbMeeting.start_time < week_end)
            .scalar()
        )
        meeting_today = (
            self.db.query(func.count(PmwbMeeting.id))
            .filter(PmwbMeeting.start_time >= today, PmwbMeeting.start_time < today + timedelta(days=1))
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
        today = datetime.utcnow().date()
        # MySQL 不支持 NULLS LAST，使用 case 将有截止日期的排前面
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
            }
            for item in items
        ]

    def get_dashboard(self) -> DashboardData:
        return DashboardData(
            stats=self.get_stats(),
            recent_todos=self.get_recent_todos(),
            recent_meetings=self.get_recent_meetings(),
            recent_issues=self.get_recent_issues(),
        )
