from fastapi.testclient import TestClient

from tests.factories import TodoFactory


def test_create_todo(client: TestClient, db):
    payload = {
        "title": "完成需求文档",
        "category": "requirement",
        "priority": "P1",
        "status": "todo",
        "due_date": "2026-07-20",
    }
    response = client.post("/api/v1/todos", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["title"] == "完成需求文档"
    assert data["data"]["status"] == "todo"


def test_list_todos(client: TestClient, db):
    TodoFactory.create(db, title="待办1")
    TodoFactory.create(db, title="待办2")
    response = client.get("/api/v1/todos")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["total"] >= 2


def test_toggle_todo_status(client: TestClient, db):
    todo = TodoFactory.create(db, status="todo")
    response = client.put(f"/api/v1/todos/{todo.id}/status", json={"status": "done"})
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["status"] == "done"
