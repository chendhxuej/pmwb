from fastapi.testclient import TestClient

from tests.factories import OperationIssueFactory, TodoFactory, MeetingFactory


def test_dashboard_stats(client: TestClient, db):
    TodoFactory.create(db, status="todo")
    MeetingFactory.create(db, status="planned")
    OperationIssueFactory.create(db, status="pending")
    response = client.get("/api/v1/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "stats" in data["data"]
    assert data["data"]["stats"]["todo_total"] >= 1
