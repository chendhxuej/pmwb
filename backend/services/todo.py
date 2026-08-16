from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import PmwbTodo, PmwbMeeting, PmwbOperationIssue, PmwbRequirementExt
from schemas.todo import TodoStats
from services.base import BaseService


def _build_related_title_map(db: Session, items: List[PmwbTodo]) -> Dict[int, Optional[str]]:
    """批量反查每条待办的关联对象标题（meeting/operation/ticket/requirement）。

    返回: todo_id -> related_title

    字段约定：
    - related_type=meeting  → related_id 存的是 PmwbMeeting.id（不是 PmwbMeetingAction.id，
      见 services/meeting.py::sync_action_todo），按 meeting.title 反查。
    - related_type in operation/ticket → related_id 存的是 issue_no，按工单标题反查。
    - related_type=requirement → related_id 存的是 req_id，按需求名称反查。
    """
    result: Dict[int, Optional[str]] = {}

    # 按 related_type 分桶收集 related_id
    meeting_ids: List[int] = []
    operation_issue_nos: List[str] = []
    requirement_ids: List[str] = []

    todo_cache: List[PmwbTodo] = []
    for t in items:
        if not t.related_type or not t.related_id:
            result[t.id] = None
            continue
        todo_cache.append(t)
        if t.related_type == "meeting":
            try:
                meeting_ids.append(int(t.related_id))
            except (TypeError, ValueError):
                pass
        elif t.related_type in ("operation", "ticket"):
            operation_issue_nos.append(str(t.related_id))
        elif t.related_type == "requirement":
            requirement_ids.append(str(t.related_id))
        else:
            result[t.id] = None

    # 1) meeting: meeting_id -> meeting.title（todo.related_id 是 PmwbMeeting.id）
    meeting_title_map: Dict[int, Optional[str]] = {}
    if meeting_ids:
        rows = db.query(PmwbMeeting.id, PmwbMeeting.title).filter(PmwbMeeting.id.in_(meeting_ids)).all()
        for mid, mtitle in rows:
            meeting_title_map[mid] = mtitle

    # 2) operation/ticket: issue_no -> title
    issue_title_map: Dict[str, str] = {}
    if operation_issue_nos:
        rows = (
            db.query(PmwbOperationIssue.issue_no, PmwbOperationIssue.title)
            .filter(PmwbOperationIssue.issue_no.in_(operation_issue_nos))
            .all()
        )
        for no, title in rows:
            issue_title_map[no] = title

    # 3) requirement: req_id -> req_name
    req_name_map: Dict[str, str] = {}
    if requirement_ids:
        rows = (
            db.query(PmwbRequirementExt.req_id, PmwbRequirementExt.req_name)
            .filter(PmwbRequirementExt.req_id.in_(requirement_ids))
            .all()
        )
        for rid, name in rows:
            req_name_map[rid] = name

    for t in todo_cache:
        if t.related_type == "meeting":
            try:
                mid = int(t.related_id)
                result[t.id] = meeting_title_map.get(mid)
            except (TypeError, ValueError):
                result[t.id] = None
        elif t.related_type in ("operation", "ticket"):
            result[t.id] = issue_title_map.get(str(t.related_id))
        elif t.related_type == "requirement":
            result[t.id] = req_name_map.get(str(t.related_id))
        else:
            result[t.id] = None

    return result


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

        # 注入 related_title（SQLAlchemy 实例需要 service 主动 setattr 才能被 Pydantic 序列化）
        title_map = _build_related_title_map(db, items)
        for it in items:
            it.related_title = title_map.get(it.id)

        # 即时刷新 is_overdue（不写库），避免历史残留导致 UI 红条错标
        self._refresh_overdue_inplace(items)

        pages = (total + page_size - 1) // page_size if page_size > 0 else 1
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
            "items": items,
        }

    def get(self, db: Session, id: int) -> PmwbTodo | None:
        obj = super().get(db, id)
        if obj is None:
            return None
        title_map = _build_related_title_map(db, [obj])
        obj.related_title = title_map.get(obj.id)
        # 即时刷新 is_overdue（不写库），避免历史残留导致 UI 红条错标
        self._refresh_overdue_inplace([obj])
        return obj

    def get_stats(self, db: Session) -> TodoStats:
        today = datetime.now().date()
        total = db.query(func.count(self.model.id)).scalar()
        todo = db.query(func.count(self.model.id)).filter(self.model.status == "todo").scalar()
        in_progress = db.query(func.count(self.model.id)).filter(self.model.status == "in_progress").scalar()
        done = db.query(func.count(self.model.id)).filter(self.model.status == "done").scalar()
        cancelled = db.query(func.count(self.model.id)).filter(self.model.status == "cancelled").scalar()
        # overdue 实时计算：未完成态 + due_date < today（不依赖 DB 里 is_overdue 的历史值）
        overdue = (
            db.query(func.count(self.model.id))
            .filter(
                self.model.status.notin_(["done", "cancelled"]),
                self.model.due_date.isnot(None),
                self.model.due_date < today,
            )
            .scalar()
        )
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
            obj.completed_at = datetime.now()
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
        today = datetime.now().date()
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

    def _refresh_overdue_inplace(self, items: List[PmwbTodo]):
        """批量把内存里的 obj.is_overdue 校正为「今天 vs due_date」的实时结果（不写库）。

        解决 list/get 接口直接返回 DB 历史 is_overdue 导致的问题：
        - 跨天后没有 create/update 触发过的待办 is_overdue 没刷新；
        - 已完成态没把 is_overdue 清零的红条残留。
        """
        if not items:
            return
        today = datetime.now().date()
        for obj in items:
            due = obj.due_date
            if isinstance(due, str):
                try:
                    due = date.fromisoformat(due)
                except ValueError:
                    due = None
            if due and obj.status not in ("done", "cancelled") and due < today:
                obj.is_overdue = 1
            else:
                obj.is_overdue = 0


todo_service = TodoService()
