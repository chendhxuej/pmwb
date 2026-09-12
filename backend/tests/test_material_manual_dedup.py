# -*- coding: utf-8 -*-
"""业务资料库：操作手册去重 + 自动归类（老大 2026-09-11 反馈）。

验收点：
1. req_manual 来源自动归到「操作手册」分类（新建时带分类，已存在且未分类时补齐，人工设过的不覆盖）；
2. 同一文件既登记成「需求交付物」又登记成「需求操作手册」时，purge 掉交付物那条；
3. 需求 deliverables 里历史兼容条目「操作手册-{系统}」不再登记成材料；
4. upload_manual 只在 PmwbReqManual 落一份，不再往 deliverables 写兼容条目。
"""
import json
import os

import pytest

from core.config import settings
from db.models import (
    PmwbMaterial,
    PmwbMaterialCategory,
    PmwbReqManual,
    PmwbRequirementExt,
)
from services import material_sync
from utils import file_storage as fs


@pytest.fixture
def vault_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    return tmp_path


def _req(db, req_id="REQ-M1", status="dev"):
    r = PmwbRequirementExt(
        req_id=req_id,
        status=status,
        req_name="操作手册测试需求",
        system_name="CRM",
        deliverables="[]",
    )
    db.add(r)
    db.commit()
    return r


# ------------------------------------------------------------------ 1. 自动归类
def test_req_manual_auto_category_on_create(db):
    material_sync._upsert(
        db,
        source_type="req_manual",
        source_id="1",
        source_no="REQ-1",
        storage_root="vault",
        rel_path="a/操作手册.docx",
        file_name="操作手册.docx",
        file_size=100,
    )
    db.commit()
    m = db.query(PmwbMaterial).filter(PmwbMaterial.source_type == "req_manual").one()
    cat = db.query(PmwbMaterialCategory).filter(
        PmwbMaterialCategory.id == m.category_id
    ).first()
    assert cat is not None
    assert cat.name == "操作手册"


def test_existing_uncategorized_gets_filled_but_manual_kept(db):
    other = PmwbMaterialCategory(code="other", name="我手工分的类")
    db.add(other)
    db.commit()

    # 未分类 -> 补「操作手册」
    db.add(
        PmwbMaterial(
            source_type="req_manual",
            source_id="1",
            file_name="m1.docx",
            stored_name="m1.docx",
            storage_root="vault",
            rel_path="a/m1.docx",
            rel_path_hash=fs.path_hash("a/m1.docx"),
        )
    )
    # 已人工分类 -> 不覆盖
    db.add(
        PmwbMaterial(
            source_type="req_manual",
            source_id="2",
            file_name="m2.docx",
            stored_name="m2.docx",
            storage_root="vault",
            rel_path="a/m2.docx",
            rel_path_hash=fs.path_hash("a/m2.docx"),
            category_id=other.id,
        )
    )
    db.commit()

    for sid, rel in (("1", "a/m1.docx"), ("2", "a/m2.docx")):
        material_sync._upsert(
            db,
            source_type="req_manual",
            source_id=sid,
            storage_root="vault",
            rel_path=rel,
            file_name=f"m{sid}.docx",
        )
    db.commit()

    m1 = db.query(PmwbMaterial).filter(PmwbMaterial.source_id == "1").one()
    m2 = db.query(PmwbMaterial).filter(PmwbMaterial.source_id == "2").one()
    cz = db.query(PmwbMaterialCategory).filter(
        PmwbMaterialCategory.name == "操作手册"
    ).first()
    assert m1.category_id == cz.id
    assert m2.category_id == other.id


# ------------------------------------------------------------------ 2. 去重清理
def test_purge_manual_duplicates(db):
    rel = "a/操作手册.docx"
    db.add(
        PmwbMaterial(
            source_type="req_manual",
            source_id="11",
            file_name="操作手册.docx",
            stored_name="操作手册.docx",
            storage_root="vault",
            rel_path=rel,
            rel_path_hash="hm",
        )
    )
    db.add(
        PmwbMaterial(
            source_type="requirement",
            source_id="REQ-1",
            file_name="操作手册.docx",
            stored_name="操作手册.docx",
            storage_root="vault",
            rel_path=rel,
            rel_path_hash="hr",
        )
    )
    db.commit()

    assert material_sync.purge_manual_duplicates(db) == 1
    left = db.query(PmwbMaterial).all()
    assert len(left) == 1
    assert left[0].source_type == "req_manual"


# ------------------------------------------------- 3. 交付物里的手册兼容条目跳过
def test_sync_requirement_skips_manual_compat_entry(db, vault_tmp):
    rel = "业务建设/x/操作手册/CRM_操作手册.docx"
    fp = os.path.join(str(vault_tmp), rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "wb") as f:
        f.write(b"x")

    ext = _req(db)
    ext.deliverables = json.dumps(
        [
            {"file_name": "操作手册.docx", "local_path": rel, "note": "操作手册-CRM"},
            {"file_name": "需求说明书.docx", "local_path": rel, "note": "需求文档"},
        ],
        ensure_ascii=False,
    )
    db.commit()

    stat = material_sync._sync_requirement(db)
    db.commit()

    rows = db.query(PmwbMaterial).filter(PmwbMaterial.source_type == "requirement").all()
    assert len(rows) == 1
    assert rows[0].file_name == "需求说明书.docx"
    assert any("操作手册" in w for w in stat["warn"])


# ------------------------------------------------- 4. 上传手册只落一份
def test_upload_manual_writes_single_source(db, vault_tmp):
    from services.requirement_stage import upload_manual

    _req(db, status="dev")
    upload_manual(
        db,
        "REQ-M1",
        "CRM",
        "操作手册.docx",
        b"dummy",
        note="",
        uploaded_by="陈大海",
    )

    # 手册表一份
    assert db.query(PmwbReqManual).filter(PmwbReqManual.req_id == "REQ-M1").count() == 1
    # deliverables 不再写兼容条目
    from services.obsidian_link import get_requirement_deliverables

    assert get_requirement_deliverables(db, "REQ-M1") == []

    # 汇聚后只有一条「需求操作手册」
    material_sync.sync_all(db)
    rows = db.query(PmwbMaterial).all()
    assert len(rows) == 1
    assert rows[0].source_type == "req_manual"
