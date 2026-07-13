from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import PmwbRequirementExt, SentEmail
from schemas.common import PaginationParams, PaginationResponse


class RequirementService:
    """需求管理 Service，聚合 sent_emails 和 pmwb_requirement_ext。"""

    def _get_or_create_ext(self, db: Session, req_id: str) -> PmwbRequirementExt:
        ext = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == req_id).first()
        if not ext:
            ext = PmwbRequirementExt(req_id=req_id)
            db.add(ext)
            db.commit()
            db.refresh(ext)
        return ext

    def _merge_ext(self, item: SentEmail, ext: Optional[PmwbRequirementExt]) -> Dict[str, Any]:
        data = {
            "req_id": item.req_id,
            "req_name": item.req_name,
            "proposer": item.proposer,
            "propose_time": item.propose_time,
            "background": item.background,
            "description": item.description,
            "clarification": item.clarification,
            "system_name": item.system_name,
            "sa_name": item.sa_name,
            "send_datetime": item.send_datetime,
            "workload": float(item.workload) if item.workload is not None else None,
            "is_involved": item.is_involved,
            "dev_ticket_no": item.dev_ticket_no,
            "involve_dev": item.involve_dev,
            "ext": None,
        }
        if ext:
            data["ext"] = {
                "id": ext.id,
                "req_id": ext.req_id,
                "status": ext.status,
                "tags": ext.tags,
                "personal_note": ext.personal_note,
                "priority": ext.priority,
                "owner_note": ext.owner_note,
                "created_at": ext.created_at,
                "updated_at": ext.updated_at,
            }
        return data

    def list_with_filters(
        self,
        db: Session,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        system_name: Optional[str] = None,
        is_involved: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginationResponse[Dict[str, Any]]:
        query = db.query(SentEmail)
        if keyword:
            query = query.filter(
                (SentEmail.req_id.ilike(f"%{keyword}%"))
                | (SentEmail.req_name.ilike(f"%{keyword}%"))
                | (SentEmail.proposer.ilike(f"%{keyword}%"))
            )
        if system_name:
            query = query.filter(SentEmail.system_name == system_name)
        if is_involved is not None:
            query = query.filter(SentEmail.is_involved == is_involved)

        total = query.count()
        items = query.order_by(SentEmail.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

        ext_map = {}
        if status or priority:
            ext_query = db.query(PmwbRequirementExt)
            if status:
                ext_query = ext_query.filter(PmwbRequirementExt.status == status)
            if priority:
                ext_query = ext_query.filter(PmwbRequirementExt.priority == priority)
            ext_rows = ext_query.all()
            ext_map = {row.req_id: row for row in ext_rows}
            req_ids = {item.req_id for item in items}
            ext_map.update({row.req_id: row for row in ext_rows if row.req_id in req_ids})
        else:
            req_ids = {item.req_id for item in items}
            ext_rows = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id.in_(req_ids)).all()
            ext_map = {row.req_id: row for row in ext_rows}

        merged = [self._merge_ext(item, ext_map.get(item.req_id)) for item in items]
        return PaginationResponse.create(
            total=total,
            page=page,
            page_size=page_size,
            items=merged,
        )

    def get(self, db: Session, req_id: str) -> Optional[Dict[str, Any]]:
        item = db.query(SentEmail).filter(SentEmail.req_id == req_id).first()
        if not item:
            return None
        ext = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == req_id).first()
        return self._merge_ext(item, ext)

    def update_ext(self, db: Session, req_id: str, obj_in: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        item = db.query(SentEmail).filter(SentEmail.req_id == req_id).first()
        if not item:
            return None
        ext = self._get_or_create_ext(db, req_id)
        for key, value in obj_in.items():
            if value is not None and hasattr(ext, key):
                setattr(ext, key, value)
        db.commit()
        db.refresh(ext)
        return self._merge_ext(item, ext)

    def get_stats(self, db: Session) -> Dict[str, int]:
        total = db.query(SentEmail).count()
        involved = db.query(SentEmail).filter(SentEmail.is_involved == 1).count()
        counts = (
            db.query(PmwbRequirementExt.status, func.count(PmwbRequirementExt.id))
            .group_by(PmwbRequirementExt.status)
            .all()
        )
        status_map = {row[0]: row[1] for row in counts}
        return {
            "total": total,
            "proposed": status_map.get("proposed", 0),
            "accepted": status_map.get("accepted", 0),
            "dev": status_map.get("dev", 0),
            "closed": status_map.get("closed", 0),
            "paused": status_map.get("paused", 0),
            "involved": involved,
        }

    def get_systems(self, db: Session) -> List[str]:
        rows = db.query(SentEmail.system_name).distinct().filter(SentEmail.system_name.isnot(None)).all()
        return [row[0] for row in rows if row[0]]


requirement_service = RequirementService()
