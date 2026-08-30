"""T4 主笔记结构标准化 — 测试（TDD 红→绿）。

验证：
1. get_main_note_structured 按 domain_group 选三类模板（business/platform/capability）
2. 编号匹配（带点编号 2.1）正确，build→parse 往返一致，每章节命中（非"暂无数据"）
3. §10 关联系统与接口在新笔记中存在且可被解析
4. 平台/能力模板与业务模板章节数不同，互不串用
"""
import pytest

from db.models import PmwbBusinessDomain, PmwbKnowledgeItem
from services import knowledge_link_service as kls
from services import obsidian_paths as op
from utils.obsidian import write_markdown


@pytest.fixture
def vault_tmp(monkeypatch, tmp_path):
    from core.config import settings
    monkeypatch.setattr(settings, "OBSIDIAN_VAULT_PATH", str(tmp_path / "vault"))
    return tmp_path / "vault"


def _seed(db, code, name, group):
    db.add(PmwbBusinessDomain(domain_code=code, domain_name=name, domain_group=group))
    db.commit()
    content = op.build_main_note_skeleton(name, group)
    rel = op.main_note_rel_path(name, group)
    write_markdown(rel, content)
    db.add(PmwbKnowledgeItem(
        item_id=f"kn-{code}", title=f"{name} 业务知识主笔记", category="product",
        obsidian_path=rel, source_type="manual", domain_code=code, note_type="main",
    ))
    db.commit()
    return rel


def test_structured_business_roundtrip(db, vault_tmp):
    _seed(db, "ywt", "一网通宽带", "商客业务")
    res = kls.get_main_note_structured(db, "ywt")
    assert res["sections"], "业务模板应至少含 §1-§10"
    for sec in res["sections"]:
        assert sec["markdown"] != "_暂无数据_", f"业务章节 {sec['key']} 解析失败"
    # §10 命中
    s10 = [s for s in res["sections"] if s["key"] == "10"]
    assert s10 and "关联系统与接口" in s10[0]["title"]


def test_structured_platform_distinct(db, vault_tmp):
    _seed(db, "ddzx", "订单中心", "系统平台")
    res = kls.get_main_note_structured(db, "ddzx")
    titles = [s["title"] for s in res["sections"]]
    assert any("平台概述" in t for t in titles)
    assert any("关联系统集成" in t for t in titles)  # 平台 §10 文案不同


def test_structured_capability_distinct(db, vault_tmp):
    _seed(db, "cjxs", "场景化销售", "公共能力")
    res = kls.get_main_note_structured(db, "cjxs")
    titles = [s["title"] for s in res["sections"]]
    assert any("能力介绍" in t for t in titles)
    assert any("快速建档与标签" in t for t in titles)
    # 公共能力无 §10（关联系统），章节数应少于业务套
    assert len(res["sections"]) < 14


def test_section_kind_label_consistent(db, vault_tmp):
    _seed(db, "ywt", "一网通宽带", "商客业务")
    res = kls.get_main_note_structured(db, "ywt")
    kinds = {s["kind"] for s in res["sections"]}
    assert kinds <= {"baseline", "auto", "system"}
    assert all(s["kind_label"] for s in res["sections"])
