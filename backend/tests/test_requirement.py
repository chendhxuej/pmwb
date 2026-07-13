from fastapi.testclient import TestClient

from db.models import SentEmail
from tests.factories import RequirementExtFactory


def _create_sent_email(db, **kwargs):
    defaults = {
        "req_id": "REQ-TEST-001",
        "req_name": "测试需求",
        "proposer": "张三",
        "propose_time": "2026-07-01",
        "background": "背景",
        "description": "描述",
        "clarification": "澄清",
        "system_name": "测试系统",
        "sa_name": "李四",
        "send_datetime": "2026-07-01",
        "workload": 5.0,
        "is_involved": 1,
        "dev_ticket_no": "TICKET-001",
        "involve_dev": "是",
    }
    defaults.update(kwargs)
    obj = SentEmail(**defaults)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def test_list_requirements(client: TestClient, db):
    _create_sent_email(db, req_id="REQ-001", req_name="需求1")
    _create_sent_email(db, req_id="REQ-002", req_name="需求2")
    RequirementExtFactory.create(db, req_id="REQ-001", status="accepted")
    response = client.get("/api/v1/requirements")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["total"] >= 2


def test_get_requirement_detail(client: TestClient, db):
    _create_sent_email(db, req_id="REQ-DETAIL-001", req_name="详情需求")
    RequirementExtFactory.create(db, req_id="REQ-DETAIL-001", priority="P0", status="dev")
    response = client.get("/api/v1/requirements/REQ-DETAIL-001")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["req_id"] == "REQ-DETAIL-001"
    assert data["data"]["ext"]["priority"] == "P0"


def test_update_requirement_ext(client: TestClient, db):
    _create_sent_email(db, req_id="REQ-UPDATE-001")
    RequirementExtFactory.create(db, req_id="REQ-UPDATE-001", status="proposed")
    response = client.put(
        "/api/v1/requirements/REQ-UPDATE-001",
        json={"status": "accepted", "priority": "P1", "tags": "标签1,标签2"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["ext"]["status"] == "accepted"
    assert data["data"]["ext"]["priority"] == "P1"
    assert data["data"]["ext"]["tags"] == "标签1,标签2"


def test_get_requirement_stats(client: TestClient, db):
    _create_sent_email(db, req_id="REQ-STAT-001")
    _create_sent_email(db, req_id="REQ-STAT-002")
    RequirementExtFactory.create(db, req_id="REQ-STAT-001", status="accepted")
    response = client.get("/api/v1/requirements/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["total"] >= 2
    assert data["data"]["accepted"] >= 1
