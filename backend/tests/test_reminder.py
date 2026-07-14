import uuid
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from db.models import EmailRecord
from services.reminder import reminder_service


def _create_email_record(db: Session, req_id: str = "REQ-REMINDER-001", email_type: str = "pmwb_reminder") -> EmailRecord:
    record = EmailRecord(
        req_id=req_id,
        req_name="测试需求",
        email_type=email_type,
        recipient="sa@example.com",
        recipient_name="测试SA",
        subject="催办：测试需求",
        content="请尽快处理",
        send_status="success",
        source="pmwb",
        sender="pmwb",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def test_send_reminder_success(client: TestClient, db: Session, monkeypatch):
    mock_client = MagicMock()
    mock_client.send_email.return_value = {"message_id": "msg-123", "status": "ok"}
    monkeypatch.setattr(reminder_service, "email_client", mock_client)
    payload = {
        "req_id": "REQ-REMINDER-001",
        "req_name": "测试需求",
        "to": "sa@example.com",
        "subject": "催办：测试需求",
        "body": "请尽快处理该需求",
        "operator": "pmwb",
    }
    response = client.post("/api/v1/reminders/send", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["success"] is True
    assert data["data"]["record_id"] > 0

    # 验证数据库记录
    record = db.query(EmailRecord).filter(EmailRecord.req_id == "REQ-REMINDER-001").first()
    assert record is not None
    assert record.send_status == "success"
    assert record.email_type == "pmwb_reminder"
    assert record.recipient == "sa@example.com"


def test_send_reminder_failure(client: TestClient, db: Session, monkeypatch):
    mock_client = MagicMock()
    mock_client.send_email.side_effect = Exception("邮件中心不可用")
    monkeypatch.setattr(reminder_service, "email_client", mock_client)
    payload = {
        "req_id": "REQ-REMINDER-002",
        "req_name": "测试需求失败",
        "to": "sa@example.com",
        "subject": "催办：测试需求",
        "body": "请尽快处理",
    }
    response = client.post("/api/v1/reminders/send", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["success"] is False

    record = db.query(EmailRecord).filter(EmailRecord.req_id == "REQ-REMINDER-002").first()
    assert record is not None
    assert record.send_status == "failed"
    assert "邮件中心不可用" in record.error_msg


def test_list_reminders_by_req_id(client: TestClient, db: Session):
    _create_email_record(db, req_id="REQ-REMINDER-003")
    _create_email_record(db, req_id="REQ-REMINDER-003")
    response = client.get("/api/v1/reminders/REQ-REMINDER-003")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert len(data["data"]) == 2
    assert data["data"][0]["req_id"] == "REQ-REMINDER-003"


def test_list_reminders_empty(client: TestClient, db: Session):
    response = client.get(f"/api/v1/reminders/REQ-NOT-EXIST-{uuid.uuid4().hex[:8]}")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"] == []
