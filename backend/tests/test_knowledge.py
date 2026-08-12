import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from tests.factories import KnowledgeFactory, RequirementExtFactory, OperationIssueFactory


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


def test_kc2_3_requirement_rules_sediment_and_main_link(client, db, monkeypatch, tmp_path):
    """kc-2-3：用户故事规则沉淀到场景规则子笔记，且需求沉淀回链主笔记。"""
    from db.models import PmwbBusinessDomain, PmwbKnowledgeItem, PmwbKnowledgeLink, PmwbUserStory
    from services.knowledge_link_service import ensure_domain_main_note

    monkeypatch.setattr("core.config.settings.OBSIDIAN_VAULT_PATH", str(tmp_path))

    domain = PmwbBusinessDomain(domain_code="ywt", domain_name="一网通", domain_group="政企业务", enabled=True)
    db.add(domain)
    db.commit()
    main = ensure_domain_main_note(db, "ywt")

    RequirementExtFactory.create(db, req_id="REQ-KC23", domain_code="ywt", status="closed")
    story = PmwbUserStory(req_id="REQ-KC23", seq=1, title="故事1", desc="d",
                          rules='["规则A", "规则B"]', finalized=1)
    db.add(story)
    db.commit()

    # 沉淀规则 → 场景规则子笔记 + 关联
    resp = client.post("/api/v1/knowledge/sediment/requirement/REQ-KC23/rules")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["stories_sedimented"] == 1
    sub = db.query(PmwbKnowledgeItem).filter(PmwbKnowledgeItem.sub_category == "场景规则").first()
    assert sub is not None
    link = (
        db.query(PmwbKnowledgeLink)
        .filter(PmwbKnowledgeLink.source_type == "requirement", PmwbKnowledgeLink.source_id == "REQ-KC23")
        .first()
    )
    assert link is not None

    # 需求沉淀 → 回链主笔记
    resp2 = client.post("/api/v1/knowledge/sediment/requirement/REQ-KC23")
    assert resp2.status_code == 200
    main_link = (
        db.query(PmwbKnowledgeLink)
        .filter(PmwbKnowledgeLink.knowledge_item_id == main["item"]["id"],
                PmwbKnowledgeLink.source_type == "requirement")
        .first()
    )
    assert main_link is not None


def test_kc2_3_archive_operation_manual(client, db, monkeypatch, tmp_path):
    """kc-2-3：操作手册交付物归档到业务知识交付物目录并登记主笔记。"""
    from db.models import PmwbBusinessDomain, PmwbDevTicket, PmwbDevDeliverable
    from services.knowledge_link_service import ensure_domain_main_note

    monkeypatch.setattr("core.config.settings.OBSIDIAN_VAULT_PATH", str(tmp_path))

    domain = PmwbBusinessDomain(domain_code="ywt", domain_name="一网通", domain_group="政企业务", enabled=True)
    db.add(domain)
    db.commit()
    ensure_domain_main_note(db, "ywt")

    RequirementExtFactory.create(db, req_id="REQ-ARC", domain_code="ywt")
    ticket = PmwbDevTicket(req_id="REQ-ARC", ticket_no="DEV-ARC", system_name="系统", status="archived")
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    src = tmp_path / "src_manual.pdf"
    src.write_text("manual")
    d = PmwbDevDeliverable(ticket_id=ticket.id, deliverable_type="operation_manual",
                           file_name="操作手册.pdf", local_path=str(src))
    db.add(d)
    db.commit()

    resp = client.post("/api/v1/knowledge/sediment/requirement/REQ-ARC/archive-manual")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["archived"]) == 1
    assert (tmp_path / "01-业务知识/政企业务/一网通/05-交付物/attachments/操作手册.pdf").exists()
    # 主笔记 frontmatter related_deliverables 已登记
    from utils.obsidian import read_frontmatter
    main_path = f"01-业务知识/政企业务/一网通/一网通 业务知识主笔记.md"
    fm = read_frontmatter(main_path)
    assert "操作手册.pdf" in (fm.get("related_deliverables") or [])


def test_kc2_4_operation_rules_sediment_and_link(client, db, monkeypatch, tmp_path):
    """kc-2-4：运营工单结构化经验沉淀到场景规则子笔记，并记录工单→子笔记关联。"""
    from db.models import PmwbBusinessDomain, PmwbKnowledgeItem, PmwbKnowledgeLink
    from services.knowledge_link_service import ensure_domain_main_note

    monkeypatch.setattr("core.config.settings.OBSIDIAN_VAULT_PATH", str(tmp_path))

    domain = PmwbBusinessDomain(domain_code="ywt", domain_name="一网通", domain_group="政企业务", enabled=True)
    db.add(domain)
    db.commit()
    ensure_domain_main_note(db, "ywt")

    issue = OperationIssueFactory.create(
        db, issue_no="OP-KC24", title="工单沉淀测试", domain_code="ywt", status="closed",
        root_cause_type="data_issue", impact_scope="partial_region", solution_type="data_repair",
        root_cause="数据口径不一致", solution="修正计算逻辑", lesson_learned="增加校验",
    )

    resp = client.post(f"/api/v1/knowledge/sediment/operation/{issue.id}/rules")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["issue_sedimented"] == "OP-KC24"

    sub = db.query(PmwbKnowledgeItem).filter(PmwbKnowledgeItem.sub_category == "场景规则").first()
    assert sub is not None
    from utils.obsidian import read_markdown
    content = read_markdown(sub.obsidian_path)
    assert "OP-KC24" in content
    assert "数据问题" in content  # 根因分类标签

    link = (
        db.query(PmwbKnowledgeLink)
        .filter(PmwbKnowledgeLink.source_type == "operation", PmwbKnowledgeLink.source_id == str(issue.id))
        .first()
    )
    assert link is not None

    # 重复触发幂等（整体替换，不重复堆积）
    resp2 = client.post(f"/api/v1/knowledge/sediment/operation/{issue.id}/rules")
    assert resp2.status_code == 200
    content2 = read_markdown(sub.obsidian_path)
    assert content2.count("## 场景规则 · OP-KC24") == 1

