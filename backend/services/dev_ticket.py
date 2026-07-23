from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import PmwbDevDeliverable, PmwbDevTicket, PmwbDevTicketLog


class DevTicketService:
    """开发工单 Service。"""

    STATUS_PROGRESS = {
        "created": 0,
        "design_reviewed": 20,
        "dev_completed": 50,
        "test_completed": 80,
        "live": 100,
        "archived": 100,
    }

    STATUS_DATE_FIELDS = {
        "design_reviewed": "design_reviewed_date",
        "dev_completed": "dev_completed_date",
        "test_completed": "test_completed_date",
        "live": "go_live_date",
        "archived": "archived_date",
    }

    def _get(self, db: Session, ticket_id: int) -> Optional[PmwbDevTicket]:
        return db.query(PmwbDevTicket).filter(PmwbDevTicket.id == ticket_id).first()

    def _add_log(self, db: Session, ticket_id: int, from_status: str, to_status: str, operator: str, note: str):
        log = PmwbDevTicketLog(
            ticket_id=ticket_id,
            from_status=from_status,
            to_status=to_status,
            operator=operator,
            note=note,
        )
        db.add(log)

    def list_with_filters(
        self,
        db: Session,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        system_name: Optional[str] = None,
        req_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ):
        query = db.query(PmwbDevTicket)
        if keyword:
            query = query.filter(
                (PmwbDevTicket.ticket_no.ilike(f"%{keyword}%"))
                | (PmwbDevTicket.system_name.ilike(f"%{keyword}%"))
                | (PmwbDevTicket.developer.ilike(f"%{keyword}%"))
            )
        if status:
            query = query.filter(PmwbDevTicket.status == status)
        if priority:
            query = query.filter(PmwbDevTicket.priority == priority)
        if system_name:
            query = query.filter(PmwbDevTicket.system_name == system_name)
        if req_id:
            query = query.filter(PmwbDevTicket.req_id == req_id)

        total = query.count()
        items = query.order_by(PmwbDevTicket.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        pages = (total + page_size - 1) // page_size if page_size > 0 else 1
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
            "items": items,
        }

    def get(self, db: Session, ticket_id: int) -> Optional[PmwbDevTicket]:
        return self._get(db, ticket_id)

    def create(self, db: Session, obj_in: Dict[str, Any]) -> PmwbDevTicket:
        obj = PmwbDevTicket(**obj_in)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def update(self, db: Session, ticket_id: int, obj_in: Dict[str, Any]) -> Optional[PmwbDevTicket]:
        obj = self._get(db, ticket_id)
        if not obj:
            return None
        for key, value in obj_in.items():
            if value is not None and hasattr(obj, key):
                setattr(obj, key, value)
        db.commit()
        db.refresh(obj)
        return obj

    def update_status(
        self,
        db: Session,
        ticket_id: int,
        status: str,
        operator: str = "",
        note: str = "",
    ) -> Optional[PmwbDevTicket]:
        obj = self._get(db, ticket_id)
        if not obj:
            return None
        from_status = obj.status
        if from_status == status:
            return obj
        obj.status = status
        obj.progress = self.STATUS_PROGRESS.get(status, obj.progress)
        date_field = self.STATUS_DATE_FIELDS.get(status)
        if date_field:
            setattr(obj, date_field, datetime.utcnow().date())
        self._add_log(db, ticket_id, from_status, status, operator, note)
        db.commit()
        db.refresh(obj)
        return obj

    def delete(self, db: Session, ticket_id: int) -> bool:
        obj = self._get(db, ticket_id)
        if not obj:
            return False
        # 先删除关联日志和交付物，避免外键约束 1451
        db.query(PmwbDevTicketLog).filter(PmwbDevTicketLog.ticket_id == ticket_id).delete(synchronize_session=False)
        db.query(PmwbDevDeliverable).filter(PmwbDevDeliverable.ticket_id == ticket_id).delete(synchronize_session=False)
        db.delete(obj)
        db.commit()
        return True

    def get_stats(self, db: Session) -> Dict[str, int]:
        total = db.query(PmwbDevTicket).count()
        overdue = db.query(PmwbDevTicket).filter(PmwbDevTicket.is_overdue == 1).count()
        counts = (
            db.query(PmwbDevTicket.status, func.count(PmwbDevTicket.id))
            .group_by(PmwbDevTicket.status)
            .all()
        )
        status_map = {row[0]: row[1] for row in counts}
        return {
            "total": total,
            "created": status_map.get("created", 0),
            "design_reviewed": status_map.get("design_reviewed", 0),
            "dev_completed": status_map.get("dev_completed", 0),
            "test_completed": status_map.get("test_completed", 0),
            "live": status_map.get("live", 0),
            "archived": status_map.get("archived", 0),
            "overdue": overdue,
        }

    def get_logs(self, db: Session, ticket_id: int) -> List[PmwbDevTicketLog]:
        return (
            db.query(PmwbDevTicketLog)
            .filter(PmwbDevTicketLog.ticket_id == ticket_id)
            .order_by(PmwbDevTicketLog.created_at.desc())
            .all()
        )

    def get_deliverables(self, db: Session, ticket_id: int) -> List[PmwbDevDeliverable]:
        return db.query(PmwbDevDeliverable).filter(PmwbDevDeliverable.ticket_id == ticket_id).all()

    def create_deliverable(self, db: Session, ticket_id: int, obj_in: Dict[str, Any]) -> PmwbDevDeliverable:
        obj = PmwbDevDeliverable(ticket_id=ticket_id, **obj_in)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def get_systems(self, db: Session) -> List[str]:
        rows = db.query(PmwbDevTicket.system_name).distinct().filter(PmwbDevTicket.system_name.isnot(None)).all()
        return [row[0] for row in rows if row[0]]


dev_ticket_service = DevTicketService()
