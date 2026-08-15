import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload

from core.config import settings
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
from utils.master_service import MasterServiceClient
from utils.validators import validate_email_strict
from services.mail_dispatch import dispatch_email

logger = logging.getLogger(__name__)


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

    def sync_action_todo(self, db: Session, meeting_id: int, action_id: int, *, dispatch: bool = True) -> dict:
        """会议行动项归属分流（统一邮件治理层）：

        - owner == 本人(SELF_NAME) → 建个人待办（PmwbTodo）并回填 related_todo_id；
        - owner 为团队成员 → 不进个人待办，作为「团队任务」保留在行动项，发送 HTML 派发邮件给负责人；
        - owner 为空 → 拒绝，需先指定负责人。
        返回 {todo_id, created, personal, dispatched, owner, message}。
        """
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
        if not (action.owner or "").strip():
            raise ValidationException("请先指定行动项负责人，再创建/派发任务")

        # 已是本人的个人待办则直接返回
        if action.related_todo_id:
            todo = todo_service.get(db, action.related_todo_id)
            if todo:
                return {"todo_id": todo.id, "created": False, "personal": True, "dispatched": False, "todo": todo}

        owner = (action.owner or "").strip()
        if owner == settings.SELF_NAME:
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
            return {"todo_id": todo.id, "created": True, "personal": True, "dispatched": False, "todo": todo}

        # 团队成员 → 团队任务：不建个人待办，发送派发邮件
        dispatched = False
        note = ""
        if dispatch:
            md = self._build_dispatch_mail(action, meeting)
            emails, _ = self._resolve_recipients([owner])
            if emails:
                res = dispatch_email(
                    db=db,
                    to=emails,
                    subject=f"【任务派发】{meeting.title}",
                    body=md,
                    scene="action_dispatch",
                    body_format="html",
                    req_id=meeting.meeting_id,
                    req_name=meeting.title,
                    source="pmwb_meeting",
                )
                dispatched = res["success"]
                note = res["message"]
            else:
                note = f"负责人 {owner} 未在人员中台解析到邮箱，未发送派发邮件"
        return {
            "todo_id": None,
            "created": False,
            "personal": False,
            "dispatched": dispatched,
            "owner": owner,
            "message": note or "已记录为团队任务（不进入你的个人待办）",
        }

    def _build_dispatch_mail(self, action, meeting) -> str:
        due = action.due_date or "待定"
        return (
            f"### 任务派发通知\n\n"
            f"**{action.content or '(未填写内容)'}**\n\n"
            f"- **所属会议**：{meeting.title}\n"
            f"- **负责人**：{action.owner or '—'}\n"
            f"- **截止日期**：{due}\n"
            f"- **分类**：{action.category or 'meeting'}\n\n"
            f"请按上述要求在期限内推进，并在 PMWB「会议行动项跟踪台」及时更新状态。"
        )

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
        # 兼容「姓名 / 邮箱」两种输入：姓名经人员中台解析为邮箱
        resolved_to, unresolved_to = self._resolve_recipients(to)
        resolved_cc, unresolved_cc = self._resolve_recipients(cc)
        bad = unresolved_to + unresolved_cc
        if bad:
            raise ValidationException(
                "收件人邮箱格式不正确或通讯录中无匹配：" + "、".join(bad)
                + "。请在通讯录按姓名解析或手动填写真实邮箱。"
            )
        if not resolved_to:
            raise ValidationException("请至少填写一位收件人")

        # 走统一邮件治理门面：HTML 转换 + 统一签名 + 落库 + 统一降级
        scene = mail_type or "meeting_notice"
        result = dispatch_email(
            db=db,
            to=resolved_to,
            cc=resolved_cc,
            subject=subject,
            body=body,
            scene=scene,
            body_format="html",
            req_id=meeting.meeting_id,
            req_name=meeting.title,
            source="pmwb_meeting",
        )
        return {
            "success": result["success"],
            "record_id": result["record_id"],
            "message": result["message"],
        }

    def _resolve_recipients(self, entries: List[str]) -> Tuple[List[str], List[str]]:
        """将收件人条目（姓名或邮箱）解析为邮箱列表。

        返回 (resolved_emails, unresolved_entries)：
        - 已是合法邮箱者原样保留；
        - 非邮箱文本按姓名经人员中台解析，成功取邮箱，失败计入 unresolved；
        - 空项跳过；解析出的邮箱按出现顺序去重。
        """
        clean = [str(e).strip() for e in (entries or []) if e and str(e).strip()]
        emails: List[str] = []
        unresolved: List[str] = []
        name_entries = [e for e in clean if not validate_email_strict(e)]
        name_map: Dict[str, Optional[str]] = {}
        if name_entries:
            try:
                name_map = MasterServiceClient().resolve_staff_emails(name_entries)
            except Exception as exc:  # noqa: BLE001
                logger.warning("人员中台解析收件人邮箱失败: %s", exc)
                name_map = {}
        seen: set = set()
        for e in clean:
            if validate_email_strict(e):
                target = e
            else:
                target = name_map.get(e)
            if not target:
                if not validate_email_strict(e):
                    unresolved.append(e)
                continue
            if target not in seen:
                seen.add(target)
                emails.append(target)
        return emails, unresolved

    def list_actions(
        self,
        db: Session,
        *,
        meeting_id: Optional[int] = None,
        owner: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        due_start: Optional[date] = None,
        due_end: Optional[date] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """查询会议行动项列表，返回带会议简要信息的分页结果。"""
        query = db.query(PmwbMeetingAction).join(
            PmwbMeeting, PmwbMeetingAction.meeting_id == PmwbMeeting.id
        )

        if meeting_id is not None:
            query = query.filter(PmwbMeetingAction.meeting_id == meeting_id)
        if owner:
            query = query.filter(PmwbMeetingAction.owner.like(f"%{owner}%"))
        if status:
            query = query.filter(PmwbMeetingAction.status == status)
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(
                PmwbMeetingAction.content.like(like)
                | PmwbMeeting.title.like(like)
                | PmwbMeeting.meeting_id.like(like)
            )
        if due_start is not None:
            query = query.filter(PmwbMeetingAction.due_date >= due_start)
        if due_end is not None:
            query = query.filter(PmwbMeetingAction.due_date <= due_end)

        total = query.count()
        pages = (total + page_size - 1) // page_size if page_size > 0 else 1
        offset = (page - 1) * page_size
        actions = (
            query.options(joinedload(PmwbMeetingAction.meeting))
            .order_by(PmwbMeetingAction.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        items = []
        for a in actions:
            items.append(
                {
                    "id": a.id,
                    "meeting_id": a.meeting_id,
                    "meeting_title": a.meeting.title if a.meeting else "",
                    "meeting_id_no": a.meeting.meeting_id if a.meeting else "",
                    "content": a.content,
                    "owner": a.owner,
                    "due_date": a.due_date.isoformat() if a.due_date else None,
                    "status": a.status,
                    "category": a.category,
                    "template": a.template,
                    "related_todo_id": a.related_todo_id,
                    "created_at": a.created_at,
                    "updated_at": a.updated_at,
                }
            )

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
            "items": items,
        }

    def update_action(
        self,
        db: Session,
        meeting_id: int,
        action_id: int,
        obj_in: dict,
    ) -> PmwbMeetingAction:
        """更新会议行动项（完整编辑）。"""
        from datetime import date as _date

        action = (
            db.query(PmwbMeetingAction)
            .filter(PmwbMeetingAction.id == action_id, PmwbMeetingAction.meeting_id == meeting_id)
            .first()
        )
        if not action:
            raise NotFoundException(f"会议行动项不存在：meeting_id={meeting_id}, action_id={action_id}")

        if "content" in obj_in and obj_in["content"] is not None:
            action.content = obj_in["content"]
        if "owner" in obj_in:
            action.owner = obj_in["owner"]
        if "due_date" in obj_in:
            due_date = obj_in["due_date"]
            if due_date is None or due_date == "":
                action.due_date = None
            elif isinstance(due_date, str):
                action.due_date = _date.fromisoformat(due_date)
            else:
                action.due_date = due_date
        if "status" in obj_in and obj_in["status"] is not None:
            action.status = obj_in["status"].value if hasattr(obj_in["status"], "value") else obj_in["status"]
        if "category" in obj_in:
            action.category = obj_in["category"]
        if "template" in obj_in:
            action.template = obj_in["template"]

        db.commit()
        db.refresh(action)
        return action

    def update_action_status(
        self,
        db: Session,
        meeting_id: int,
        action_id: int,
        status: str,
    ) -> PmwbMeetingAction:
        """更新会议行动项状态。"""
        action = (
            db.query(PmwbMeetingAction)
            .filter(PmwbMeetingAction.id == action_id, PmwbMeetingAction.meeting_id == meeting_id)
            .first()
        )
        if not action:
            raise NotFoundException(f"会议行动项不存在：meeting_id={meeting_id}, action_id={action_id}")
        action.status = status
        db.commit()
        db.refresh(action)
        return action

    def supervise_action(
        self,
        db: Session,
        meeting_id: int,
        action_id: int,
        scene: str,
        recipients: Optional[List[str]] = None,
    ) -> dict:
        """对会议行动项发起督办邮件。"""
        from services import supervise as supervise_service

        action = (
            db.query(PmwbMeetingAction)
            .filter(PmwbMeetingAction.id == action_id, PmwbMeetingAction.meeting_id == meeting_id)
            .first()
        )
        if not action:
            raise NotFoundException(f"会议行动项不存在：meeting_id={meeting_id}, action_id={action_id}")

        meeting = self.get(db, meeting_id)
        target_recipients = recipients if recipients is not None else [action.owner] if action.owner else []

        return supervise_service.supervise_action(
            scene=scene,
            action={
                "id": action.id,
                "content": action.content,
                "owner": action.owner,
                "due_date": action.due_date.isoformat() if action.due_date else "",
                "status": action.status,
                "meeting_title": meeting.title if meeting else "",
            },
            recipients=target_recipients,
        )

    def delete(self, db: Session, id: int) -> bool:
        db_obj = self.get(db, id)
        if not db_obj:
            return False
        db.delete(db_obj)
        db.commit()
        return True


meeting_service = MeetingService()
