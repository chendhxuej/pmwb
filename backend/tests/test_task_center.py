"""任务中心测试：ma-1 会议行动项标记 + tc-1 source_url 深链验证。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import (
    Base,
    PmwbTodo,
    PmwbOperationIssue,
    PmwbDevTicket,
    PmwbMeetingAction,
    PmwbMeeting,
    PmwbKeyWork,
    PmwbKeyWorkMemberTask,
    PmwbKeyWorkMilestone,
    PmwbRequirementEvaluation,
    PmwbRequirementExt,
)
from services.task_center import TaskCenterService
from tests.factories import MeetingFactory, TodoFactory


# ---------------------------------------------------------------------------
# ma-1 fixtures & helpers
# ---------------------------------------------------------------------------

_counter = 0


def _next_meeting_id():
    global _counter
    _counter += 1
    return f"MEET-MA1-{_counter:03d}"


@pytest.fixture
def svc():
    return TaskCenterService()


def _make_meeting_with_action(
    db: Session,
    *,
    content="行动项A",
    owner="张三",
    status="pending",
    related_todo_id=None,
):
    m = MeetingFactory.create(db, meeting_id=_next_meeting_id(), title="测试会议")
    a = MeetingFactory.add_action(db, meeting_id=m.id, content=content, owner=owner)
    if status != "pending":
        a.status = status
        db.commit()
        db.refresh(a)
    if related_todo_id is not None:
        a.related_todo_id = related_todo_id
        db.commit()
        db.refresh(a)
    return m, a


class TestMeetingActionSyncedToTodo:
    """会议行动项不再去重，全部返回，含 synced_to_todo 标记。"""

    def test_unsynced_action_synced_to_todo_false(self, db, svc):
        """未同步的行动项 synced_to_todo=False"""
        m, a = _make_meeting_with_action(db)
        items = svc.collect_meeting_action(db)
        matched = [i for i in items if i.source_id == str(a.id)]
        assert len(matched) == 1
        assert matched[0].synced_to_todo is False

    def test_synced_action_still_appears(self, db, svc):
        """已同步的行动项不再被跳过，仍然出现在 meeting_action 来源"""
        m, a = _make_meeting_with_action(db, content="已同步行动项")
        todo = TodoFactory.create(db, title="同步的待办", category="meeting")
        a.related_todo_id = todo.id
        db.commit()
        db.refresh(a)

        items = svc.collect_meeting_action(db)
        matched = [i for i in items if i.source_id == str(a.id)]
        assert len(matched) == 1, "已同步行动项应出现在 meeting_action 来源"

    def test_synced_action_synced_to_todo_true(self, db, svc):
        """已同步的行动项 synced_to_todo=True"""
        m, a = _make_meeting_with_action(db, content="已同步行动项2")
        todo = TodoFactory.create(db, title="同步的待办2", category="meeting")
        a.related_todo_id = todo.id
        db.commit()
        db.refresh(a)

        items = svc.collect_meeting_action(db)
        matched = [i for i in items if i.source_id == str(a.id)]
        assert matched[0].synced_to_todo is True

    def test_mixed_synced_and_unsynced(self, db, svc):
        """混合场景：同步+未同步的行动项都返回"""
        m1, a1 = _make_meeting_with_action(db, content="未同步")
        m2, a2 = _make_meeting_with_action(db, content="已同步")
        todo = TodoFactory.create(db, title="同步的待办3", category="meeting")
        a2.related_todo_id = todo.id
        db.commit()
        db.refresh(a2)

        items = svc.collect_meeting_action(db)
        ids = {i.source_id for i in items}
        assert str(a1.id) in ids
        assert str(a2.id) in ids
        synced_map = {i.source_id: i.synced_to_todo for i in items}
        assert synced_map[str(a1.id)] is False
        assert synced_map[str(a2.id)] is True

    def test_todo_source_not_affected(self, db, svc):
        """个人待办来源不受影响，仍包含同步副本"""
        m, a = _make_meeting_with_action(db, content="将同步的行动项")
        todo = TodoFactory.create(db, title="同步的待办4", category="meeting")
        a.related_todo_id = todo.id
        db.commit()

        todo_items = svc.collect_todo(db)
        todo_ids = {t.source_id for t in todo_items}
        assert str(todo.id) in todo_ids, "同步的待办仍出现在 todo 来源"


# ---------------------------------------------------------------------------
# tc-1 fixtures & helpers
# ---------------------------------------------------------------------------


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
    db.add(
        PmwbOperationIssue(
            id=id,
            issue_no="OP-001",
            title="test issue",
            status="pending",
            handler="张三",
            impact_level="P1",
        )
    )
    db.commit()


def _insert_dev_ticket(db, id=1, ticket_no="TKT-001"):
    db.add(
        PmwbDevTicket(
            id=id,
            ticket_no=ticket_no,
            req_id="REQ-001",
            system_name="TestSys",
            description="test ticket",
            status="created",
            priority="P1",
        )
    )
    db.commit()


def _insert_meeting(db, id=1, title="Test Meeting"):
    from datetime import datetime

    db.add(
        PmwbMeeting(
            id=id,
            meeting_id=f"M-{id:04d}",
            title=title,
            start_time=datetime(2026, 7, 1, 9, 0),
        )
    )
    db.commit()


def _insert_meeting_action(db, id=1, meeting_id=1, content="test action"):
    db.add(
        PmwbMeetingAction(
            id=id, meeting_id=meeting_id, content=content, status="pending"
        )
    )
    db.commit()


def _insert_key_work(db, id=1, title="Test KW"):
    db.add(
        PmwbKeyWork(
            id=id,
            work_no=f"KW-{id:04d}",
            title=title,
            owner="负责人",
            status="in_progress",
        )
    )
    db.commit()


def _insert_key_work_task(db, id=1, key_work_id=1, title="task1"):
    db.add(
        PmwbKeyWorkMemberTask(
            id=id, key_work_id=key_work_id, title=title, status="todo"
        )
    )
    db.commit()


def _insert_key_work_milestone(db, id=1, key_work_id=1, name="MS1"):
    db.add(
        PmwbKeyWorkMilestone(
            id=id, key_work_id=key_work_id, name=name, status="pending"
        )
    )
    db.commit()


def _insert_requirement_evaluation(
    db,
    req_id="REQ-001",
    sa_name="李明",
    workload=None,
    review_workload=None,
    system_name="测试系统",
):
    db.add(
        PmwbRequirementEvaluation(
            req_id=req_id,
            req_name="测试需求",
            proposer="王五",
            sa_name=sa_name,
            system_name=system_name,
            workload=workload,
            review_workload=review_workload,
        )
    )
    db.commit()


class TestTaskCenterSourceUrl:

    def test_collect_todo_source_url_has_id(self, db_session, task_service):
        _insert_todo(db_session, id=42)
        items = task_service.collect_todo(db_session)
        assert len(items) == 1
        assert items[0].source_url == "/todo?id=42"
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

    def test_collect_requirement_urge_excludes_reviewed_zero_workload(self, db_session, task_service):
        """已复核（复核工作量非空，含 0=不需要开发）一律不催办，与前端状态列口径对齐。"""
        # 场景1：workload=0 + review_workload=0（评估不需要开发）→ 不催办
        _insert_requirement_evaluation(
            db_session, req_id="REQ-RV-1", sa_name="吴雨霜", workload=0.0,
            review_workload=0.0, system_name="CRM",
        )
        # 场景2：workload=None + review_workload=5（已复核但工作量漏填）→ 不催办
        _insert_requirement_evaluation(
            db_session, req_id="REQ-RV-2", sa_name="秦新", workload=None,
            review_workload=5.0, system_name="电子协议",
        )
        # 场景3：workload=None + review_workload=None（真正评估未完成）→ 催办
        _insert_requirement_evaluation(
            db_session, req_id="REQ-RV-3", sa_name="陈山", workload=None,
            review_workload=None, system_name="订单中心",
        )
        items = task_service.collect_requirement_urge(db_session)
        task_ids = {it.task_id for it in items}
        assert not any("REQ-RV-1" in t for t in task_ids), "已复核(复核=0)不应催办"
        assert not any("REQ-RV-2" in t for t in task_ids), "已复核(工作量漏填)不应催办"
        assert any("REQ-RV-3" in t for t in task_ids), "评估未完成应催办"

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

        items = task_service._collect(db_session)
        assert len(items) >= 6

        for item in items:
            assert "?" in item.source_url, (
                f"{item.source}:{item.source_id} source_url missing query params: {item.source_url}"
            )
            assert len(item.source_url) > len(item.source_url.split("?")[0]) + 1, (
                f"{item.source} source_url query is empty: {item.source_url}"
            )


# ---------------------------------------------------------------------------
# T-E：task_center_notify/urge 模板变量契约
# ---------------------------------------------------------------------------

class TestTaskSendTemplateVariables:
    """T-E：send_notification 模板变量——template_data 透传 + 无 template_data 回退兼容。"""

    def _mock_templates(self, monkeypatch, rendered):
        def fake_list(self, template_type):
            return [{"id": "tpl-tc", "type": template_type, "isDefault": True}]

        def fake_render(self, template_id, data):
            rendered.update(data.get("variables", {}))
            v = data.get("variables", {})
            return {
                "subject": "任务催办提醒" if v.get("sendType") == "urge" else "任务同步通知",
                "body": f"<div>{v.get('tasks')}</div>",
                "bodyFormat": "html",
            }

        monkeypatch.setattr("services.mail_dispatch.EmailCenterClient.list_templates", fake_list)
        monkeypatch.setattr("services.mail_dispatch.EmailCenterClient.render_template", fake_render)
        monkeypatch.setattr(
            "services.mail_dispatch.EmailCenterClient.send_email",
            lambda self, **kw: {"ok": True, "data": {"status": "ok"}},
        )

    def test_send_notification_with_template_data(self, db, svc, monkeypatch):
        """T-E：前端 template_data(tasks HTML+sendType) 进入模板变量，body 保留编辑内容。"""
        from schemas.task_center import TaskRef, TaskSendRequest

        todo = TodoFactory.create(db, title="T-E 任务测试")
        db.commit()
        db.refresh(todo)

        rendered: dict = {}
        self._mock_templates(monkeypatch, rendered)
        req = TaskSendRequest(
            tasks=[TaskRef(source="todo", source_id=str(todo.id))],
            to="owner@example.com",
            subject="催办：T-E 任务测试",
            body="编辑区自定义正文",
            send_type="urge",
            template_data={
                "tasks": "<ul><li><b>T-E 任务测试</b>（负责人：张三）</li></ul>",
                "sendType": "urge",
                "body": "编辑区自定义正文",
            },
        )
        result = svc.send_notification(db, req)
        assert result["success"] is True
        # tasks 用 template_data 的 HTML 列表，不被后端兜底覆盖
        assert rendered.get("tasks") == "<ul><li><b>T-E 任务测试</b>（负责人：张三）</li></ul>"
        assert rendered.get("sendType") == "urge"
        # body 传给 3210 前已由 Markdown 转 HTML，供模板 {{{body}}} 原始 HTML 插值
        assert "编辑区自定义正文" in rendered.get("body", "")
        assert rendered.get("body", "").startswith("<div")

    def test_send_notification_tasks_fallback(self, db, svc, monkeypatch):
        """T-E：无 template_data 时 tasks 回退后端 build_email_body 文本清单（旧调用兼容）。"""
        from schemas.task_center import TaskRef, TaskSendRequest

        todo = TodoFactory.create(db, title="T-E 回退测试")
        db.commit()
        db.refresh(todo)

        rendered: dict = {}
        self._mock_templates(monkeypatch, rendered)
        req = TaskSendRequest(
            tasks=[TaskRef(source="todo", source_id=str(todo.id))],
            to="owner@example.com",
            subject="通知：T-E 回退测试",
            send_type="notify",
        )
        result = svc.send_notification(db, req)
        assert result["success"] is True
        # 无 template_data → 后端兜底文本清单进入 tasks 变量
        assert "T-E 回退测试" in rendered.get("tasks", "")
        assert rendered.get("sendType") == "notify"
