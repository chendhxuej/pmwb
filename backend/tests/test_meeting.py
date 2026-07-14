from fastapi.testclient import TestClient

from tests.factories import MeetingFactory


def test_create_meeting(client: TestClient, db):
    payload = {
        "meeting_id": "MEET-20260713-001",
        "title": "项目周会",
        "meeting_type": "project_weekly",
        "status": "planned",
        "host": "李四",
        "attendees": [{"name": "张三", "email": "zs@example.com", "is_required": 1}],
        "actions": [{"content": "整理会议纪要", "owner": "张三"}],
    }
    response = client.post("/api/v1/meetings", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["meeting_id"] == "MEET-20260713-001"
    assert data["data"]["attendees"][0]["name"] == "张三"
    assert data["data"]["actions"][0]["content"] == "整理会议纪要"


def test_list_meetings(client: TestClient, db):
    MeetingFactory.create(db, meeting_id="MEET-001")
    MeetingFactory.create(db, meeting_id="MEET-002")
    response = client.get("/api/v1/meetings")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["total"] >= 2


def test_create_meeting_empty_optional_fields(client: TestClient, db):
    """Regression: 空字符串的 start_time / end_time / due_date 不应导致 422。"""
    payload = {
        "meeting_id": "MEET-EMPTY-TIMES",
        "title": "空时间会议",
        "meeting_type": "other",
        "status": "planned",
        "start_time": "",
        "end_time": "",
        "location": "",
        "host": "",
        "summary": "",
        "obsidian_path": "",
        "related_req_id": "",
        "related_ticket_no": "",
        "attendees": [{"name": "王五", "is_required": 1}],
        "actions": [
            {"content": "待办事项", "owner": "", "due_date": "", "status": "pending"}
        ],
    }
    response = client.post("/api/v1/meetings", json=payload)
    assert response.status_code == 200
    d = response.json()["data"]
    assert d["start_time"] is None
    assert d["end_time"] is None
    assert d["actions"][0]["due_date"] is None
    # owner/location/host 等字符串可选字段：前端规范化后发 null，后端也接受空串
    assert d["actions"][0]["owner"] in (None, "")
