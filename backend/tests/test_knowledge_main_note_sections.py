"""kc-4 T8：主笔记 §10 落盘 + 结构清理逻辑测试。"""
import types

from db.models import PmwbBusinessDomain, PmwbKnowledgeItem
from services import knowledge_link_service as kls


def _domain(name, code, group):
    return types.SimpleNamespace(domain_name=name, domain_code=code, domain_group=group)


def test_build_main_note_markdown_has_section10_business():
    md = kls.build_main_note_markdown(_domain("一网通宽带", "ywt", "business"), "ID1", "2026-08-30")
    assert "## 9. 业务全过程时间线（自动区）" in md
    assert "## 10. 关联系统与接口" in md
    assert md.index("## 10. 关联系统与接口") > md.index("## 9.")


def test_build_main_note_markdown_section10_platform_title():
    md = kls.build_main_note_markdown(_domain("政企工作台", "wj", "platform"), "ID2", "2026-08-30")
    assert "## 10. 关联系统集成（上下游系统对接）" in md


def test_build_main_note_markdown_no_section10_for_capability():
    md = kls.build_main_note_markdown(_domain("一键订购", "yj", "capability"), "ID3", "2026-08-30")
    assert "## 10." not in md


def test_strip_bases_metadata_removes_page_line():
    content = "# 电子协议 业务知识主笔记\n\n## page: 平台概述 | category: 首页\n\n## 1. 平台概述\n\nhello\n"
    out = kls.strip_bases_metadata(content)
    assert "## page:" not in out
    assert "## 1. 平台概述" in out
    assert "hello" in out


def test_dedup_duplicate_sections_removes_trailing_dup():
    content = (
        "## 1. A\n\nbody1\n\n"
        "## 7. 关联过程性内容索引\n\nlinks\n\n"
        "## 7. 关联过程性内容索引\n\nDUP\n"
    )
    out = kls.dedup_duplicate_sections(content)
    assert out.count("## 7. 关联过程性内容索引") == 1
    assert "DUP" not in out
    assert "body1" in out


def test_cleanup_duplicate_main_notes(db):
    db.add(PmwbBusinessDomain(domain_code="dup", domain_name="重复域", domain_group="business", enabled=True))
    db.commit()
    db.add(PmwbKnowledgeItem(
        item_id="K1", title="重复域 业务知识主笔记", domain_code="dup", note_type="main",
        category="product",
        obsidian_path="01-业务知识/business/重复域/重复域 业务知识主笔记.md",
    ))
    db.add(PmwbKnowledgeItem(
        item_id="K2", title="重复域 业务知识主笔记", domain_code="dup", note_type="main",
        category="product",
        obsidian_path="01-业务知识/business/重复域/重复域 业务知识主笔记-2.md",
    ))
    db.commit()
    res = kls.cleanup_duplicate_main_notes(db)
    assert res["domains_with_dups"] == 1
    assert res["notes_relabeled"] == 1
    assert db.query(PmwbKnowledgeItem).filter(
        PmwbKnowledgeItem.domain_code == "dup", PmwbKnowledgeItem.note_type == "main"
    ).count() == 1
    assert db.query(PmwbKnowledgeItem).filter(
        PmwbKnowledgeItem.domain_code == "dup", PmwbKnowledgeItem.note_type == "main_dup"
    ).count() == 1
    # 幂等
    res2 = kls.cleanup_duplicate_main_notes(db)
    assert res2["notes_relabeled"] == 0
