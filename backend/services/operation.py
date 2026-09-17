from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from db.models import PmwbOperationAnalysis, PmwbOperationIssue, PmwbKnowledgeLink, now_cn
from schemas.operation import OperationIssueStats, IssueStatsItem
from services.base import BaseService
from utils.owners import split_owners


class OperationIssueService(BaseService[PmwbOperationIssue]):
    """业务运营问题 Service。"""

    # 状态全集（顺序即前端展示顺序；pending 虽当前无数据也保留列，保证各责任人区块结构一致）
    STATUS_ORDER = ("pending", "processing", "verify", "resolved", "closed", "suspended")
    # 责任人字段为空时的兜底桶名
    UNASSIGNED_LABEL = "未指派"

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
        handler_exact: bool = False,
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
            if handler_exact:
                # 精确命中某人：按逗号边界匹配，避免「王伟」误命中「王伟民」。
                # handler 为多负责人逗号串，四个条件覆盖 单值/首/尾/中间 四种位置。
                conds = []
                for name in split_owners(handler):
                    conds.append(self.model.handler == name)
                    conds.append(self.model.handler.like(f"{name},%"))
                    conds.append(self.model.handler.like(f"%,{name}"))
                    conds.append(self.model.handler.like(f"%,{name},%"))
                if conds:
                    query = query.filter(or_(*conds))
            else:
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

    def _empty_status_bucket(self) -> Dict[str, int]:
        bucket = {s: 0 for s in self.STATUS_ORDER}
        bucket["total"] = 0
        bucket["overdue"] = 0
        return bucket

    @staticmethod
    def _rate(closed: int, total: int) -> float:
        return round(closed * 100.0 / total, 1) if total else 0.0

    def get_stats_by_handler(self, db: Session) -> dict:
        """责任人维度统计：责任人 × 工单类别 × 状态 的数量矩阵（总览页责任人分布用）。

        口径说明：
        - 全局块（summary / category_matrix）按 category + status 聚合，不做责任人拆分，
          因此多负责人工单不会被重复计数，与 /operation/stats 的口径一致；
        - 责任人块按 split_owners 拆分 handler 逗号串，一条工单挂多人时人人计数；
        - 责任人字段为空的历史脏数据归入「未指派」桶，保证总览与全量工单数对得上。
        """
        # 1) 全局：类别 × 状态（含超期数）
        global_rows = (
            db.query(
                self.model.category,
                self.model.status,
                func.count(self.model.id),
                func.coalesce(func.sum(self.model.is_overdue), 0),
            )
            .group_by(self.model.category, self.model.status)
            .all()
        )

        category_matrix: Dict[str, Dict[str, int]] = {}
        status_totals = {s: 0 for s in self.STATUS_ORDER}
        overdue_total = 0
        grand_total = 0
        for category, status, cnt, overdue in global_rows:
            cnt = int(cnt or 0)
            overdue = int(overdue or 0)
            bucket = category_matrix.setdefault(category, self._empty_status_bucket())
            bucket["total"] += cnt
            bucket["overdue"] += overdue
            grand_total += cnt
            overdue_total += overdue
            if status in self.STATUS_ORDER:
                bucket[status] += cnt
                status_totals[status] += cnt

        for bucket in category_matrix.values():
            bucket["closed_loop_rate"] = self._rate(
                bucket["resolved"] + bucket["closed"], bucket["total"]
            )

        summary = {
            **status_totals,
            "total": grand_total,
            "overdue": overdue_total,
            "closed_loop_rate": self._rate(
                status_totals["resolved"] + status_totals["closed"], grand_total
            ),
        }

        # 2) 责任人：handler × 类别 × 状态
        handler_rows = (
            db.query(
                self.model.handler,
                self.model.category,
                self.model.status,
                func.count(self.model.id),
                func.coalesce(func.sum(self.model.is_overdue), 0),
            )
            .group_by(self.model.handler, self.model.category, self.model.status)
            .all()
        )

        buckets: Dict[str, dict] = {}
        for handler, category, status, cnt, overdue in handler_rows:
            cnt = int(cnt or 0)
            overdue = int(overdue or 0)
            names = split_owners(handler)
            is_unassigned = not names
            for name in (names or [self.UNASSIGNED_LABEL]):
                b = buckets.get(name)
                if b is None:
                    b = {
                        "name": name,
                        "unassigned": is_unassigned,
                        "total": 0,
                        "overdue": 0,
                        "matrix": {},
                        "cat_totals": {},
                        "status_totals": {s: 0 for s in self.STATUS_ORDER},
                    }
                    buckets[name] = b
                b["total"] += cnt
                b["overdue"] += overdue
                row = b["matrix"].setdefault(
                    category, {s: 0 for s in self.STATUS_ORDER}
                )
                if status in self.STATUS_ORDER:
                    row[status] += cnt
                    b["status_totals"][status] += cnt

        handlers = []
        for b in buckets.values():
            b["cat_totals"] = {c: sum(row.values()) for c, row in b["matrix"].items()}
            b["closed_total"] = b["status_totals"]["resolved"] + b["status_totals"]["closed"]
            # 未闭环 = 仍在流转的状态（不含待处理以外的人工挂起）
            b["active"] = (
                b["status_totals"]["pending"]
                + b["status_totals"]["processing"]
                + b["status_totals"]["verify"]
            )
            b["closed_loop_rate"] = self._rate(b["closed_total"], b["total"])
            handlers.append(b)

        # 工单量降序；「未指派」沉底
        handlers.sort(key=lambda x: (bool(x["unassigned"]), -x["total"], x["name"]))

        return {
            "generated_at": now_cn().isoformat(),
            "statuses": list(self.STATUS_ORDER),
            "summary": summary,
            "category_matrix": category_matrix,
            "handler_count": sum(1 for h in handlers if not h["unassigned"]),
            "unassigned_total": sum(h["total"] for h in handlers if h["unassigned"]),
            "handlers": handlers,
        }

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
