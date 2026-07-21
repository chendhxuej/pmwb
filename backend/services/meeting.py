from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy.orm import Session, joinedload

from core.exceptions import NotFoundException, ValidationException
from db.models import (
    EmailRecord,
    PmwbMeeting,
    PmwbMeetingAction,
    PmwbMeetingAgenda,
    PmwbMeetingAttendee,
)
from services.base import BaseService
from services.todo import todo_service
from utils.email import EmailCenterClient
from utils.validators import validate_email_strict


class MeetingService(BaseService[PmwbMeeting]):
    """会议管理 Service。"""

    def __init__(self):
        super().__init__(PmwbMeeting)

    def get(self, db: Session, id: int) -> PmwbMeeting | None:
        return (
            db.query(self.model)
            .options(
                joinedload(self.model.attendees),
                joinedload(self.model.agendas),
                joinedload(self.model.actions),
            )
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
            .order_by(self.model.created_at.desc())
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
        agendas_data = obj_in.pop("agendas", [])

        meeting = self.model(**obj_in)
        db.add(meeting)
        db.flush()

        for attendee in attendees_data:
            db.add(PmwbMeetingAttendee(meeting_id=meeting.id, **attendee))

        for agenda in agendas_data:
            db.add(PmwbMeetingAgenda(meeting_id=meeting.id, **agenda))

        for action in actions_data:
            action = dict(action)
            action.pop("id", None)  # 新建忽略 id
            db.add(PmwbMeetingAction(meeting_id=meeting.id, **action))

        db.commit()
        db.refresh(meeting)
        return meeting

    def _replace_children(self, db: Session, meeting_id: int, children: List[dict], model, fk: str = "meeting_id"):
        """删除某会议下的全部子表记录并重新插入（用于 attendees / agendas 全量替换）。"""
        db.query(model).filter(getattr(model, fk) == meeting_id).delete()
        for child in children:
            child = dict(child)
            child.pop("id", None)
            db.add(model(**{fk: meeting_id, **child}))

    def _upsert_actions(self, db: Session, meeting_id: int, actions: List[dict]):
        """行动项 upsert：携带 id 则更新可编辑字段（保留 related_todo_id），否则新建。"""
        editable = ("content", "owner", "due_date", "status", "category", "template")
        for action in actions:
            action = dict(action)
            aid = action.get("id")
            if aid:
                existing = (
                    db.query(PmwbMeetingAction)
                    .filter(PmwbMeetingAction.id == aid, PmwbMeetingAction.meeting_id == meeting_id)
                    .first()
                )
                if existing:
                    for key in editable:
                        if key in action:
                            setattr(existing, key, action[key])
                    db.commit()
                    continue
            action.pop("id", None)
            db.add(PmwbMeetingAction(meeting_id=meeting_id, **action))

    def update(self, db: Session, id: int, obj_in: dict) -> PmwbMeeting | None:
        db_obj = self.get(db, id)
        if not db_obj:
            return None

        # 标量字段
        for key, value in obj_in.items():
            if key in ("attendees", "agendas", "actions"):
                continue
            if hasattr(db_obj, key):
                setattr(db_obj, key, value)

        # 参会人：若提供则全量替换
        if obj_in.get("attendees") is not None:
            self._replace_children(db, id, obj_in["attendees"], PmwbMeetingAttendee)
        # 议题：若提供则全量替换
        if obj_in.get("agendas") is not None:
            self._replace_children(db, id, obj_in["agendas"], PmwbMeetingAgenda)
        # 行动项：若提供则 upsert
        if obj_in.get("actions") is not None:
            self._upsert_actions(db, id, obj_in["actions"])

        db.commit()
        db.refresh(db_obj)
        return db_obj

    def sync_action_todo(self, db: Session, meeting_id: int, action_id: int) -> dict:
        """把会议行动项同步为 PMWB 待办任务（source=meeting），返回 {todo_id, created, todo}。"""
        meeting = self.get(db, meeting_id)
        if not meeting:
            raise NotFoundException(f"会议不存在：id={meeting_id}")
        action = (
            db.query(PmwbMeetingAction)
            .filter(PmwbMeetingAction.id == action_id, PmwbMeetingAction.meeting_id == meeting_id)
            .first()
        )
        if not action:
            raise NotFoundException(f"会议行动项不存在：action_id={action_id}")

        # 已关联则直接返回，避免重复建待办
        if action.related_todo_id:
            todo = todo_service.get(db, action.related_todo_id)
            if todo:
                return {"todo_id": todo.id, "created": False, "todo": todo}

        due = action.due_date
        todo = todo_service.create(
            db,
            {
                "title": (action.content or "(会议待办)")[:255],
                "content": (
                    f"来源会议：{meeting.title}（{meeting.meeting_id}）\n"
                    f"负责人：{action.owner or '—'}\n"
                    f"分类：{action.category or 'meeting'}\n"
                    f"模板：{action.template or '—'}"
                ),
                "category": action.category or "meeting",
                "priority": "P2",
                "status": "todo",
                "due_date": due,
                "related_type": "meeting",
                "related_id": str(meeting.id),
                "source": "meeting",
            },
        )
        action.related_todo_id = todo.id
        db.commit()
        return {"todo_id": todo.id, "created": True, "todo": todo}

    def send_mail(
        self,
        db: Session,
        meeting_id: int,
        to: List[str],
        cc: Optional[List[str]],
        subject: str,
        body: str,
        mail_type: str = "meeting_notice",
        recipient_names: Optional[List[str]] = None,
    ) -> dict:
        """一键发送会议邮件（通知/纪要），写入 email_records 并走统一邮件中心发信。

        - 邮箱严格校验：非 ASCII 本地名（如中文名@domain）直接 400 拒绝，避免邮件中心 500。
        - 记录 source='pmwb_meeting'，req_id 复用 meeting_id 编号以便后续按会议追溯。
        """
        meeting = self.get(db, meeting_id)
        if not meeting:
            raise NotFoundException(f"会议不存在：id={meeting_id}")

        to = to or []
        cc = cc or []
        bad = [e for e in to if not validate_email_strict(e)] + [
            e for e in cc if not validate_email_strict(e)
        ]
        if bad:
            raise ValidationException(
                "收件人邮箱格式不正确：" + "、".join(bad)
                + "。请在通讯录按姓名解析或手动填写真实邮箱。"
            )
        if not to:
            raise ValidationException("请至少填写一位收件人")

        record = EmailRecord(
            req_id=meeting.meeting_id,
            req_name=meeting.title,
            email_type=mail_type or "meeting_notice",
            recipient=",".join(to),
            recipient_name=",".join(recipient_names or []),
            subject=subject,
            content=body,
            send_status="pending",
            source="pmwb_meeting",
            sender="pmwb",
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        try:
            EmailCenterClient().send_email(
                to=to,
                cc=cc or None,
                subject=subject,
                body=body,
                body_format="text",
            )
            record.send_status = "success"
            message = "邮件发送成功"
            ok = True
        except Exception as exc:  # noqa: BLE001
            record.send_status = "failed"
            record.error_msg = str(exc)
            message = f"邮件发送失败：{exc}"
            ok = False

        db.commit()
        db.refresh(record)
        return {"success": ok, "record_id": record.id, "message": message}

    def delete(self, db: Session, id: int) -> bool:
        db_obj = self.get(db, id)
        if not db_obj:
            return False
        db.delete(db_obj)
        db.commit()
        return True


meeting_service = MeetingService()
