"""业务知识路径权威源（kc-3 / P0）。

集中计算各业务领域在 Obsidian vault 下的笔记目录，避免散落硬编码导致的
口径不一致（此前运营/会议/开发交付各自写死 11-业务运营/、05-会议纪要/、
14-知识沉淀/开发交付/ 等非领域树路径，与"业务知识主笔记"所在的
`01-业务知识/{group}/{name}/` 树割裂）。

统一约定（领域树 + 分目录管理铁律）：
    01-业务知识/{domain_group}/{domain_name}/
        ├─ 03-业务规则/      （场景规则子笔记，sediment_operation_rules）
        ├─ 05-交付物/        （操作手册归档，archive_requirement_manual）
        ├─ 运营/             （运营工单沉淀，sediment_operation_issue）
        ├─ 会议/             （会议纪要沉淀，sediment_meeting）
        ├─ 开发交付/          （开发工单沉淀，sediment_dev_ticket）
        └─ {name} 业务知识主笔记.md  （主笔记，套三类差异化模板骨架）

四类分组（分目录管理铁律，见图知识中心优化方案评估.md §3.7）：
    商客业务 / 系统平台 / 公共能力 / 通用
"""
import re
from pathlib import Path

from db.models import PmwbBusinessDomain
from core.exceptions import NotFoundException
from core.config import settings

# 领域树根目录名
BUSINESS_KNOWLEDGE_DIR = "01-业务知识"

# 各对象类型在领域树下的子目录名
SUBDIR_OPERATION = "运营"
SUBDIR_MEETING = "会议"
SUBDIR_DEV_TICKET = "开发交付"
SUBDIR_RULES = "03-业务规则"
SUBDIR_DELIVERABLE = "05-交付物"

# 领域根下统一创建的子目录（页面化同步创建时一并建好）
DOMAIN_SUBDIRS = [SUBDIR_RULES, SUBDIR_DELIVERABLE, SUBDIR_OPERATION, SUBDIR_MEETING, SUBDIR_DEV_TICKET]

# 主笔记文件名后缀
MAIN_NOTE_SUFFIX = "业务知识主笔记.md"

# DB domain_group -> 模板 key（分目录管理铁律）
GROUP_ALIAS = {
    "商客业务": "business",
    "系统平台": "platform",
    "公共能力": "capability",
    "通用": "general",
}
GROUP_TAG = {
    "business": "商客业务",
    "platform": "系统平台",
    "capability": "公共能力",
    "general": "通用",
}
# 章节区属性标记：人工维护区 / 自动区 / 系统维护区
ZONE_LABEL = {"baseline": "", "auto": "（系统自动）", "system": "（系统维护）"}

# 三类主笔记标准结构（与方案 §3.8.3 严格一致）：(编号, 标题, 区属性)
MAIN_NOTE_SECTIONS = {
    "business": [
        ("1", "业务概述", "baseline"),
        ("2.1", "产商品体系", "baseline"),
        ("2.2", "资费体系", "baseline"),
        ("2.3", "产商品变更", "auto"),
        ("3.1", "客户服务场景 SOP", "baseline"),
        ("3.2", "流程变更", "auto"),
        ("4.1", "通用规则", "baseline"),
        ("4.2", "场景规则", "auto"),
        ("5", "优化与变更轨迹", "auto"),
        ("6", "关联交付物", "auto"),
        ("7", "关联过程性内容索引", "system"),
        ("8", "相关子笔记 MOC", "system"),
        ("9", "业务全过程时间线", "auto"),
        ("10", "关联系统与接口", "baseline"),
    ],
    "platform": [
        ("1", "平台概述", "baseline"),
        ("2.1", "核心功能模块", "baseline"),
        ("2.2", "适用业务场景（支撑哪些商客业务）", "baseline"),
        ("2.3", "功能迭代轨迹", "auto"),
        ("3.1", "运营/客服操作 SOP", "baseline"),
        ("3.2", "流程优化记录", "auto"),
        ("4", "关键规则与权限", "baseline"),
        ("5", "平台变更与问题台账", "auto"),
        ("6", "关联交付物", "auto"),
        ("7", "关联内容索引", "system"),
        ("8", "相关子笔记 MOC", "system"),
        ("9", "平台演进时间线", "auto"),
        ("10", "关联系统集成（上下游系统对接）", "baseline"),
    ],
    "capability": [
        ("1", "能力介绍", "baseline"),
        ("2", "适用业务与场景", "baseline"),
        ("3", "业务流程（能力怎么用）", "baseline"),
        ("4", "快速建档与标签", "baseline"),
        ("5", "关键规则", "baseline"),
        ("6", "使用与调用轨迹", "auto"),
        ("7", "关联内容索引", "system"),
        ("8", "相关子笔记 MOC", "system"),
        ("9", "能力演进时间线", "auto"),
    ],
    "general": [
        ("1", "概述", "baseline"),
        ("2", "关键内容", "baseline"),
        ("3", "关联内容索引", "system"),
    ],
}


def group_alias(group: str) -> str:
    """DB domain_group -> 模板 key，未知分组兜底 general。"""
    return GROUP_ALIAS.get(group, "general")


def main_note_filename(name: str) -> str:
    """主笔记文件名：{领域名} 业务知识主笔记.md。"""
    return f"{name} {MAIN_NOTE_SUFFIX}"


def main_note_rel_path(name: str, group: str) -> str:
    """主笔记相对 vault 路径：01-业务知识/{group}/{name}/{name} 业务知识主笔记.md。"""
    return f"{BUSINESS_KNOWLEDGE_DIR}/{group}/{name}/{main_note_filename(name)}"


def _render_sections(sections) -> str:
    lines = []
    for no, title, zone in sections:
        suffix = ZONE_LABEL.get(zone, "")
        # 整数编号加 ". "；带小数点编号（如 2.1）直接用，避免 "2.1." 双点
        sep = "" if "." in no else "."
        lines.append(f"## {no}{sep} {title}{suffix}")
        lines.append("")
        if zone == "baseline":
            lines.append("> 人工维护区，自动沉淀不覆盖，请补充内容。")
        elif zone == "auto":
            lines.append("> 自动区：由业务事件自动回流（详见知识中心自动沉淀方案），人工请勿直接编辑。")
        else:
            lines.append("> 系统维护区，由 vault_sync 自动生成。")
        lines.append("")
    return "\n".join(lines)


def build_main_note_skeleton(name: str, group: str) -> str:
    """按领域类型渲染主笔记骨架（frontmatter + §1–§N 章节）。

    编号前缀与生成器/手写严格一致（修复此前 get_main_note_structured 按
    "2.1" 前缀匹配却生成 "## 2." 导致永远匹配不到的 bug）。
    """
    alias = group_alias(group)
    sections = MAIN_NOTE_SECTIONS.get(alias, MAIN_NOTE_SECTIONS["general"])
    tag = GROUP_TAG.get(alias, "通用")
    fm = [
        "---",
        "type: 业务知识主笔记",
        f"domain: {name}",
        f"group: {group}",
        f"tags: [{tag}]",
        "auto_sync: true",
        "---",
        "",
        f"# {name} 业务知识主笔记",
        "",
        "> 本笔记由 PMWB 知识中心自动生成骨架，按领域类型套用模板。人工维护区（baseline）请补充内容；"
        "自动区（系统自动）由业务事件自动回流；系统维护区（系统维护）由 vault_sync 自动生成。",
        "",
        _render_sections(sections),
    ]
    return "\n".join(fm)


def ensure_domain_dir(db, domain_code: str, force: bool = False) -> str:
    """在 vault 创建领域目录树 + 主笔记骨架（页面化同步创建核心）。

    建根目录 + 5 个子目录；主笔记已存在则不覆盖（保留人工内容），force=True 才重写。
    返回领域绝对路径。vault 不可达由调用方捕获处理（不在此抛致命错误）。
    """
    domain = db.query(PmwbBusinessDomain).filter(
        PmwbBusinessDomain.domain_code == domain_code
    ).first()
    if not domain:
        raise NotFoundException(message=f"业务领域不存在：{domain_code}")
    rel_root = f"{BUSINESS_KNOWLEDGE_DIR}/{domain.domain_group}/{domain.domain_name}"
    abs_root = Path(settings.OBSIDIAN_VAULT_PATH) / rel_root
    abs_root.mkdir(parents=True, exist_ok=True)
    for sub in DOMAIN_SUBDIRS:
        (abs_root / sub).mkdir(parents=True, exist_ok=True)
    note = abs_root / main_note_filename(domain.domain_name)
    if force or not note.exists():
        note.write_text(build_main_note_skeleton(domain.domain_name, domain.domain_group), encoding="utf-8")
    return str(abs_root)


def resolve_domain_path(db, domain_code: str) -> str:
    """返回某领域在 vault 下的相对根目录：01-业务知识/{domain_group}/{domain_name}。

    这是领域相关笔记落盘位置的唯一权威来源，所有 sediment_* 函数都应经此解析，
    不得再硬编码 `01-业务知识/{group}/{name}`。
    """
    domain = db.query(PmwbBusinessDomain).filter(
        PmwbBusinessDomain.domain_code == domain_code
    ).first()
    if not domain:
        raise NotFoundException(message=f"业务领域不存在：{domain_code}")
    return f"{BUSINESS_KNOWLEDGE_DIR}/{domain.domain_group}/{domain.domain_name}"


def operation_dir(db, domain_code: str) -> str:
    """运营工单沉淀目录（相对 vault）。"""
    return f"{resolve_domain_path(db, domain_code)}/{SUBDIR_OPERATION}"


def meeting_dir(db, domain_code: str) -> str:
    """会议纪要沉淀目录（相对 vault）。"""
    return f"{resolve_domain_path(db, domain_code)}/{SUBDIR_MEETING}"


def dev_ticket_dir(db, domain_code: str) -> str:
    """开发工单沉淀目录（相对 vault）。"""
    return f"{resolve_domain_path(db, domain_code)}/{SUBDIR_DEV_TICKET}"
