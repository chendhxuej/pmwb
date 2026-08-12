from fastapi.testclient import TestClient

from db.models import PmwbDevTicket, PmwbDevTicketLog
from tests.factories import RequirementExtFactory


def _create_ticket(db, **kwargs):
    defaults = {
        "ticket_no": "DTS-2026-0001",
        "req_id": "REQ-001",
        "system_name": "CRM",
        "dev_team": "研发团队A",
        "developer": "张三",
        "status": "created",
        "priority": "P2",
    }
    defaults.update(kwargs)
    obj = PmwbDevTicket(**defaults)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def test_create_dev_ticket(client: TestClient, db):
    payload = {
        "ticket_no": "DTS-2026-NEW-001",
        "req_id": "REQ-CREATE-001",
        "system_name": "BOSS",
        "dev_team": "研发团队B",
        "developer": "李四",
        "priority": "P1",
        "status": "created",
    }
    response = client.post("/api/v1/dev-tickets", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["ticket_no"] == "DTS-2026-NEW-001"
    assert data["data"]["status"] == "created"


def test_list_dev_tickets(client: TestClient, db):
    _create_ticket(db, ticket_no="DTS-001", req_id="REQ-LIST-001")
    _create_ticket(db, ticket_no="DTS-002", req_id="REQ-LIST-002")
    response = client.get("/api/v1/dev-tickets")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["total"] >= 2


def test_update_dev_ticket_status(client: TestClient, db):
    ticket = _create_ticket(db, ticket_no="DTS-UPDATE-001", status="created")
    response = client.put(
        f"/api/v1/dev-tickets/{ticket.id}/status",
        json={"status": "design_reviewed", "note": "设计评审通过"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["status"] == "design_reviewed"

    # 验证日志
    logs = db.query(PmwbDevTicketLog).filter(PmwbDevTicketLog.ticket_id == ticket.id).all()
    assert len(logs) == 1
    assert logs[0].to_status == "design_reviewed"


def test_get_dev_ticket_detail(client: TestClient, db):
    _create_ticket(db, ticket_no="DTS-DETAIL-001", req_id="REQ-DETAIL-001")
    response = client.get("/api/v1/dev-tickets/1")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["ticket_no"] == "DTS-DETAIL-001"


def test_get_dev_ticket_stats(client: TestClient, db):
    _create_ticket(db, ticket_no="DTS-STAT-001", status="created")
    _create_ticket(db, ticket_no="DTS-STAT-002", status="live")
    response = client.get("/api/v1/dev-tickets/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["total"] >= 2
    assert data["data"]["created"] >= 1
    assert data["data"]["live"] >= 1
