import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from tests.factories import KnowledgeFactory


def test_list_knowledge_items(client: TestClient, db):
    KnowledgeFactory.create(db, item_id="KN-001", title="知识1")
    KnowledgeFactory.create(db, item_id="KN-002", title="知识2")
    response = client.get("/api/v1/knowledge")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["total"] >= 2


def test_create_knowledge_item(client: TestClient, db, monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr("services.knowledge.write_markdown", lambda path, content: None)
        payload = {
            "item_id": "KN-CREATE-001",
            "title": "新建知识",
            "category": "product",
            "sub_category": "测试",
            "tags": "标签1,标签2",
            "obsidian_path": os.path.join(tmpdir, "KN-CREATE-001.md"),
            "summary": "摘要",
            "content": "内容",
        }
        response = client.post("/api/v1/knowledge", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["title"] == "新建知识"
        assert data["data"]["item_id"] == "KN-CREATE-001"


def test_get_knowledge_content(client: TestClient, db, monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "KN-CONTENT-001.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("# 测试内容\n\n正文")
        KnowledgeFactory.create(db, item_id="KN-CONTENT-001", title="内容知识", obsidian_path=path)
        response = client.get("/api/v1/knowledge/1/content")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["content"] == "# 测试内容\n\n正文"


def test_update_knowledge_item(client: TestClient, db):
    item = KnowledgeFactory.create(db, item_id="KN-UPDATE-001", title="旧标题")
    response = client.put(
        f"/api/v1/knowledge/{item.id}",
        json={"title": "新标题", "tags": "更新"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["title"] == "新标题"
    assert data["data"]["tags"] == "更新"


def test_get_knowledge_categories(client: TestClient, db):
    KnowledgeFactory.create(db, category="product")
    KnowledgeFactory.create(db, category="operation")
    response = client.get("/api/v1/knowledge/meta/categories")
    assert response.status_code == 200
    data = response.json()
    assert "product" in data["data"]
    assert "operation" in data["data"]
