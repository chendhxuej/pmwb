from datetime import datetime
from typing import Any, List

from sqlalchemy.orm import Session, joinedload

from db.models import PmwbMeeting, PmwbMeetingAction, PmwbMeetingAttendee
from services.base import BaseService


class MeetingService(BaseService[PmwbMeeting]):
    """会议管理 Service。"""

    def __init__(self):
        super().__init__(PmwbMeeting)

    def get(self, db: Session, id: int) -> PmwbMeeting | None:
        return (
            db.query(self.model)
            .options(joinedload(self.model.attendees), joinedload(self.model.actions))
            .filter(self.model.id == id)
            .first()
        )

    def list_with_filters(
        self,
        db: Session,
        keyword: str = None,
        meeting_type: str = None,
        status: str = None,
        page: int = 1,
        page_size: int = 20,
    ):
        query = db.query(self.model)

        if meeting_type:
            query = query.filter(self.model.meeting_type == meeting_type)
        if status:
            query = query.filter(self.model.status == status)
        if keyword:
            like_pattern = f"%{keyword}%"
            query = query.filter(
                self.model.title.like(like_pattern)
                | self.model.meeting_id.like(like_pattern)
                | self.model.host.like(like_pattern)
            )

        total = query.count()
        offset = (page - 1) * page_size
        items = (
            query.options(joinedload(self.model.attendees), joinedload(self.model.actions))
            .order_by(self.model.start_time.desc())
            .offset(offset)
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

    def create_with_relations(self, db: Session, obj_in: dict) -> PmwbMeeting:
        attendees_data = obj_in.pop("attendees", [])
        actions_data = obj_in.pop("actions", [])

        meeting = self.model(**obj_in)
        db.add(meeting)
        db.flush()

        for attendee in attendees_data:
            db.add(PmwbMeetingAttendee(meeting_id=meeting.id, **attendee))

        for action in actions_data:
            db.add(PmwbMeetingAction(meeting_id=meeting.id, **action))

        db.commit()
        db.refresh(meeting)
        return meeting

    def update(self, db: Session, id: int, obj_in: dict) -> PmwbMeeting | None:
        db_obj = self.get(db, id)
        if not db_obj:
            return None

        for key, value in obj_in.items():
            if key in ("attendees", "actions"):
                continue
            if hasattr(db_obj, key):
                setattr(db_obj, key, value)

        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, id: int) -> bool:
        db_obj = self.get(db, id)
        if not db_obj:
            return False
        db.delete(db_obj)
        db.commit()
        return True


meeting_service = MeetingService()
