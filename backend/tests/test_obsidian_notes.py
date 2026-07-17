from fastapi.testclient import TestClient


def test_list_operation_notes(client: TestClient, db):
    """运营关联知识笔记列表接口可用（只读 vault，返回列表）。"""
    response = client.get("/api/v1/obsidian/notes")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["data"], list)


def test_read_note_path_traversal_rejected(client: TestClient, db):
    """读取笔记的路径穿越必须被拒绝。"""
    response = client.get("/api/v1/obsidian/content", params={"path": "../../etc/passwd"})
    assert response.status_code == 400


def test_write_note_path_traversal_rejected(client: TestClient, db):
    """写回笔记的路径穿越必须被拒绝。"""
    response = client.put(
        "/api/v1/obsidian/content",
        json={"path": "../../etc/passwd", "content": "hacked"},
    )
    assert response.status_code == 400
