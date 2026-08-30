"""T6 主笔记生成端点 — 测试（TDD 红→绿）。

验证 KnowledgeView「新建主笔记」所依赖的后端链路：
1. create_main_note_service 对全新领域生成标准模板文件 + 建知识索引（created=True）
2. 幂等：重复调用返回 created=False，不重复建索引
3. 主笔记文件真实写入 vault（OBSIDIAN_VAULT_PATH 被 vault_tmp 重定向）
"""
import pytest

from db.models import PmwbBusinessDomain, PmwbKnowledgeItem
from services import knowledge_link_service as kls
from services import obsidian_paths as op
from utils.obsidian import write_markdown, read_markdown


@pytest.fixture
def vault_tmp(monkeypatch, tmp_path):
    from core.config import settings
    monkeypatch.setattr(settings, "OBSIDIAN_VAULT_PATH", str(tmp_path / "vault"))
    return tmp_path / "vault"


def _seed_domain(db, code, name, group):
    db.add(PmwbBusinessDomain(domain_code=code, domain_name=name, domain_group=group, enabled=True))
    db.commit()


def test_create_main_note_new(db, vault_tmp):
    _seed_domain(db, "ywt", "一网通宽带", "商客业务")
    res = kls.create_main_note(db, "ywt")
    assert res["created"] is True
    item = res["item"]
    assert item["domain_code"] == "ywt"
    assert item["note_type"] == "main"
    # 文件真实落盘
    rel = item["obsidian_path"]
    assert (vault_tmp / rel).exists(), f"主笔记文件未写入 vault: {rel}"
    body = read_markdown(rel)
    assert "业务概述" in body or "业务知识主笔记" in body


def test_create_main_note_idempotent(db, vault_tmp):
    _seed_domain(db, "ywt", "一网通宽带", "商客业务")
    first = kls.create_main_note(db, "ywt")
    assert first["created"] is True
    second = kls.create_main_note(db, "ywt")
    assert second["created"] is False
    # 索引唯一
    cnt = (
        db.query(PmwbKnowledgeItem)
        .filter(PmwbKnowledgeItem.domain_code == "ywt")
        .filter(PmwbKnowledgeItem.note_type == "main")
        .count()
    )
    assert cnt == 1


def test_create_main_note_unknown_domain_raises(db, vault_tmp):
    from core.exceptions import NotFoundException
    with pytest.raises(NotFoundException):
        kls.create_main_note(db, "nope")
