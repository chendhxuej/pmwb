from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import PmwbActiveOptimization


# 中国时区（UTC+8），与 models 及 dashboard 保持一致
_CST = timezone(timedelta(hours=8))

_STATUS_LABELS = {
    "pending": "待评估",
    "adopted": "已采纳",
    "rejected": "不采纳",
}


class ActiveOptimizationService:
    """主动优化建议工单 Service。"""

    def _get(self, db: Session, opt_id: int) -> Optional[PmwbActiveOptimization]:
        return db.query(PmwbActiveOptimization).filter(PmwbActiveOptimization.id == opt_id).first()

    def list_with_filters(
        self,
        db: Session,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        admin_name: Optional[str] = None,
        req_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ):
        query = db.query(PmwbActiveOptimization)
        if keyword:
            kw = f"%{keyword}%"
            query = query.filter(
                (PmwbActiveOptimization.title.ilike(kw))
                | (PmwbActiveOptimization.current_situation.ilike(kw))
                | (PmwbActiveOptimization.suggestion.ilike(kw))
                | (PmwbActiveOptimization.admin_name.ilike(kw))
                | (PmwbActiveOptimization.req_id.ilike(kw))
            )
        if status:
            query = query.filter(PmwbActiveOptimization.status == status)
        if admin_name:
            query = query.filter(PmwbActiveOptimization.admin_name.ilike(f"%{admin_name}%"))
        if req_id:
            query = query.filter(PmwbActiveOptimization.req_id == req_id)

        total = query.count()
        items = (
            query.order_by(PmwbActiveOptimization.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        pages = (total + page_size - 1) // page_size if page_size > 0 else 1
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
            "items": items,
        }

    def get(self, db: Session, opt_id: int) -> Optional[PmwbActiveOptimization]:
        return self._get(db, opt_id)

    def create(self, db: Session, obj_in: Dict[str, Any], created_by: Optional[str] = None) -> PmwbActiveOptimization:
        data = {k: v for k, v in obj_in.items() if v is not None}
        data.setdefault("status", "pending")
        data["created_by"] = created_by
        obj = PmwbActiveOptimization(**data)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def update(self, db: Session, opt_id: int, obj_in: Dict[str, Any]) -> Optional[PmwbActiveOptimization]:
        obj = self._get(db, opt_id)
        if not obj:
            return None
        for key, value in obj_in.items():
            if value is not None and hasattr(obj, key):
                setattr(obj, key, value)
        db.commit()
        db.refresh(obj)
        return obj

    def delete(self, db: Session, opt_id: int) -> bool:
        obj = self._get(db, opt_id)
        if not obj:
            return False
        db.delete(obj)
        db.commit()
        return True

    def get_summary_stats(self, db: Session) -> Dict[str, int]:
        """首页看板用：总数、各状态数、本周新增。"""
        today = datetime.now(_CST).date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=7)
        week_start_dt = datetime.combine(week_start, datetime.min.time())
        week_end_dt = datetime.combine(week_end, datetime.min.time())

        total = db.query(func.count(PmwbActiveOptimization.id)).scalar() or 0
        pending = db.query(func.count(PmwbActiveOptimization.id)).filter(
            PmwbActiveOptimization.status == "pending"
        ).scalar() or 0
        adopted = db.query(func.count(PmwbActiveOptimization.id)).filter(
            PmwbActiveOptimization.status == "adopted"
        ).scalar() or 0
        rejected = db.query(func.count(PmwbActiveOptimization.id)).filter(
            PmwbActiveOptimization.status == "rejected"
        ).scalar() or 0
        this_week = db.query(func.count(PmwbActiveOptimization.id)).filter(
            PmwbActiveOptimization.created_at >= week_start_dt,
            PmwbActiveOptimization.created_at < week_end_dt,
        ).scalar() or 0

        return {
            "total": total,
            "pending": pending,
            "adopted": adopted,
            "rejected": rejected,
            "this_week": this_week,
        }

    def build_email_variables(self, obj: PmwbActiveOptimization, scene: str = "sync") -> Dict[str, Any]:
        """为 mail_dispatch 组装邮件模板变量。"""
        return {
            "title": obj.title or "",
            "status": obj.status or "pending",
            "status_label": _STATUS_LABELS.get(obj.status or "pending", obj.status or "待评估"),
            "admin_name": obj.admin_name or "",
            "req_id": obj.req_id or "",
            "current_situation": obj.current_situation or "（无）",
            "suggestion": obj.suggestion or "（无）",
            "note": obj.note or "（无）",
            "scene_label": "催办" if scene == "urge" else "同步",
            "body": "",  # 前端编辑区正文，需要时由调用方填充
        }


active_optimization_service = ActiveOptimizationService()
