"""测试数据工厂，用于快速构造测试数据。"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from db.models import (
    PmwbKnowledgeItem,
    PmwbMeeting,
    PmwbMeetingAction,
    PmwbMeetingAttendee,
    PmwbOperationIssue,
    PmwbRequirementExt,
    PmwbTodo,
)


class OperationIssueFactory:
    _counter = 0

    @staticmethod
    def create(
        db: Session,
        issue_no: str = None,
        title: str = "测试问题",
        issue_type: str = "data_abnormal",
        impact_level: str = "P2",
        status: str = "pending",
        handler: str = "测试人",
        **kwargs,
    ):
        OperationIssueFactory._counter += 1
        if issue_no is None:
            issue_no = f"ISSUE-TEST-{uuid.uuid4().hex[:8].upper()}"
        obj = PmwbOperationIssue(
            issue_no=issue_no,
            title=title,
            issue_type=issue_type,
            impact_level=impact_level,
            status=status,
            handler=handler,
            **kwargs,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj


class MeetingFactory:
    @staticmethod
    def create(
        db: Session,
        meeting_id: str = "MEET-TEST-001",
        title: str = "测试会议",
        meeting_type: str = "internal_regular",
        status: str = "planned",
        host: str = "主持人",
        start_time: datetime = None,
        **kwargs,
    ):
        if start_time is None:
            start_time = datetime.utcnow() + timedelta(days=1)
        obj = PmwbMeeting(
            meeting_id=meeting_id,
            title=title,
            meeting_type=meeting_type,
            status=status,
            host=host,
            start_time=start_time,
            **kwargs,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @staticmethod
    def add_attendee(db: Session, meeting_id: int, name: str = "参会人", email: str = "test@example.com"):
        obj = PmwbMeetingAttendee(meeting_id=meeting_id, name=name, email=email, is_required=1)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @staticmethod
    def add_action(db: Session, meeting_id: int, content: str = "行动项", owner: str = "负责人"):
        obj = PmwbMeetingAction(meeting_id=meeting_id, content=content, owner=owner, status="pending")
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj


class TodoFactory:
    @staticmethod
    def create(
        db: Session,
        title: str = "测试待办",
        category: str = "requirement",
        priority: str = "P2",
        status: str = "todo",
        due_date=None,
        **kwargs,
    ):
        obj = PmwbTodo(
            title=title,
            category=category,
            priority=priority,
            status=status,
            due_date=due_date,
            **kwargs,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj


class RequirementExtFactory:
    @staticmethod
    def create(
        db: Session,
        req_id: str = "REQ-TEST-001",
        status: str = "proposed",
        priority: str = "P2",
        tags: str = "",
        personal_note: str = "",
        **kwargs,
    ):
        obj = PmwbRequirementExt(
            req_id=req_id,
            status=status,
            priority=priority,
            tags=tags,
            personal_note=personal_note,
            **kwargs,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj


class KnowledgeFactory:
    _counter = 0

    @staticmethod
    def create(
        db: Session,
        item_id: str = None,
        title: str = "测试知识",
        category: str = "需求分析",
        obsidian_path: str = None,
        **kwargs,
    ):
        KnowledgeFactory._counter += 1
        if item_id is None:
            item_id = f"KN-TEST-{KnowledgeFactory._counter:04d}"
        if obsidian_path is None:
            obsidian_path = f"/vault/{item_id}.md"
        obj = PmwbKnowledgeItem(
            item_id=item_id,
            title=title,
            category=category,
            obsidian_path=obsidian_path,
            **kwargs,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj
