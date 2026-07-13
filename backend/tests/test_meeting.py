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
