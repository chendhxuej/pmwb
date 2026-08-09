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


def test_domain_related_main_note_and_sub_notes(client: TestClient, db):
    """kc-2-2/7：get_related 应区分主笔记(main)与子笔记(sub)。"""
    from db.models import PmwbBusinessDomain

    domain = PmwbBusinessDomain(
        domain_code="ftto", domain_name="FTTO", domain_group="政企业务", enabled=True
    )
    db.add(domain)
    db.commit()

    KnowledgeFactory.create(
        db, item_id="KN-MAIN", title="FTTO 业务知识主笔记",
        domain_code="ftto", note_type="main", sub_category="主笔记",
    )
    KnowledgeFactory.create(
        db, item_id="KN-SUB1", title="子笔记1", domain_code="ftto",
        note_type="sub", category="requirement",
    )
    KnowledgeFactory.create(
        db, item_id="KN-SUB2", title="子笔记2", domain_code="ftto",
        note_type="sub", category="operation",
    )

    response = client.get("/api/v1/basic-data/business-domains/ftto/related")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["main_note"] is not None
    assert data["main_note"]["title"] == "FTTO 业务知识主笔记"
    assert len(data["sub_notes"]) == 2


def test_ensure_main_notes_creates_missing_main(client: TestClient, db, monkeypatch):
    """kc-2-2/7：ensure-main-notes 为缺主笔记的领域自动保活主笔记。"""
    import services.knowledge_link_service as kls

    monkeypatch.setattr(kls, "write_markdown", lambda path, content: None)
    from db.models import PmwbBusinessDomain

    domain = PmwbBusinessDomain(
        domain_code="ftto2", domain_name="FTTO2", domain_group="政企业务", enabled=True
    )
    db.add(domain)
    db.commit()
    # 只有子笔记，无主笔记
    KnowledgeFactory.create(
        db, item_id="KN-SUB", title="子笔记", domain_code="ftto2", note_type="sub"
    )

    resp = client.post("/api/v1/knowledge/ensure-main-notes")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["main_notes_created"] >= 1

    rel = client.get("/api/v1/basic-data/business-domains/ftto2/related").json()["data"]
    assert rel["main_note"] is not None
