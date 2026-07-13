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
