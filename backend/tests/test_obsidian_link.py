"""Obsidian 联动测试：笔记读取（含越界校验）+ 运营工单/会议 一键沉淀。"""
import pytest

from core.config import settings


@pytest.fixture
def vault_tmp(tmp_path, monkeypatch):
    """把 Obsidian vault 根目录指向临时目录，避免污染真实知识库。"""
    monkeypatch.setattr(settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    return tmp_path


def test_obsidian_content_read(client, vault_tmp):
    (vault_tmp / "note.md").write_text("# Hello\n内容", encoding="utf-8")
    res = client.get("/api/v1/obsidian/content", params={"path": "note.md"})
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["exists"] is True
    assert "Hello" in data["content"]
    assert data["absolute_path"].endswith("note.md")


def test_obsidian_content_missing(client, vault_tmp):
    res = client.get("/api/v1/obsidian/content", params={"path": "no_such.md"})
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["exists"] is False
    assert data["content"] is None
    assert data["absolute_path"].endswith("no_such.md")


def test_obsidian_content_traversal_rejected(client, vault_tmp):
    res = client.get("/api/v1/obsidian/content", params={"path": "../escape.md"})
    assert res.status_code == 400
    assert res.json()["code"] == 400


def test_sediment_operation_issue(client, vault_tmp):
    # 创建运营工单（bug 类）
    payload = {
        "issue_no": "BUG-20260716-001",
        "title": "登录页报错",
        "category": "bug",
        "issue_type": "bug",
        "status": "resolved",
        "impact_level": "P1",
        "root_cause": "空指针",
        "solution": "加判空",
        "handler": "张三",
    }
    create = client.post("/api/v1/operation/issues", json=payload)
    assert create.status_code == 200
    issue_id = create.json()["data"]["id"]

    # 一键沉淀
    res = client.post(f"/api/v1/operation/issues/{issue_id}/sediment")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["created"] is True
    assert data["obsidian_path"].startswith("11-业务运营/Bug解决方案/")
    assert data["obsidian_path"].endswith(".md")

    # 文件确实写入临时 vault
    written = vault_tmp / data["obsidian_path"]
    assert written.exists()
    text = written.read_text(encoding="utf-8")
    assert "登录页报错" in text
    assert "空指针" in text

    # 知识条目索引已建（双向关联）
    know = client.get("/api/v1/knowledge", params={"source_type": "operation"})
    assert know.status_code == 200
    items = know.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["source_id"] == str(issue_id)
    assert items[0]["obsidian_path"] == data["obsidian_path"]

    # 工单 obsidian_path 已回填
    issue = client.get(f"/api/v1/operation/issues/{issue_id}")
    assert issue.json()["data"]["obsidian_path"] == data["obsidian_path"]

    # 幂等：再次沉淀返回已存在索引，不重复创建
    res2 = client.post(f"/api/v1/operation/issues/{issue_id}/sediment")
    assert res2.status_code == 200
    assert res2.json()["data"]["created"] is False
    know2 = client.get("/api/v1/knowledge", params={"source_type": "operation"})
    assert know2.json()["data"]["total"] == 1


def test_sediment_meeting(client, vault_tmp):
    payload = {
        "meeting_id": "MEET-20260716-001",
        "title": "周会",
        "meeting_type": "internal_regular",
        "status": "held",
        "agendas": [
            {"seq": 1, "topic": "议题一", "conclusion": "结论一", "division": "张三负责"},
        ],
        "actions": [
            {"content": "行动一", "owner": "李四", "category": "operation", "template": "厂家团队待办模板"},
        ],
    }
    create = client.post("/api/v1/meetings", json=payload)
    assert create.status_code == 200
    meeting_id = create.json()["data"]["id"]

    res = client.post(f"/api/v1/meetings/{meeting_id}/sediment")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["created"] is True
    # 落盘到真实 vault 目录 05-会议纪要，命名 【日期】-标题.md
    assert data["obsidian_path"].startswith("05-会议纪要/")
    assert data["obsidian_path"].endswith(".md")

    written = vault_tmp / data["obsidian_path"]
    assert written.exists()
    text = written.read_text(encoding="utf-8")
    assert "周会" in text
    assert "## 二、会议议程与讨论" in text
    assert "议题一" in text
    assert "结论一" in text
    assert "## 四、待办事项（行动项）" in text
    assert "李四" in text
    assert "厂家团队待办模板" in text

    know = client.get("/api/v1/knowledge", params={"source_type": "meeting"})
    assert know.json()["data"]["total"] == 1
    assert know.json()["data"]["items"][0]["category"] == "meeting"


def test_kc2_5_meeting_force_overwrite_and_delete(db, vault_tmp):
    """kc-2-5：会议纪要 force=true 整体覆盖（无残留/无重复）；删除纪要三者一致（文件+索引+关联）。"""
    from db.models import PmwbKnowledgeItem, PmwbKnowledgeLink
    from services.meeting import meeting_service
    from services.obsidian_link import sediment_meeting, delete_meeting_minutes
    from services.knowledge_link_service import link_note

    m = meeting_service.create_with_relations(db, {
        "meeting_id": "MEET-KC25-001",
        "title": "纪要标题",
        "meeting_type": "internal_regular",
        "status": "held",
        "agendas": [{"seq": 1, "topic": "议题A", "conclusion": "结论一"}],
    })

    # 首次沉淀（非 force）
    res = sediment_meeting(db, m.id, force=False)
    assert res["created"] is True
    path = res["obsidian_path"]
    text0 = (vault_tmp / path).read_text(encoding="utf-8")
    assert "结论一" in text0
    assert text0.count("## 三、会议决议") == 1

    # force=true 再次沉淀：整体覆盖，不产生重复区块（幂等）
    res2 = sediment_meeting(db, m.id, force=True)
    assert res2["created"] is False
    text1 = (vault_tmp / path).read_text(encoding="utf-8")
    assert text1.count("## 三、会议决议") == 1  # 无重复区块（force 覆盖非追加）
    assert text1.count("## 一、会议信息") == 1

    # 额外建一条关联，再删除纪要应一并清理（文件 + 索引 + 关联 三者一致）
    item = db.query(PmwbKnowledgeItem).filter(
        PmwbKnowledgeItem.source_type == "meeting", PmwbKnowledgeItem.source_id == str(m.id)
    ).first()
    assert item is not None
    link_note(db, item.id, source_type="meeting", source_id=str(m.id), link_type="main")
    db.commit()

    delete_meeting_minutes(db, m.id)
    assert not (vault_tmp / path).exists()  # 文件已删
    idx = db.query(PmwbKnowledgeItem).filter(
        PmwbKnowledgeItem.source_type == "meeting", PmwbKnowledgeItem.source_id == str(m.id)
    ).first()
    assert idx is None  # 索引已删
    link = db.query(PmwbKnowledgeLink).filter(
        PmwbKnowledgeLink.source_type == "meeting", PmwbKnowledgeLink.source_id == str(m.id)
    ).first()
    assert link is None  # 关联已删



def test_sediment_requirement_rules_draft_story_with_rules(db, vault_tmp, monkeypatch):
    """kc-3：需求级沉淀不再要求「已定稿」，含业务规则但未定稿的故事也能沉淀。"""
    import json

    from core.exceptions import NotFoundException
    from db.models import PmwbBusinessDomain, PmwbRequirementExt, PmwbUserStory
    from services.obsidian_link import sediment_requirement_rules

    monkeypatch.setattr(
        "services.knowledge_link_service._sync_frontmatter_and_section",
        lambda db, kid: None,
    )
    db.add(PmwbBusinessDomain(domain_code="ywt-broadband", domain_name="一网通宽带", domain_group="商客业务"))
    db.add(PmwbRequirementExt(req_id="REQ-TEST-001", req_name="测试需求", domain_code="ywt-broadband", status="closed"))
    db.add(PmwbUserStory(req_id="REQ-TEST-001", seq=1, title="故事1",
                         rules=json.dumps(["规则A：需实名认证"]), finalized=0))
    db.commit()
    res = sediment_requirement_rules(db, "REQ-TEST-001")
    assert res["stories_sedimented"] == 1
    written = vault_tmp / res["obsidian_path"]
    assert written.exists()
    assert "规则A" in written.read_text(encoding="utf-8")


def test_sediment_requirement_rules_no_rules_404(db, vault_tmp, monkeypatch):
    """无业务规则的用户故事不应沉淀（抛出 NotFoundException）。"""
    import json

    from core.exceptions import NotFoundException
    from db.models import PmwbBusinessDomain, PmwbRequirementExt, PmwbUserStory
    from services.obsidian_link import sediment_requirement_rules

    monkeypatch.setattr(
        "services.knowledge_link_service._sync_frontmatter_and_section",
        lambda db, kid: None,
    )
    db.add(PmwbBusinessDomain(domain_code="ywt-broadband", domain_name="一网通宽带", domain_group="商客业务"))
    db.add(PmwbRequirementExt(req_id="REQ-TEST-002", req_name="测试需求2", domain_code="ywt-broadband", status="closed"))
    db.add(PmwbUserStory(req_id="REQ-TEST-002", seq=1, title="故事无规则", rules="", finalized=0))
    db.commit()
    try:
        sediment_requirement_rules(db, "REQ-TEST-002")
        assert False, "应抛出 NotFoundException"
    except NotFoundException:
        pass
