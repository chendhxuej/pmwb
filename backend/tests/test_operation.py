from fastapi.testclient import TestClient

from tests.factories import OperationIssueFactory


def test_create_operation_issue(client: TestClient, db):
    payload = {
        "issue_no": "ISSUE-20260713-001",
        "title": "数据异常",
        "issue_type": "data_abnormal",
        "impact_level": "P1",
        "status": "pending",
        "handler": "张三",
    }
    response = client.post("/api/v1/operation/issues", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["issue_no"] == "ISSUE-20260713-001"
    assert data["data"]["status"] == "pending"


def test_list_operation_issues(client: TestClient, db):
    OperationIssueFactory.create(db, issue_no="ISSUE-001")
    OperationIssueFactory.create(db, issue_no="ISSUE-002")
    response = client.get("/api/v1/operation/issues")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["total"] >= 2


def test_get_operation_issue_stats(client: TestClient, db):
    OperationIssueFactory.create(db, status="pending")
    OperationIssueFactory.create(db, status="resolved")
    response = client.get("/api/v1/operation/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["pending"] >= 1
    assert data["data"]["resolved"] >= 1


def test_update_operation_issue(client: TestClient, db):
    issue = OperationIssueFactory.create(db, issue_no="ISSUE-UPDATE-001")
    response = client.put(
        f"/api/v1/operation/issues/{issue.id}",
        json={"status": "processing"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["status"] == "processing"
