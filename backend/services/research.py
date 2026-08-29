from datetime import date, datetime
from typing import Any, Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import PmwbResearchIssue
from schemas.research import IssueStatsItem, ResearchIssueStats
from services.base import BaseService


class ResearchIssueService(BaseService[PmwbResearchIssue]):
    """一线调研工单 Service。"""

    def __init__(self):
        super().__init__(PmwbResearchIssue)

    def list_with_filters(
        self,
        db: Session,
        keyword: str = None,
        city: str = None,
        sub_type: str = None,
        status: str = None,
        issue_nature: str = None,
        vendor_handler: str = None,
        business_admin: str = None,
        related_req_id: str = None,
        related_issue_id: int = None,
        related_meeting_id: int = None,
        page: int = 1,
        page_size: int = 20,
    ):
        query = db.query(self.model)

        if city:
            query = query.filter(self.model.city == city)
        if sub_type:
            query = query.filter(self.model.sub_type == sub_type)
        if status:
            query = query.filter(self.model.status == status)
        if issue_nature:
            query = query.filter(self.model.issue_nature == issue_nature)
        if vendor_handler:
            query = query.filter(self.model.vendor_handlers.like(f"%{vendor_handler}%"))
        if business_admin:
            query = query.filter(self.model.business_admin.like(f"%{business_admin}%"))
        if related_req_id:
            query = query.filter(self.model.related_req_id == related_req_id)
        if related_issue_id:
            query = query.filter(self.model.related_issue_id == related_issue_id)
        if related_meeting_id:
            query = query.filter(self.model.related_meeting_id == related_meeting_id)
        if keyword:
            like_pattern = f"%{keyword}%"
            query = query.filter(
                self.model.title.like(like_pattern)
                | self.model.issue_no.like(like_pattern)
                | self.model.vendor_handlers.like(like_pattern)
                | self.model.business_admin.like(like_pattern)
                | self.model.feedback_name.like(like_pattern)
            )

        total = query.count()

        offset = (page - 1) * page_size
        items = (
            query.order_by(self.model.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        return self._to_pagination(total, page, page_size, items)

    def _to_pagination(self, total: int, page: int, page_size: int, items: List[Any]):
        pages = (total + page_size - 1) // page_size if page_size > 0 else 1
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
            "items": items,
        }

    def _refresh_overdue(self, obj: PmwbResearchIssue) -> bool:
        """根据反馈截止日期和计划完成时间刷新超期标记。"""
        overdue = False
        today = date.today()
        if obj.feedback_deadline and obj.feedback_deadline < today:
            overdue = True
        if obj.go_live_date and obj.go_live_date < today:
            overdue = True
        new_val = 1 if overdue else 0
        if obj.is_overdue != new_val:
            obj.is_overdue = new_val
            return True
        return False

    def get(self, db: Session, id: int) -> PmwbResearchIssue | None:
        obj = super().get(db, id)
        if obj:
            # 每次读取时自动刷新超期状态
            if self._refresh_overdue(obj):
                db.commit()
                db.refresh(obj)
        return obj

    def update_status(self, db: Session, id: int, status: str, resolve_date: datetime = None):
        obj = self.get(db, id)
        if not obj:
            return None
        obj.status = status
        if resolve_date:
            obj.resolve_date = resolve_date
        if status in ("resolved", "closed") and not obj.resolve_date:
            obj.resolve_date = datetime.now()
        self._refresh_overdue(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def get_stats(self, db: Session) -> ResearchIssueStats:
        total = db.query(func.count(self.model.id)).scalar()
        pending = db.query(func.count(self.model.id)).filter(self.model.status == "pending").scalar()
        processing = db.query(func.count(self.model.id)).filter(self.model.status == "processing").scalar()
        verify = db.query(func.count(self.model.id)).filter(self.model.status == "verify").scalar()
        resolved = db.query(func.count(self.model.id)).filter(self.model.status == "resolved").scalar()
        closed = db.query(func.count(self.model.id)).filter(self.model.status == "closed").scalar()
        suspended = db.query(func.count(self.model.id)).filter(self.model.status == "suspended").scalar()
        overdue = db.query(func.count(self.model.id)).filter(self.model.is_overdue == 1).scalar()

        closed_loop_rate = 0.0
        if total:
            closed_loop_rate = round((resolved + closed) * 100.0 / total, 1)

        def _group_by(column):
            rows = db.query(column, func.count(self.model.id)).group_by(column).all()
            return [IssueStatsItem(name=row[0] or "", value=row[1]) for row in rows]

        by_sub_type = _group_by(self.model.sub_type)
        by_city = _group_by(self.model.city)
        by_nature = _group_by(self.model.issue_nature)
        by_status = _group_by(self.model.status)

        return ResearchIssueStats(
            total=total,
            pending=pending,
            processing=processing,
            verify=verify,
            resolved=resolved,
            closed=closed,
            suspended=suspended,
            overdue=overdue,
            closed_loop_rate=closed_loop_rate,
            by_sub_type=by_sub_type,
            by_city=by_city,
            by_nature=by_nature,
            by_status=by_status,
        )


research_issue_service = ResearchIssueService()
