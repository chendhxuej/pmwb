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
    assert data["obsidian_path"].startswith("01-运营知识/Bug解决方案/")
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
        "meeting_type": "project_weekly",
        "status": "held",
    }
    create = client.post("/api/v1/meetings", json=payload)
    assert create.status_code == 200
    meeting_id = create.json()["data"]["id"]

    res = client.post(f"/api/v1/meetings/{meeting_id}/sediment")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["created"] is True
    assert data["obsidian_path"].startswith("03-会议资产/")
    assert data["obsidian_path"].endswith(".md")

    written = vault_tmp / data["obsidian_path"]
    assert written.exists()
    assert "周会" in written.read_text(encoding="utf-8")

    know = client.get("/api/v1/knowledge", params={"source_type": "meeting"})
    assert know.json()["data"]["total"] == 1
