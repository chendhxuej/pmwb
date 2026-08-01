"""会议行动项子模块接口测试。"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from db.models import PmwbMeetingAction
from tests.factories import MeetingFactory


_counter = 0


def _next_meeting_id():
    global _counter
    _counter += 1
    return f"MEET-MA3-{_counter:03d}"


def _make_action(db, *, content="行动项", owner="张三", status="pending", due_date=None):
    m = MeetingFactory.create(db, meeting_id=_next_meeting_id(), title="测试会议")
    a = PmwbMeetingAction(
        meeting_id=m.id,
        content=content,
        owner=owner,
        status=status,
        due_date=due_date,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return m, a


class TestMeetingActionList:
    """GET /api/v1/meetings/actions 列表接口。"""

    def test_list_actions_empty(self, client: TestClient):
        resp = client.get("/api/v1/meetings/actions")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_actions_returns_items(self, client, db):
        _make_action(db, content="待办A", owner="张三")
        resp = client.get("/api/v1/meetings/actions")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["content"] == "待办A"
        assert data["items"][0]["meeting_title"] == "测试会议"
        assert "meeting_id_no" in data["items"][0]

    def test_filter_by_status(self, client, db):
        _make_action(db, content="未完成", owner="张三", status="pending")
        _make_action(db, content="已完成", owner="李四", status="done")
        resp = client.get("/api/v1/meetings/actions?status=pending")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["content"] == "未完成"

    def test_filter_by_owner(self, client, db):
        _make_action(db, content="A", owner="张三")
        _make_action(db, content="B", owner="李四")
        resp = client.get("/api/v1/meetings/actions?owner=张三")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["content"] == "A"

    def test_filter_by_due_date_range(self, client, db):
        today = date.today()
        _make_action(db, content="今天到期", owner="张三", due_date=today)
        _make_action(db, content="三天后到期", owner="张三", due_date=today + timedelta(days=3))
        resp = client.get(f"/api/v1/meetings/actions?due_start={today}&due_end={today}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["content"] == "今天到期"


class TestMeetingActionStatusUpdate:
    """PUT /api/v1/meetings/{id}/actions/{id}/status 状态更新。"""

    def test_update_status_success(self, client, db):
        _, a = _make_action(db, content="更新状态测试")
        resp = client.put(
            f"/api/v1/meetings/{a.meeting_id}/actions/{a.id}/status",
            json={"status": "done"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "done"

    def test_update_status_not_found(self, client, db):
        _, a = _make_action(db, content="更新状态测试")
        resp = client.put(
            f"/api/v1/meetings/{a.meeting_id}/actions/{a.id + 9999}/status",
            json={"status": "done"},
        )
        assert resp.status_code == 404


class TestMeetingActionSupervise:
    """POST /api/v1/meetings/{id}/actions/{id}/supervise 督办邮件。"""

    def test_supervise_returns_result(self, client, db, monkeypatch):
        _, a = _make_action(db, content="督办测试", owner="王五")

        def fake_supervise_action(scene, action, recipients):
            return {"ok": True, "subject": f"督办-{action['content']}", "body": "请尽快处理"}

        monkeypatch.setattr(
            "services.supervise.supervise_action",
            fake_supervise_action,
        )

        resp = client.post(
            f"/api/v1/meetings/{a.meeting_id}/actions/{a.id}/supervise",
            json={"scene": "urge", "recipients": ["王五"]},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["ok"] is True

    def test_supervise_default_recipient_from_owner(self, client, db, monkeypatch):
        _, a = _make_action(db, content="督办测试2", owner="赵六")

        captured = {}

        def fake_supervise_action(scene, action, recipients):
            captured["recipients"] = recipients
            return {"ok": False, "error": "邮件中心不可用"}

        monkeypatch.setattr(
            "services.supervise.supervise_action",
            fake_supervise_action,
        )

        resp = client.post(
            f"/api/v1/meetings/{a.meeting_id}/actions/{a.id}/supervise",
            json={"scene": "sync"},
        )
        assert resp.status_code == 200
        assert captured["recipients"] == ["赵六"]
