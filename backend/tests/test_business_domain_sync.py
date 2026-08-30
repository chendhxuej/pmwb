"""T3 领域同步创建 — 测试（TDD 红→绿）。

覆盖：
1. create 写 DB 后同步建 vault 目录树 + 主笔记，并回写 vault_path
2. 主笔记已存在不覆盖（幂等）
3. update 改名/改组时原子重命名 vault 目录 + 主笔记，回写 vault_path
4. create_note 页面化建子笔记并登记 pmwb_knowledge_item
5. vault 不可达时 create 不致命（DB 仍建）
"""
import pytest

from core.config import settings
from db.models import PmwbKnowledgeItem
from pathlib import Path
from schemas.business_domain import BusinessDomainCreate, BusinessDomainUpdate
from services import business_domain as bd
from services import obsidian_paths as op


@pytest.fixture
def vault_tmp(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "OBSIDIAN_VAULT_PATH", str(tmp_path / "vault"))
    return tmp_path / "vault"


def _new(code, name, group="商客业务", vault_path=None):
    return BusinessDomainCreate(
        domain_code=code, domain_name=name, domain_group=group,
        vault_path=vault_path, match_keywords=None, parent_domain_code=None,
        description=None, sort_order=0, enabled=True,
    )


def test_create_sync_builds_vault(db, vault_tmp):
    out = bd.create(db, _new("ywt", "一网通宽带", "商客业务"))
    # vault_path 被回写
    assert out.vault_path == "01-业务知识/商客业务/一网通宽带"
    # 目录树 + 子目录 + 主笔记存在
    root = Path(settings.OBSIDIAN_VAULT_PATH) / "01-业务知识/商客业务/一网通宽带"
    assert root.is_dir()
    for sub in op.DOMAIN_SUBDIRS:
        assert (root / sub).is_dir()
    note = root / op.main_note_filename("一网通宽带")
    assert note.exists()
    txt = note.read_text(encoding="utf-8")
    assert "## 1" in txt
    assert "group: 商客业务" in txt


def test_create_idempotent_main_note(db, vault_tmp):
    bd.create(db, _new("ftto", "FTTO", "商客业务"))
    root = Path(settings.OBSIDIAN_VAULT_PATH) / "01-业务知识/商客业务/FTTO"
    note = root / op.main_note_filename("FTTO")
    note.write_text("# 人工改写标记\n人工补充内容", encoding="utf-8")
    # 二次 ensure 不应覆盖人工内容
    op.ensure_domain_dir(db, "ftto")
    assert "人工改写标记" in note.read_text(encoding="utf-8")


def test_update_rename_sync(db, vault_tmp):
    bd.create(db, _new("dd1", "订单中心旧", "商客业务"))
    old_root = Path(settings.OBSIDIAN_VAULT_PATH) / "01-业务知识/商客业务/订单中心旧"
    assert old_root.is_dir()
    out = bd.update(db, "dd1", BusinessDomainUpdate(domain_name="订单中心", domain_group="系统平台"))
    assert out.vault_path == "01-业务知识/系统平台/订单中心"
    new_root = Path(settings.OBSIDIAN_VAULT_PATH) / "01-业务知识/系统平台/订单中心"
    assert new_root.is_dir()
    assert not old_root.exists()
    note = new_root / op.main_note_filename("订单中心")
    assert note.exists()
    assert "group: 系统平台" in note.read_text(encoding="utf-8")


def test_create_note_registers_item(db, vault_tmp):
    bd.create(db, _new("cn1", "场景化销售", "公共能力"))
    item = bd.create_note(db, "cn1", "操作手册示例", note_type="sub", category="operation")
    assert item.domain_code == "cn1"
    assert item.source_type == "manual"
    root = Path(settings.OBSIDIAN_VAULT_PATH) / "01-业务知识/公共能力/场景化销售"
    assert (Path(settings.OBSIDIAN_VAULT_PATH) / item.obsidian_path) == root / "操作手册示例.md"
    assert (root / "操作手册示例.md").exists()
    assert db.query(PmwbKnowledgeItem).filter(PmwbKnowledgeItem.domain_code == "cn1").count() == 1


def test_create_vault_unreachable_not_fatal(db, monkeypatch):
    monkeypatch.setattr(settings, "OBSIDIAN_VAULT_PATH", "Z:\\__no_such_vault__xyz")
    out = bd.create(db, _new("ur1", "不可达域", "商客业务"))
    assert out.domain_code == "ur1"
    assert out.vault_path == "01-业务知识/商客业务/不可达域"
    assert db.query(PmwbKnowledgeItem).count() == 0
