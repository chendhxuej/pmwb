from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import PmwbOperationAnalysis, PmwbOperationIssue, PmwbKnowledgeLink
from schemas.operation import OperationIssueStats, IssueStatsItem
from services.base import BaseService


class OperationIssueService(BaseService[PmwbOperationIssue]):
    """业务运营问题 Service。"""

    def __init__(self):
        super().__init__(PmwbOperationIssue)

    def delete(self, db: Session, id: int) -> dict:
        """删除工单：级联清理关联数据，避免外键约束（1451）报错与孤儿数据。

        级联范围：
        - 分析明细（PmwbOperationAnalysis，1:1，按 issue_id）
        - 主动运营分析主工单（category=prod）下的遗留任务工单（不限类别，按 related_req_id==issue_no）
        - 知识关联（pmwb_knowledge_link，source_type=operation）
        返回删除明细，便于前端提示。
        """
        obj = self.get(db, id)
        if not obj:
            return {"deleted": False, "reason": "not_found"}

        # 主动运营分析主工单：级联删除其遗留任务工单（不限类别，按 related_req_id 关联）
        legacy_tasks_deleted = 0
        if obj.category == "prod":
            legacy_tasks_deleted = (
                db.query(PmwbOperationIssue)
                .filter(PmwbOperationIssue.related_req_id == obj.issue_no)
                .delete(synchronize_session=False)
            )

        # 分析明细（1:1，先删明细再删主工单，规避外键约束）
        analysis_deleted = (
            db.query(PmwbOperationAnalysis)
            .filter(PmwbOperationAnalysis.issue_id == id)
            .delete(synchronize_session=False)
        )

        # 知识关联
        links_deleted = (
            db.query(PmwbKnowledgeLink)
            .filter(
                PmwbKnowledgeLink.source_type == "operation",
                PmwbKnowledgeLink.source_id == str(id),
            )
            .delete(synchronize_session=False)
        )

        super().delete(db, id)
        return {
            "deleted": True,
            "category": obj.category,
            "issue_no": obj.issue_no,
            "analysis_deleted": analysis_deleted or 0,
            "legacy_tasks_deleted": legacy_tasks_deleted or 0,
            "links_deleted": links_deleted or 0,
        }

    def batch_delete(self, db: Session, ids: List[int]) -> dict:
        """批量删除工单，逐个走 delete 级联逻辑。"""
        deleted_count = 0
        legacy_tasks_deleted = 0
        for i in ids or []:
            r = self.delete(db, i)
            if r.get("deleted"):
                deleted_count += 1
                legacy_tasks_deleted += r.get("legacy_tasks_deleted", 0)
        return {
            "deleted_count": deleted_count,
            "legacy_tasks_deleted": legacy_tasks_deleted,
            "requested": len(ids or []),
        }

    def list_with_filters(
        self,
        db: Session,
        keyword: str = None,
        category: str = None,
        issue_type: str = None,
        status: str = None,
        impact_level: str = None,
        handler: str = None,
        related_system: str = None,
        page: int = 1,
        page_size: int = 20,
    ):
        query = db.query(self.model)

        if category:
            query = query.filter(self.model.category == category)
        if issue_type:
            query = query.filter(self.model.issue_type == issue_type)
        if status:
            query = query.filter(self.model.status == status)
        if impact_level:
            query = query.filter(self.model.impact_level == impact_level)
        if handler:
            query = query.filter(self.model.handler.like(f"%{handler}%"))
        if related_system:
            query = query.filter(self.model.related_system == related_system)
        if keyword:
            like_pattern = f"%{keyword}%"
            query = query.filter(
                self.model.title.like(like_pattern)
                | self.model.issue_no.like(like_pattern)
                | self.model.handler.like(like_pattern)
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

    def get_stats(self, db: Session, category: str = None) -> OperationIssueStats:
        query = db.query(self.model)
        if category:
            query = query.filter(self.model.category == category)

        base_count = query.with_entities(func.count(self.model.id))
        total = base_count.scalar()
        pending = query.filter(self.model.status == "pending").with_entities(func.count(self.model.id)).scalar()
        processing = query.filter(self.model.status == "processing").with_entities(func.count(self.model.id)).scalar()
        verify = query.filter(self.model.status == "verify").with_entities(func.count(self.model.id)).scalar()
        resolved = query.filter(self.model.status == "resolved").with_entities(func.count(self.model.id)).scalar()
        closed = query.filter(self.model.status == "closed").with_entities(func.count(self.model.id)).scalar()
        suspended = query.filter(self.model.status == "suspended").with_entities(func.count(self.model.id)).scalar()
        overdue = query.filter(self.model.is_overdue == 1).with_entities(func.count(self.model.id)).scalar()

        closed_loop_rate = 0.0
        if total:
            closed_loop_rate = round((resolved + closed) * 100.0 / total, 1)

        type_query = db.query(self.model.issue_type, func.count(self.model.id))
        if category:
            type_query = type_query.filter(self.model.category == category)
        type_rows = type_query.group_by(self.model.issue_type).all()
        by_type = [IssueStatsItem(name=row[0], value=row[1]) for row in type_rows]

        by_category = []
        if not category:
            cat_rows = (
                db.query(self.model.category, func.count(self.model.id))
                .group_by(self.model.category)
                .all()
            )
            by_category = [IssueStatsItem(name=row[0], value=row[1]) for row in cat_rows]

        return OperationIssueStats(
            total=total,
            pending=pending,
            processing=processing,
            verify=verify,
            resolved=resolved,
            closed=closed,
            suspended=suspended,
            overdue=overdue,
            closed_loop_rate=closed_loop_rate,
            by_type=by_type,
            by_category=by_category,
        )

    def update_status(self, db: Session, id: int, status: str, resolve_date: datetime = None):
        obj = self.get(db, id)
        if not obj:
            return None
        obj.status = status
        if resolve_date:
            obj.resolve_date = resolve_date
        if status in ("resolved", "closed") and not obj.resolve_date:
            obj.resolve_date = datetime.now()
        db.commit()
        db.refresh(obj)
        return obj


operation_issue_service = OperationIssueService()
