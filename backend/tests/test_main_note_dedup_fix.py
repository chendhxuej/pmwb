"""回归：主笔记重复章节/AUTO 块根治（方案A 单一真相源）。

覆盖：
1. 新建领域（骨架已由 ensure_domain_dir 落盘）后调 create_main_note → 覆盖为单模板，无重复块；
2. normalize_main_note_content 对已被叠加污染的正文去重（保留人工内容）；
3. dedup_auto_blocks 同 key 多块（空+非空）只保留内容最丰富的一块；
4. ensure_frontmatter 补回丢失的 YAML 头，幂等。
"""
import re

import pytest

from db.models import PmwbBusinessDomain
from services import knowledge_link_service as kls
from services import obsidian_paths as op
from utils.obsidian import read_markdown


@pytest.fixture
def vault_tmp(monkeypatch, tmp_path):
    from core.config import settings
    monkeypatch.setattr(settings, "OBSIDIAN_VAULT_PATH", str(tmp_path / "vault"))
    return tmp_path / "vault"


def _seed_domain(db, code="jtqly", name="集团千里眼业务", group="商客业务"):
    db.add(PmwbBusinessDomain(domain_code=code, domain_name=name, domain_group=group, enabled=True))
    db.commit()


def test_create_main_note_overwrites_pure_skeleton(db, vault_tmp):
    """建领域生成 A 骨架后调 create_main_note，不应叠加成双模板。"""
    _seed_domain(db)
    # 模拟 business_domain.create 链路：先落 A 骨架
    op.ensure_domain_dir(db, "jtqly")
    rel = op.main_note_rel_path("集团千里眼业务", "商客业务")
    before = read_markdown(rel)
    assert before and "自动生成骨架" in before

    res = kls.create_main_note(db, "jtqly")
    assert res["created"] is True
    after = read_markdown(rel)
    assert after and after.lstrip().startswith("---"), "标准模板 frontmatter 缺失"
    for key in ("product", "process", "scenario_rules", "change_log", "deliverables", "timeline"):
        cnt = len(re.findall(rf"PMWB:AUTO:BEGIN key={key}\b", after))
        assert cnt == 1, f"AUTO 块 {key} 出现 {cnt} 次（应为 1）"
    assert "自动生成骨架" not in after, "A 骨架残留，发生双模板叠加"
    # 幂等：再建一次不重复
    kls.create_main_note(db, "jtqly")
    assert read_markdown(rel) == after


def test_normalize_preserves_user_content_and_dedups(db):
    """已污染文件：重复章节 + 双 AUTO 块 → 去重且保留人工正文。"""
    polluted = (
        "## 1. 业务概述\n人工填写的定义\n\n"
        "<!-- PMWB:AUTO:BEGIN key=product -->\n_暂无数据_\n<!-- PMWB:AUTO:END key=product -->\n\n"
        "<!-- PMWB:AUTO:BEGIN key=product -->\n真实产品变更\n<!-- PMWB:AUTO:END key=product -->\n\n"
        "## 7. 关联过程性内容索引\nlink-A\n\n"
        "## 7. 关联过程性内容索引\nlink-DUP\n"
    )
    out = kls.normalize_main_note_content(polluted)
    assert out.count("## 7. 关联过程性内容索引") == 1
    assert "link-DUP" not in out
    assert "link-A" in out
    assert "人工填写的定义" in out, "人工内容被误删"
    assert out.count("PMWB:AUTO:BEGIN key=product") == 1
    assert "真实产品变更" in out, "未保留非空 AUTO 内容"
    # 幂等
    assert kls.normalize_main_note_content(out) == out


def test_build_markdown_section10_chinese_group():
    """DB 存中文 domain_group 时 §10 必须存在（本次回归点）。"""
    import types
    biz = kls.build_main_note_markdown(types.SimpleNamespace(domain_code="ywt", domain_name="一网通宽带", domain_group="商客业务"), "ID1", "2026-11-26")
    assert "## 10. 关联系统与接口" in biz
    plat = kls.build_main_note_markdown(types.SimpleNamespace(domain_code="wj", domain_name="政企工作台", domain_group="系统平台"), "ID2", "2026-11-26")
    assert "## 10. 关联系统集成（上下游系统对接）" in plat
    cap = kls.build_main_note_markdown(types.SimpleNamespace(domain_code="yj", domain_name="一键订购", domain_group="公共能力"), "ID3", "2026-11-26")
    assert "## 10." not in cap


def test_dedup_keeps_filled_auto_in_duplicate_section():
    """重复 H2 段内的非空 AUTO 块内容不得丢失（审查 #1 回归点）。"""
    polluted = (
        "## 5. 优化与变更轨迹（自动区）\n"
        "<!-- PMWB:AUTO:BEGIN key=change_log -->\n<!-- PMWB:AUTO:END key=change_log -->\n\n"
        "## 6. 关联交付物（自动区）\n\n"
        "## 5. 优化与变更轨迹（自动区）\n"
        "<!-- PMWB:AUTO:BEGIN key=change_log -->\n真实回填内容XYZ\n<!-- PMWB:AUTO:END key=change_log -->\n"
    )
    out = kls.normalize_main_note_content(polluted)
    assert out.count("PMWB:AUTO:BEGIN key=change_log") == 1, "AUTO 块未唯一"
    assert "真实回填内容XYZ" in out, "同步回填内容被误删"
    assert out.count("## 5. 优化与变更轨迹（自动区）") == 1


def test_ensure_frontmatter_fills_partial(db):
    import types
    domain = types.SimpleNamespace(domain_code="jtqly", domain_name="集团千里眼业务", domain_group="商客业务")
    # 无 frontmatter：新建
    body = "# 集团千里眼业务 业务知识主笔记\n\n## 1. 业务概述\n内容\n"
    out = kls.ensure_frontmatter(body, domain, "K-1", "2026-11-26")
    assert out.startswith("---")
    assert "domain_code: jtqly" in out
    assert "## 1. 业务概述" in out
    assert kls.ensure_frontmatter(out, domain, "K-1", "2026-11-26") == out
    # 残缺 frontmatter（有 --- 但缺 item_id）：补齐
    partial = "---\ntitle: 测试\n---\n\n# 正文\n"
    fixed = kls.ensure_frontmatter(partial, domain, "K-1", "2026-11-26")
    assert "item_id: K-1" in fixed
    assert "title: 测试" in fixed, "已有键被覆盖"
    assert kls.ensure_frontmatter(fixed, domain, "K-1", "2026-11-26") == fixed, "补全非幂等"
