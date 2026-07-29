"""Tests for task_center service — source_url deep link verification."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base, PmwbTodo, PmwbOperationIssue, PmwbDevTicket, \
    PmwbMeetingAction, PmwbMeeting, PmwbKeyWork, PmwbKeyWorkMemberTask, \
    PmwbKeyWorkMilestone, PmwbRequirementEvaluation, PmwbRequirementExt
from services.task_center import TaskCenterService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def task_service():
    return TaskCenterService()


def _insert_todo(db, id=1, title="test todo", status="todo"):
    db.add(PmwbTodo(id=id, title=title, status=status))
    db.commit()


def _insert_operation_issue(db, id=1):
    db.add(PmwbOperationIssue(
        id=id, issue_no="OP-001", title="test issue", status="pending",
        handler="张三", impact_level="P1",
    ))
    db.commit()


def _insert_dev_ticket(db, id=1, ticket_no="TKT-001"):
    db.add(PmwbDevTicket(
        id=id, ticket_no=ticket_no, req_id="REQ-001", system_name="TestSys",
        description="test ticket", status="created", priority="P1",
    ))
    db.commit()


def _insert_meeting(db, id=1, title="Test Meeting"):
    from datetime import datetime
    db.add(PmwbMeeting(
        id=id, meeting_id=f"M-{id:04d}", title=title,
        start_time=datetime(2026, 7, 1, 9, 0),
    ))
    db.commit()


def _insert_meeting_action(db, id=1, meeting_id=1, content="test action"):
    db.add(PmwbMeetingAction(id=id, meeting_id=meeting_id, content=content, status="pending"))
    db.commit()


def _insert_key_work(db, id=1, title="Test KW"):
    db.add(PmwbKeyWork(
        id=id, work_no=f"KW-{id:04d}", title=title,
        owner="负责人", status="in_progress",
    ))
    db.commit()


def _insert_key_work_task(db, id=1, key_work_id=1, title="task1"):
    db.add(PmwbKeyWorkMemberTask(id=id, key_work_id=key_work_id, title=title, status="todo"))
    db.commit()


def _insert_key_work_milestone(db, id=1, key_work_id=1, name="MS1"):
    db.add(PmwbKeyWorkMilestone(id=id, key_work_id=key_work_id, name=name, status="pending"))
    db.commit()


def _insert_requirement_evaluation(db, req_id="REQ-001", sa_name="李明"):
    db.add(PmwbRequirementEvaluation(
        req_id=req_id, req_name="测试需求", proposer="王五",
        sa_name=sa_name, system_name="测试系统",
        workload=None,  # empty workload triggers collection
    ))
    db.commit()


class TestTaskCenterSourceUrl:

    def test_collect_todo_source_url_has_id(self, db_session, task_service):
        _insert_todo(db_session, id=42)
        items = task_service.collect_todo(db_session)
        assert len(items) == 1
        assert items[0].source_url == "/dashboard?id=42"
        assert "?" in items[0].source_url

    def test_collect_operation_issue_source_url_has_issueId(self, db_session, task_service):
        _insert_operation_issue(db_session, id=77)
        items = task_service.collect_operation_issue(db_session)
        assert len(items) == 1
        assert items[0].source_url == "/operation?issueId=77"

    def test_collect_dev_ticket_source_url_has_ticket_no(self, db_session, task_service):
        _insert_dev_ticket(db_session, id=10, ticket_no="TKT-999")
        items = task_service.collect_dev_ticket(db_session)
        assert len(items) == 1
        assert items[0].source_url == "/requirement-delivery?ticket=TKT-999"

    def test_collect_meeting_action_source_url_has_actionId(self, db_session, task_service):
        _insert_meeting(db_session, id=5)
        _insert_meeting_action(db_session, id=33, meeting_id=5)
        items = task_service.collect_meeting_action(db_session)
        assert len(items) == 1
        assert items[0].source_url == "/meeting?actionId=33"

    def test_collect_key_work_task_source_url_has_id(self, db_session, task_service):
        _insert_key_work(db_session, id=2)
        _insert_key_work_task(db_session, id=55, key_work_id=2)
        items = task_service.collect_key_work(db_session)
        # find the task item (not milestone)
        task_items = [t for t in items if t.detail.get("类型") == "成员待办"]
        assert len(task_items) >= 1
        assert task_items[0].source_url == "/key-works?id=task-55"

    def test_collect_key_work_milestone_source_url_has_id(self, db_session, task_service):
        _insert_key_work(db_session, id=3)
        _insert_key_work_milestone(db_session, id=66, key_work_id=3)
        items = task_service.collect_key_work(db_session)
        milestone_items = [t for t in items if t.detail.get("类型") == "里程碑"]
        assert len(milestone_items) >= 1
        assert milestone_items[0].source_url == "/key-works?id=milestone-66"

    def test_collect_requirement_urge_source_url_has_req_and_sa(self, db_session, task_service):
        _insert_requirement_evaluation(db_session, req_id="REQ-100", sa_name="李明")
        items = task_service.collect_requirement_urge(db_session)
        assert len(items) >= 1
        assert items[0].source_url == "/requirement-delivery?req=REQ-100&sa=李明"

    def test_all_six_sources_have_query_params(self, db_session, task_service):
        """Verify all 6 collector methods return source_url with query parameters."""
        _insert_todo(db_session, id=1)
        _insert_operation_issue(db_session, id=1)
        _insert_dev_ticket(db_session, id=1, ticket_no="T-001")
        _insert_meeting(db_session, id=1)
        _insert_meeting_action(db_session, id=1, meeting_id=1)
        _insert_key_work(db_session, id=1)
        _insert_key_work_task(db_session, id=1, key_work_id=1)
        _insert_key_work_milestone(db_session, id=1, key_work_id=1)
        _insert_requirement_evaluation(db_session, req_id="REQ-X1", sa_name="SA-1")

        # Collect from all sources
        items = task_service._collect(db_session)
        assert len(items) >= 6  # at least 6 items

        for item in items:
            assert "?" in item.source_url, \
                f"{item.source}:{item.source_id} source_url missing query params: {item.source_url}"
            assert len(item.source_url) > len(item.source_url.split("?")[0]) + 1, \
                f"{item.source} source_url query is empty: {item.source_url}"
