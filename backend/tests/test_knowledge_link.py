# -*- coding: utf-8 -*-
"""kc-2-1 业务知识关联 CRUD 测试：/knowledge/{item_id}/links 系列 + 主笔记生成。

覆盖：
- POST /knowledge/main-note 幂等生成标准模板主笔记（vault 临时目录，不污染真实库）
- POST /knowledge/{item_id}/links 建立关联
- GET /knowledge/{item_id}/links 查询关联
- DELETE /knowledge/{item_id}/links/{source_type}/{source_id} 移除关联
- 关联后主笔记 frontmatter related_* 数组同步
"""
import os

import pytest

from core.config import settings


@pytest.fixture
def vault_tmp(tmp_path, monkeypatch):
    """将 Obsidian vault 根目录指向临时目录，避免污染真实知识库。"""
    monkeypatch.setattr(settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    return tmp_path


def _create_domain(client, code="ftto", name="FTTO"):
    res = client.post(
        "/api/v1/basic-data/business-domains",
        json={
            "domain_code": code,
            "domain_name": name,
            "domain_group": "政企",
            "vault_path": f"01-业务知识/政企/{name}",
            "match_keywords": name,
            "enabled": 1,
        },
    )
    assert res.status_code == 200, res.text
    return res.json()["data"]


def test_create_main_note_idempotent(client, vault_tmp):
    _create_domain(client)
    # 第一次创建
    res = client.post("/api/v1/knowledge/main-note", json={"domain_code": "ftto"})
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["created"] is True
    item = data["item"]
    assert item["title"] == "FTTO 业务知识主笔记"
    assert item["obsidian_path"].startswith("01-业务知识/政企/FTTO/")
    # 文件存在且含标准模板
    path = item["obsidian_path"]
    assert os.path.exists(os.path.join(str(vault_tmp), path))
    content = open(os.path.join(str(vault_tmp), path), encoding="utf-8").read()
    assert "## 1. 业务概述" in content
    assert "## 7. 关联过程性内容索引" in content
    assert "related_reqs: []" in content
    # 幂等：再次创建返回 created=False 且不生成新文件
    res2 = client.post("/api/v1/knowledge/main-note", json={"domain_code": "ftto"})
    assert res2.status_code == 200
    assert res2.json()["data"]["created"] is False
    assert res2.json()["data"]["item"]["id"] == item["id"]


def test_item_link_crud(client, vault_tmp):
    _create_domain(client)
    res = client.post("/api/v1/knowledge/main-note", json={"domain_code": "ftto"})
    item_id = res.json()["data"]["item"]["id"]
    obs_path = res.json()["data"]["item"]["obsidian_path"]

    # 建立关联
    r = client.post(
        f"/api/v1/knowledge/{item_id}/links",
        json={"source_type": "requirement", "source_id": "REQ-TEST-001", "link_type": "main", "note": "测试关联"},
    )
    assert r.status_code == 200, r.text
    link = r.json()["data"]
    assert link["link_id"] > 0
    assert link["source_id"] == "REQ-TEST-001"

    # 幂等重复建立
    r2 = client.post(
        f"/api/v1/knowledge/{item_id}/links",
        json={"source_type": "requirement", "source_id": "REQ-TEST-001", "link_type": "main"},
    )
    assert r2.status_code == 200
    assert r2.json()["data"]["link_id"] == link["link_id"]

    # 查询关联
    g = client.get(f"/api/v1/knowledge/{item_id}/links")
    assert g.status_code == 200
    items = g.json()["data"]
    assert len(items) == 1
    assert items[0]["source_id"] == "REQ-TEST-001"

    # frontmatter related_reqs 数组已同步
    content = open(os.path.join(str(vault_tmp), obs_path), encoding="utf-8").read()
    assert "related_reqs: [REQ-TEST-001]" in content

    # 移除关联
    d = client.delete(f"/api/v1/knowledge/{item_id}/links/requirement/REQ-TEST-001")
    assert d.status_code == 200, d.text
    assert d.json()["data"] is True

    # 查询为空
    g2 = client.get(f"/api/v1/knowledge/{item_id}/links")
    assert g2.status_code == 200
    assert g2.json()["data"] == []

    # frontmatter 已清理
    content2 = open(os.path.join(str(vault_tmp), obs_path), encoding="utf-8").read()
    assert "related_reqs: []" in content2


def test_item_link_batch(client, vault_tmp):
    _create_domain(client)
    res = client.post("/api/v1/knowledge/main-note", json={"domain_code": "ftto"})
    item_id = res.json()["data"]["item"]["id"]

    r = client.post(
        f"/api/v1/knowledge/{item_id}/links/batch",
        json={
            "links": [
                {"source_type": "requirement", "source_id": "REQ-A"},
                {"source_type": "operation", "source_id": "OP-B", "link_type": "sub"},
                {"source_type": "meeting", "source_id": "MEET-C"},
            ]
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert len(data) == 3

    g = client.get(f"/api/v1/knowledge/{item_id}/links")
    assert len(g.json()["data"]) == 3
    sources = sorted(x["source_id"] for x in g.json()["data"])
    assert sources == ["MEET-C", "OP-B", "REQ-A"]


def test_list_by_source(client, vault_tmp):
    """同一需求可关联多条知识笔记（多对多）。"""
    _create_domain(client)
    res1 = client.post("/api/v1/knowledge/main-note", json={"domain_code": "ftto"})
    item1 = res1.json()["data"]["item"]["id"]
    # 第二领域（另一条主笔记）也关联同一需求
    _create_domain(client, code="fttb", name="FTTB")
    res2 = client.post("/api/v1/knowledge/main-note", json={"domain_code": "fttb"})
    item2 = res2.json()["data"]["item"]["id"]

    for iid in (item1, item2):
        client.post(
            f"/api/v1/knowledge/{iid}/links",
            json={"source_type": "requirement", "source_id": "REQ-SHARED"},
        )
    # 按来源查
    r = client.get("/api/v1/knowledge/links", params={"source_type": "requirement", "source_id": "REQ-SHARED"})
    assert r.status_code == 200, r.text
    assert len(r.json()["data"]) == 2
