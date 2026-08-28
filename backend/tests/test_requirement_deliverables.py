# -*- coding: utf-8 -*-
"""kc4-4 需求交付物去开发工单测试。

核心验收（对应 .workbuddy/tasks/kc4-4.md）：
- 需求直挂交付物 CRUD（上传/列举/删除）；
- 归档后 deliverables JSON 中 archived_at 被回写；
- 旧 dev_ticket 数据仍在，不报错；
- 空需求返回空列表不报错。
"""
import json
import os
from datetime import date

import pytest

from core.config import settings
from db.models import PmwbBusinessDomain, PmwbKnowledgeItem, PmwbRequirementExt
from services.obsidian_link import (
    archive_requirement_manual,
    get_requirement_deliverables,
    add_requirement_deliverable,
    remove_requirement_deliverable,
)


@pytest.fixture
def vault_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    return tmp_path


def _create_domain(db, code="ftto", name="FTTO"):
    db.add(
        PmwbBusinessDomain(
            domain_code=code,
            domain_name=name,
            domain_group="政企",
            vault_path=f"01-业务知识/政企/{name}",
            enabled=1,
        )
    )
    db.commit()


def _req(db, req_id="REQ-D4", status="closed"):
    req = PmwbRequirementExt(
        req_id=req_id,
        status=status,
        domain_code="ftto",
        req_name="交付物测试需求",
        description="kc4-4 测试",
        system_name="CRM",
        deliverables="[]",
    )
    db.add(req)
    db.commit()
    return req


def _main_note(db, code="ftto", vault_tmp=None):
    obsidian_path = f"01-业务知识/政企/{code.upper()}/{code.upper()}.md"
    item = PmwbKnowledgeItem(
        item_id=f"KNOW-D4-{code}",
        title=code.upper(),
        category="业务知识",
        domain_code=code,
        note_type="main",
        obsidian_path=obsidian_path,
    )
    db.add(item)
    db.commit()
    if vault_tmp:
        # 创建最小主笔记模板，包含自动区标记，便于 sync_main_note_from_links 写入
        full_path = os.path.join(str(vault_tmp), obsidian_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        content = f"""---
title: {code.upper()} 业务知识主笔记
tags: [业务知识, 政企, {code.upper()}, 主笔记]
related_sub_notes: []
related_reqs: []
related_tickets: []
related_meetings: []
related_issues: []
related_deliverables: []
---

## 6. 关联交付物（自动区）

<!-- PMWB:AUTO:BEGIN key=deliverables -->
<!-- PMWB:AUTO:END key=deliverables -->
"""
        print("DEBUG _main_note writing to", full_path)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("DEBUG _main_note exists after write", os.path.exists(full_path))
    return item


def test_empty_deliverables(db):
    """新需求默认空列表。"""
    _create_domain(db)
    r = _req(db)
    items = get_requirement_deliverables(db, "REQ-D4")
    assert items == []


def test_add_and_list(db, vault_tmp):
    """添加交付物后可列举。"""
    _create_domain(db)
    _req(db)

    entry = add_requirement_deliverable(
        db, "REQ-D4", file_name="操作手册.pdf", local_path="uploads/test.pdf", note="上线操作手册"
    )
    assert entry["file_name"] == "操作手册.pdf"
    assert entry["archived_at"] is None

    items = get_requirement_deliverables(db, "REQ-D4")
    assert len(items) == 1
    assert items[0]["file_name"] == "操作手册.pdf"


def test_remove_by_index(db):
    """按索引删除。"""
    _create_domain(db)
    _req(db)
    add_requirement_deliverable(db, "REQ-D4", file_name="a.pdf", local_path="/a.pdf")
    add_requirement_deliverable(db, "REQ-D4", file_name="b.docx", local_path="/b.docx")

    ok = remove_requirement_deliverable(db, "REQ-D4", 0)
    assert ok is True
    items = get_requirement_deliverables(db, "REQ-D4")
    assert len(items) == 1
    assert items[0]["file_name"] == "b.docx"

    # 索引越界
    assert remove_requirement_deliverable(db, "REQ-D4", 99) is False


def test_archive_writes_back_archived_at(db, vault_tmp):
    """归档后 deliverables JSON 的 archived_at 被回写，文件复制到 06-交付物/。"""
    _create_domain(db)
    _req(db)
    _main_note(db, vault_tmp=vault_tmp)

    # 创建一个假文件在 uploads/
    fake_file = os.path.join(str(vault_tmp), "uploads", "manual.pdf")
    os.makedirs(os.path.dirname(fake_file), exist_ok=True)
    with open(fake_file, 'w') as f:
        f.write("fake manual content")

    add_requirement_deliverable(
        db, "REQ-D4", file_name="manual.pdf", local_path="uploads/manual.pdf", note="操作手册"
    )

    result = archive_requirement_manual(db, "REQ-D4")
    assert result["archived"]
    assert len(result["archived"]) == 1
    assert result["archived"][0]["obsidian_path"].endswith("manual.pdf")

    # 文件确实复制到了 06-交付物/
    dst = os.path.join(str(vault_tmp), result["archived"][0]["obsidian_path"])
    assert os.path.exists(dst)

    # archived_at 已回写到 deliverables JSON
    ext = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == "REQ-D4").first()
    items = json.loads(ext.deliverables or "[]")
    assert len(items) == 1
    assert items[0]["archived_at"] is not None
    assert items[0]["obsidian_path"] == result["archived"][0]["obsidian_path"]


def test_archive_no_domain_raises(db):
    """无 domain_code 的需求归档报错。"""
    req = PmwbRequirementExt(req_id="REQ-NODOMAIN", status="closed", deliverables="[]")
    db.add(req)
    db.commit()

    from core.exceptions import NotFoundException
    with pytest.raises(NotFoundException):
        archive_requirement_manual(db, "REQ-NODOMAIN")


def test_endpoint_crud(client, db, vault_tmp):
    """REST API 端点可用：GET/POST/DELETE /deliverables。"""
    _create_domain(db)
    _req(db)

    # 列举（空）
    res = client.get("/api/v1/requirements/REQ-D4/deliverables")
    assert res.status_code == 200
    assert res.json()["data"] == []

    # 添加
    res = client.post(
        "/api/v1/requirements/REQ-D4/deliverables",
        json={"file_name": "test.pdf", "local_path": "uploads/test.pdf", "note": "测试"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["file_name"] == "test.pdf"

    # 再次列举
    res = client.get("/api/v1/requirements/REQ-D4/deliverables")
    assert res.status_code == 200
    assert len(res.json()["data"]) == 1

    # 删除
    res = client.delete("/api/v1/requirements/REQ-D4/deliverables/0")
    assert res.status_code == 200
    assert res.json()["data"]["deleted"] is True

    # 确认已删
    res = client.get("/api/v1/requirements/REQ-D4/deliverables")
    assert len(res.json()["data"]) == 0


def test_upload_requirement_manual_service_accepted_stages_only(db, vault_tmp):
    """upload_requirement_manual 仅允许 accepted/dev/closed 三阶段上传，proposed 拒绝。"""
    _create_domain(db)
    _req(db, status="proposed")
    from services.requirement_delivery import upload_requirement_manual
    from core.exceptions import ValidationException
    with pytest.raises(ValidationException):
        upload_requirement_manual(db, "REQ-D4", "manual.pdf", b"content")


def test_upload_requirement_manual_service_no_domain(db, vault_tmp):
    """未设置 domain_code 的需求上传操作手册报错。"""
    req = PmwbRequirementExt(req_id="REQ-NODOMAIN", status="closed", deliverables="[]")
    db.add(req)
    db.commit()
    from services.requirement_delivery import upload_requirement_manual
    from core.exceptions import ValidationException
    with pytest.raises(ValidationException):
        upload_requirement_manual(db, "REQ-NODOMAIN", "manual.pdf", b"content")


def test_upload_requirement_manual_service_ok(db, vault_tmp):
    """正常上传操作手册：文件落盘、归档、deliverables 回写 obsidian_path。"""
    _create_domain(db)
    _req(db)
    _main_note(db, vault_tmp=vault_tmp)

    from services.requirement_delivery import upload_requirement_manual
    from services.knowledge_link_service import sync_main_note_from_links
    from utils.obsidian import read_markdown
    result = upload_requirement_manual(db, "REQ-D4", "manual.pdf", b"manual content", note="上线操作手册")
    print("DEBUG main_note_path", result.get("main_note"))
    print("DEBUG main_note_synced", result["main_note_synced"])

    ext_after = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == "REQ-D4").first()
    print("DEBUG ext deliverables", ext_after.deliverables)

    full = os.path.join(str(vault_tmp), "01-业务知识/政企/FTTO/FTTO.md")
    print("DEBUG full path", full)
    print("DEBUG dir exists", os.path.isdir(os.path.dirname(full)))
    if os.path.isdir(os.path.dirname(full)):
        print("DEBUG dir list", os.listdir(os.path.dirname(full)))

    from db.models import PmwbKnowledgeItem
    item = db.query(PmwbKnowledgeItem).filter(PmwbKnowledgeItem.domain_code == "ftto", PmwbKnowledgeItem.note_type == "main").first()
    print("DEBUG item path", item.obsidian_path if item else None)
    print("DEBUG file exists", os.path.exists(os.path.join(str(vault_tmp), item.obsidian_path)) if item else False)
    print("DEBUG content preview", (read_markdown(item.obsidian_path) or "")[:200] if item else "")
    sync_result = sync_main_note_from_links(db, "ftto")
    print("DEBUG sync changed", sync_result.get("changed"))

    assert result["req_id"] == "REQ-D4"
    assert result["file_name"] == "manual.pdf"
    assert result["archived"] is True
    assert result["obsidian_path"].endswith("manual.pdf")
    assert result["main_note_synced"] is True

    dst = os.path.join(str(vault_tmp), result["obsidian_path"])
    assert os.path.exists(dst)

    ext = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == "REQ-D4").first()
    items = json.loads(ext.deliverables or "[]")
    assert len(items) == 1
    assert items[0]["obsidian_path"] == result["obsidian_path"]


def test_upload_manual_endpoint(client, db, vault_tmp):
    """POST /requirements/{req_id}/delivery/upload-manual 端点上传文件。"""
    _create_domain(db)
    _req(db)
    _main_note(db, vault_tmp=vault_tmp)

    from io import BytesIO
    res = client.post(
        "/api/v1/requirements/REQ-D4/delivery/upload-manual",
        files={"file": ("manual.pdf", BytesIO(b"manual content"), "application/pdf")},
        data={"note": "上线操作手册"},
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["req_id"] == "REQ-D4"
    assert data["file_name"] == "manual.pdf"
    assert data["archived"] is True
    assert data["obsidian_path"].endswith("manual.pdf")
    assert data["main_note_synced"] is True
