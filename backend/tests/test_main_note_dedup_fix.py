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


def test_section7_rebuild_ignores_5min_write_guard(db, vault_tmp):
    """刚生成/刚修改的主笔记（mtime<5min）也必须能回填 §7 自动区。

    回归背景：迁移领域后重建 §7 被 write_markdown 的「最近修改」保护静默跳过，
    新领域主笔记 §7 长期为空。自动回流只改自动区，人工正文源同一份 read，
    因此强制写入不会覆盖人工内容。
    """
    from db.models import PmwbKnowledgeItem, PmwbRequirementExt
    from utils.obsidian import write_markdown

    _seed_domain(db, "jtqly", "集团千里眼业务", "商客业务")
    rel = op.main_note_rel_path("集团千里眼业务", "商客业务")
    body = (
        "# 集团千里眼业务 业务知识主笔记\n\n"
        "## 7. 关联过程性内容索引\n\n> 以下链接由系统自动维护，删除或新增关联时会同步更新。\n\n"
        "## 8. 相关子笔记 MOC\n"
    )
    write_markdown(rel, body, protect_if_modified=False)  # mtime = now

    db.add(PmwbKnowledgeItem(
        item_id="KNOW-TEST-001", title="集团千里眼业务 业务知识主笔记",
        category="product", sub_category="主笔记", tags="业务知识",
        obsidian_path=rel, source_type="manual", source_id="jtqly",
        domain_code="jtqly", note_type="main", summary="test",
    ))
    db.add(PmwbRequirementExt(
        req_id="REQ-TEST-1", req_name="千里眼批量销户", domain_code="jtqly",
    ))
    db.commit()

    assert kls.rebuild_main_note_section7(db, "jtqly") is True
    after = read_markdown(rel)
    assert "### 关联需求" in after, "5 分钟写保护挡住了 §7 自动区回填"
    assert "REQ-TEST-1" in after
    # 反向保护：读取后到写入前若用户在 Obsidian 编辑了人工区，必须拒绝写入
    from utils.obsidian import write_markdown as wm
    disk_now = read_markdown(rel) + "\n人工正文哨兵XYZ\n"
    wm(rel, disk_now, protect_if_modified=False)
    assert kls._write_auto_refresh(rel, read_markdown(rel) + "\n旧快照\n", "新内容") is False
    assert read_markdown(rel) == disk_now, "读取后的人工编辑被自动回流覆盖"


# --- 结构规范化：错乱主笔记（A骨架+B模板混排）重排 ---

def _chaotic_content():
    """模拟跨省企业宽带式错乱：无 frontmatter、H1 流窜、§1-§9 空壳在前、### 内容在后。"""
    return """## 1. 业务概述
- **业务定义**：面向连锁客户跨省组网。

## 2. 产商品与资费体系

## 3. 客户服务场景 SOP

## 4. 业务规则

## 5. 优化与变更轨迹（自动区）
<!-- PMWB:AUTO:BEGIN key=change_log -->
_暂无变更_
<!-- PMWB:AUTO:END key=change_log -->

## 9. 业务全过程时间线（自动区）
<!-- PMWB:AUTO:BEGIN key=timeline -->
- 2026-11-25 · [运营] 输出落地方案
<!-- PMWB:AUTO:END key=timeline -->

# 跨省企业宽带 业务知识主笔记
> 本笔记唯一主入口。

### 2.1 产品矩阵（人工维护）
| 产品 | 定位 |
|------|------|
| 跨省企业宽带 | 连锁客户 |

### 3.1 常见服务场景（人工维护）
| 场景 | 步骤 |
| 受理 | 一点受理 |

### 关联需求
- [[REQ-1]] 改造通知

## 相关子笔记 MOC
_暂无子笔记_
"""


def test_restructure_chaotic_note(db):
    domain = PmwbBusinessDomain(domain_code="KSQYKD", domain_name="跨省企业宽带", domain_group="商客业务", enabled=True)
    out = kls.restructure_main_note_content(_chaotic_content(), domain, "K-1", "2026-11-26")
    lines = out.splitlines()
    # frontmatter + H1 在前
    assert out.startswith("---")
    h1 = [i for i, l in enumerate(lines, 1) if re.match(r"^# ", l)]
    assert len(h1) == 1 and h1[0] <= 25, f"H1 未在头部: {h1}"
    # §1-§10 顺序
    heads = [m.group(1) for l in lines for m in [re.match(r"^## (\d+)\.", l)] if m]
    assert heads == sorted(heads, key=int), f"章节顺序错乱: {heads}"
    # 人工正文归位且保留
    assert "面向连锁客户跨省组网" in out
    assert "| 跨省企业宽带 | 连锁客户 |" in out
    assert "| 受理 | 一点受理 |" in out
    # AUTO 回填内容保留
    assert "2026-11-25 · [运营] 输出落地方案" in out
    # 无编号 MOC 残留清除、AUTO 块唯一
    assert not any(l.strip() == "## 相关子笔记 MOC" for l in lines)
    for key in ("change_log", "timeline", "product", "process", "scenario_rules", "deliverables"):
        assert out.count(f"PMWB:AUTO:BEGIN key={key}") == 1, f"{key} 块非唯一"


def test_restructure_idempotent(db):
    domain = PmwbBusinessDomain(domain_code="KSQYKD", domain_name="跨省企业宽带", domain_group="商客业务", enabled=True)
    once = kls.restructure_main_note_content(_chaotic_content(), domain, "K-1", "2026-11-26")
    twice = kls.restructure_main_note_content(once, domain, "K-1", "2026-11-26")
    assert once == twice, "结构规范化非幂等"


def test_restructure_preserves_manual_edits(db):
    """人工区任何正文都必须原样保留（只换位置、不改字）。"""
    domain = PmwbBusinessDomain(domain_code="KSQYKD", domain_name="跨省企业宽带", domain_group="商客业务", enabled=True)
    src = _chaotic_content().replace(
        "- **业务定义**：面向连锁客户跨省组网。",
        "- **业务定义**：人工撰写的关键定义，一字不改。",
    )
    out = kls.restructure_main_note_content(src, domain, "K-1", "2026-11-26")
    assert "人工撰写的关键定义，一字不改。" in out


# --- 审查发现的边界：父章节导语/非标准编号/AUTO旁正文/frontmatter元数据/回填幂等 ---

def test_restructure_keeps_parent_intro_and_children(db):
    """父章节（## 2）下的导语必须保留，且不能覆盖其 ### 子节与其中 AUTO 块。"""
    domain = PmwbBusinessDomain(domain_code="KSQYKD", domain_name="跨省企业宽带", domain_group="商客业务", enabled=True)
    src = """## 1. 业务概述
- 定义。

## 2. 产商品与资费体系
本节导语：涵盖多类产品。

### 2.1 产品矩阵（人工维护）
| 产品 | 定位 |
| A | B |

### 2.3 产品变更（自动区）
<!-- PMWB:AUTO:BEGIN key=product -->
- 变更记录X
<!-- PMWB:AUTO:END key=product -->

## 3. 客户服务场景 SOP
"""
    out = kls.restructure_main_note_content(src, domain, "K-1", "2026-11-26")
    assert "本节导语：涵盖多类产品。" in out, "父章节导语丢失"
    assert "| A | B |" in out, "### 子节被父章节覆盖删除"
    assert "- 变更记录X" in out, "子节内 AUTO 回填内容丢失"
    assert out.count("PMWB:AUTO:BEGIN key=product") == 1


def test_restructure_keeps_nonstandard_and_unnumbered_sections(db):
    """非标准编号（2.9）/ 无编号人工章节不得静默丢弃。"""
    domain = PmwbBusinessDomain(domain_code="KSQYKD", domain_name="跨省企业宽带", domain_group="商客业务", enabled=True)
    src = """## 1. 业务概述
- 定义。

## 2.9 人工自定义章节
自定义章节正文ABC

## 人工补充说明
无编号正文XYZ
"""
    out = kls.restructure_main_note_content(src, domain, "K-1", "2026-11-26")
    assert "自定义章节正文ABC" in out, "非标准编号章节丢失"
    assert "无编号正文XYZ" in out, "无编号人工章节丢失"


def test_restructure_keeps_manual_text_beside_auto(db):
    """AUTO 块同章节内的人工正文（标记之外）不得随整块跳过。"""
    domain = PmwbBusinessDomain(domain_code="KSQYKD", domain_name="跨省企业宽带", domain_group="商客业务", enabled=True)
    src = """## 1. 业务概述
- 定义。

### 2.3 产品变更（自动区）
人工补充说明：MAGIC_MANUAL_TEXT
<!-- PMWB:AUTO:BEGIN key=product -->
- 变更
<!-- PMWB:AUTO:END key=product -->
"""
    out = kls.restructure_main_note_content(src, domain, "K-1", "2026-11-26")
    assert "MAGIC_MANUAL_TEXT" in out, "AUTO 旁人工正文丢失"


def test_restructure_preserves_frontmatter_metadata(db):
    """原 frontmatter 的 created_date / related_* / item_id 不得被重建覆盖。"""
    domain = PmwbBusinessDomain(domain_code="KSQYKD", domain_name="跨省企业宽带", domain_group="商客业务", enabled=True)
    src = """---
item_id: OLD-ID
created_date: 2020-01-01
related_reqs: [REQ-OLD]
---
## 1. 业务概述
- 定义。
"""
    out = kls.restructure_main_note_content(src, domain, "NEW-ID", "2026-11-26")
    assert "item_id: OLD-ID" in out
    assert "created_date: 2020-01-01" in out
    assert "related_reqs: [REQ-OLD]" in out


def test_restructure_keeps_refilled_section7_8(db):
    """对已规范且 §7/§8 已被 rebuild 回填的文件再跑，不得清空索引（幂等短路）。"""
    domain = PmwbBusinessDomain(domain_code="KSQYKD", domain_name="跨省企业宽带", domain_group="商客业务", enabled=True)
    base = kls.restructure_main_note_content(_chaotic_content(), domain, "K-1", "2026-11-26")
    # 模拟 rebuild 回填 §7/§8
    refilled = kls._replace_auto_block(base, "timeline", "- 2026-11-25 · [需求] X")
    refilled = refilled.replace(
        "## 7. 关联过程性内容索引\n\n> 以下链接由系统自动维护，删除或新增关联时会同步更新。\n",
        "## 7. 关联过程性内容索引\n\n> 以下链接由系统自动维护，删除或新增关联时会同步更新。\n\n### 关联需求\n- [[REQ-1]] 需求甲\n",
    )
    refilled = refilled.replace(
        "## 8. 相关子笔记 MOC\n",
        "## 8. 相关子笔记 MOC\n\n- **[子笔记A](path)** — 摘要一\n",
        1,
    )
    out = kls.restructure_main_note_content(refilled, domain, "K-1", "2026-11-26")
    assert "[[REQ-1]] 需求甲" in out, "§7 回填被清空"
    assert "子笔记A" in out, "§8 回填被清空"
    assert "- 2026-11-25 · [需求] X" in out, "AUTO 回填被清空"


# --- 生产链路回归：全库保活 / 手动创建不得把已修好的文件再次搞乱 ---

def _assert_standard_structure(text, label):
    lines = text.splitlines()
    h1 = [i for i, l in enumerate(lines, 1) if re.match(r"^# ", l)]
    heads = [m.group(1) for l in lines for m in [re.match(r"^## (\d+)\.", l)] if m]
    assert text.startswith("---"), f"{label}: frontmatter 丢失"
    assert len(h1) == 1 and h1[0] <= 25, f"{label}: H1 不在头部 {h1}"
    assert heads == sorted(heads, key=int), f"{label}: 章节顺序错乱 {heads}"
    assert not any(l.strip() == "## 相关子笔记 MOC" for l in lines), f"{label}: 无编号 MOC 残留"


def test_repair_damaged_restructures_chaotic(db, vault_tmp):
    """保活的 repair 分支必须用 restructure，不能按标题拼块重建。"""
    from db.models import PmwbKnowledgeItem
    from utils.obsidian import write_markdown

    _seed_domain(db)
    domain = db.query(PmwbBusinessDomain).filter_by(domain_code="jtqly").first()
    rel = op.main_note_rel_path("集团千里眼业务", "商客业务")
    write_markdown(rel, _chaotic_content(), protect_if_modified=False)
    db.add(PmwbKnowledgeItem(
        item_id="K-REPAIR", title="集团千里眼业务 业务知识主笔记",
        category="product", sub_category="主笔记", tags="业务知识",
        obsidian_path=rel, source_type="manual", source_id="jtqly",
        domain_code="jtqly", note_type="main", summary="test",
    ))
    db.commit()

    kls._repair_damaged_main_note(db, domain, rel)
    after = read_markdown(rel)
    _assert_standard_structure(after, "repair")
    assert "面向连锁客户跨省组网" in after, "repair 吞掉人工正文"


def test_keepalive_twice_keeps_structure(db, vault_tmp):
    """两轮全库保活后结构仍规范（旧 repair 每轮都会回退成错乱）。"""
    from db.models import PmwbKnowledgeItem
    from utils.obsidian import write_markdown

    _seed_domain(db)
    domain = db.query(PmwbBusinessDomain).filter_by(domain_code="jtqly").first()
    rel = op.main_note_rel_path("集团千里眼业务", "商客业务")
    write_markdown(
        rel,
        kls.build_main_note_markdown(domain, "K-KEEP", "2026-11-26"),
        protect_if_modified=False,
    )
    db.add(PmwbKnowledgeItem(
        item_id="K-KEEP", title="集团千里眼业务 业务知识主笔记",
        category="product", sub_category="主笔记", tags="业务知识",
        obsidian_path=rel, source_type="manual", source_id="jtqly",
        domain_code="jtqly", note_type="main", summary="test",
    ))
    db.commit()

    for rnd in (1, 2):
        kls._ensure_one_domain_main_note(db, domain, {"jtqly": rel})
        _assert_standard_structure(read_markdown(rel), f"keepalive-{rnd}")
    assert kls._ensure_one_domain_main_note(db, domain, {"jtqly": rel}) == "ensured"


def test_create_main_note_restructures_existing_chaotic(db, vault_tmp):
    """手动点『生成主笔记』遇到已错乱的存量文件，也要重排而非固化。"""
    from utils.obsidian import write_markdown

    _seed_domain(db)
    op.ensure_domain_dir(db, "jtqly")
    rel = op.main_note_rel_path("集团千里眼业务", "商客业务")
    write_markdown(rel, _chaotic_content(), protect_if_modified=False)

    assert kls.create_main_note(db, "jtqly")["created"] is True
    after = read_markdown(rel)
    _assert_standard_structure(after, "create-existing")
    assert "面向连锁客户跨省组网" in after, "create 分支吞掉人工正文"


def test_sync_create_vault_lands_standard_template(db, vault_tmp):
    """页面建领域后主笔记一次到位为标准模板，不留 A 骨架等保活补正。"""
    from services import business_domain as bd

    _seed_domain(db, "jtqly-new", "新建测试领域", "商客业务")
    domain = db.query(PmwbBusinessDomain).filter_by(domain_code="jtqly-new").first()
    bd._sync_create_vault(db, domain)
    rel = op.main_note_rel_path("新建测试领域", "商客业务")
    _assert_standard_structure(read_markdown(rel), "sync-create")
