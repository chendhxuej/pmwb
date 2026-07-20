from datetime import date, datetime
from typing import Any, Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import PmwbTodo
from schemas.todo import TodoStats
from services.base import BaseService


class TodoService(BaseService[PmwbTodo]):
    """待办中心 Service。"""

    def __init__(self):
        super().__init__(PmwbTodo)

    def list_with_filters(
        self,
        db: Session,
        keyword: str = None,
        category: str = None,
        status: str = None,
        priority: str = None,
        is_overdue: bool = None,
        page: int = 1,
        page_size: int = 20,
    ):
        query = db.query(self.model)

        if category:
            query = query.filter(self.model.category == category)
        if status:
            query = query.filter(self.model.status == status)
        if priority:
            query = query.filter(self.model.priority == priority)
        if is_overdue is not None:
            if is_overdue:
                query = query.filter(self.model.is_overdue == 1)
            else:
                query = query.filter(self.model.is_overdue == 0)
        if keyword:
            like_pattern = f"%{keyword}%"
            query = query.filter(
                self.model.title.like(like_pattern)
                | self.model.content.like(like_pattern)
            )

        total = query.count()
        offset = (page - 1) * page_size
        items = (
            query.order_by(self.model.created_at.desc())
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

    def get_stats(self, db: Session) -> TodoStats:
        today = datetime.utcnow().date()
        total = db.query(func.count(self.model.id)).scalar()
        todo = db.query(func.count(self.model.id)).filter(self.model.status == "todo").scalar()
        in_progress = db.query(func.count(self.model.id)).filter(self.model.status == "in_progress").scalar()
        done = db.query(func.count(self.model.id)).filter(self.model.status == "done").scalar()
        cancelled = db.query(func.count(self.model.id)).filter(self.model.status == "cancelled").scalar()
        overdue = db.query(func.count(self.model.id)).filter(self.model.is_overdue == 1).scalar()
        today_count = db.query(func.count(self.model.id)).filter(self.model.due_date == today).scalar()
        return TodoStats(
            total=total,
            todo=todo,
            in_progress=in_progress,
            done=done,
            cancelled=cancelled,
            overdue=overdue,
            today=today_count,
        )

    def update_status(self, db: Session, id: int, status: str) -> PmwbTodo | None:
        obj = self.get(db, id)
        if not obj:
            return None
        obj.status = status
        if status == "done":
            obj.completed_at = datetime.utcnow()
        else:
            obj.completed_at = None
        self._check_overdue(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def create(self, db: Session, obj_in: Dict[str, Any]) -> PmwbTodo:
        db_obj = self.model(**obj_in)
        self._check_overdue(db_obj)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, id: int, obj_in: Dict[str, Any]) -> PmwbTodo | None:
        db_obj = self.get(db, id)
        if not db_obj:
            return None
        for key, value in obj_in.items():
            if hasattr(db_obj, key):
                setattr(db_obj, key, value)
        self._check_overdue(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def _check_overdue(self, obj: PmwbTodo):
        today = datetime.utcnow().date()
        due_date = obj.due_date
        if isinstance(due_date, str):
            try:
                due_date = date.fromisoformat(due_date)
            except ValueError:
                due_date = None
        if due_date and obj.status not in ("done", "cancelled"):
            obj.is_overdue = 1 if due_date < today else 0
        else:
            obj.is_overdue = 0


todo_service = TodoService()
