"""路径权威源增强（T1 / kc-4 知识中心 P0）测试。

验证 obsidian_paths 新增能力：
- group_alias：DB domain_group -> 模板 key
- main_note_rel_path / main_note_filename：主笔记相对路径
- build_main_note_skeleton：按三类（business/platform/capability）渲染 frontmatter + 章节骨架，编号与 §3.8.3 严格一致
- ensure_domain_dir：建根 + 5 子目录 + 主笔记（已存在不覆盖）
"""
import pytest

from core.config import settings
from core.exceptions import NotFoundException
from db.models import PmwbBusinessDomain
from services import obsidian_paths


@pytest.fixture
def vault_tmp(tmp_path, monkeypatch):
    """把 Obsidian vault 根目录指向临时目录，避免污染真实知识库。"""
    monkeypatch.setattr(settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    return tmp_path


def _domain(db, code, name, group, vault_path=None):
    d = PmwbBusinessDomain(
        domain_code=code,
        domain_name=name,
        domain_group=group,
        vault_path=vault_path or f"01-业务知识/{group}/{name}",
        enabled=True,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


# ---------- 纯函数 ----------

def test_group_alias():
    assert obsidian_paths.group_alias("商客业务") == "business"
    assert obsidian_paths.group_alias("系统平台") == "platform"
    assert obsidian_paths.group_alias("公共能力") == "capability"
    assert obsidian_paths.group_alias("通用") == "general"
    # 未知分组兜底 general
    assert obsidian_paths.group_alias("未知分组") == "general"


def test_main_note_rel_path():
    p = obsidian_paths.main_note_rel_path("一网通宽带", "商客业务")
    assert p == "01-业务知识/商客业务/一网通宽带/一网通宽带 业务知识主笔记.md"
    p2 = obsidian_paths.main_note_rel_path("电子协议", "系统平台")
    assert p2 == "01-业务知识/系统平台/电子协议/电子协议 业务知识主笔记.md"


def test_build_main_note_skeleton_business():
    md = obsidian_paths.build_main_note_skeleton("一网通宽带", "商客业务")
    assert md.startswith("---\n")
    assert "tags: [商客业务]" in md
    # 人工区章节
    assert "## 1. 业务概述" in md
    assert "## 2.1 产商品体系" in md
    assert "## 2.2 资费体系" in md
    # 自动区章节 + 标记
    assert "## 2.3 产商品变更（系统自动）" in md
    assert "## 3.2 流程变更（系统自动）" in md
    assert "## 9. 业务全过程时间线（系统自动）" in md
    # §10 必须存在（之前永不落盘的根因之一）
    assert "## 10. 关联系统与接口" in md


def test_build_main_note_skeleton_platform():
    md = obsidian_paths.build_main_note_skeleton("订单中心", "系统平台")
    assert "tags: [系统平台]" in md
    assert "## 1. 平台概述" in md
    assert "## 2.2 适用业务场景（支撑哪些商客业务）" in md
    assert "## 2.3 功能迭代轨迹（系统自动）" in md
    assert "## 10. 关联系统集成（上下游系统对接）" in md


def test_build_main_note_skeleton_capability():
    md = obsidian_paths.build_main_note_skeleton("一键订购", "公共能力")
    assert "tags: [公共能力]" in md
    assert "## 1. 能力介绍" in md
    assert "## 4. 快速建档与标签" in md
    assert "## 6. 使用与调用轨迹（系统自动）" in md
    assert "## 9. 能力演进时间线（系统自动）" in md


def test_build_skeleton_three_types_distinct():
    biz = obsidian_paths.build_main_note_skeleton("X", "商客业务")
    plat = obsidian_paths.build_main_note_skeleton("X", "系统平台")
    cap = obsidian_paths.build_main_note_skeleton("X", "公共能力")
    # 三类不得混用同一套章节（核心诉求：结构差异化）
    assert "业务概述" in biz and "平台概述" not in biz
    assert "平台概述" in plat and "业务概述" not in plat
    assert "能力介绍" in cap and "平台概述" not in cap


# ---------- ensure_domain_dir（依赖 db + 隔离 vault） ----------

def test_ensure_domain_dir_creates_tree(db, vault_tmp):
    _domain(db, "ywt-broadband", "一网通宽带", "商客业务")
    root = obsidian_paths.ensure_domain_dir(db, "ywt-broadband")
    root_path = vault_tmp / "01-业务知识/商客业务/一网通宽带"
    assert root_path.exists()
    for sub in ["03-业务规则", "05-交付物", "运营", "会议", "开发交付"]:
        assert (root_path / sub).exists(), f"子目录缺失：{sub}"
    note = root_path / "一网通宽带 业务知识主笔记.md"
    assert note.exists()
    text = note.read_text(encoding="utf-8")
    assert "## 1. 业务概述" in text
    assert "## 10. 关联系统与接口" in text


def test_ensure_domain_dir_idempotent_no_overwrite(db, vault_tmp):
    _domain(db, "ywt-broadband", "一网通宽带", "商客业务")
    obsidian_paths.ensure_domain_dir(db, "ywt-broadband")
    note = vault_tmp / "01-业务知识/商客业务/一网通宽带/一网通宽带 业务知识主笔记.md"
    txt0 = note.read_text(encoding="utf-8")
    # 人工在主笔记追加内容后，二次 ensure 不得覆盖
    note.write_text(txt0 + "\n## 1. 业务概述\n人工补充的关键内容\n", encoding="utf-8")
    obsidian_paths.ensure_domain_dir(db, "ywt-broadband")
    txt1 = note.read_text(encoding="utf-8")
    assert "人工补充的关键内容" in txt1  # 未被覆盖


def test_ensure_domain_dir_not_found(db, vault_tmp):
    with pytest.raises(NotFoundException):
        obsidian_paths.ensure_domain_dir(db, "no-such-code")
