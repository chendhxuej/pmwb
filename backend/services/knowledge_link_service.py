"""业务知识关联服务（kc-2 规范实现）。

职责：
- 以数据库 `pmwb_knowledge_link` 为关联权威源，维护「知识索引 ↔ 过程性对象」多对多关系；
- 关联变更时同步主笔记 Obsidian frontmatter 的 `related_*` 数组（related_reqs /
  related_tickets / related_meetings / related_issues / related_deliverables），
  并重建正文「## 7. 关联过程性内容索引」章节的 [[...]] 链接列表；
- 提供「新建业务知识主笔记」：按方案 §4.1/4.2 生成标准模板文件并建立索引。

与 services/knowledge_link.py（早期版本，按「## 关联对象」章节同步）并存，
本模块是 spec 要求的标准实现，routers 新增端点调用本模块。
"""
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from core.exceptions import NotFoundException
from db.models import PmwbBusinessDomain, PmwbKnowledgeItem, PmwbKnowledgeLink
from utils.obsidian import (
    append_or_replace_section,
    read_frontmatter,
    read_markdown,
    replace_section,
    sanitize_filename,
    write_frontmatter,
    write_markdown,
)

# source_type -> frontmatter related_* 字段名
SOURCE_FM_KEY = {
    "requirement": "related_reqs",
    "ticket": "related_tickets",
    "meeting": "related_meetings",
    "operation": "related_issues",
    "deliverable": "related_deliverables",
    "key_work": "related_key_works",
}

# source_type -> 章节链接类型中文名
SOURCE_LABELS = {
    "requirement": "关联需求",
    "ticket": "关联开发工单",
    "meeting": "关联会议",
    "operation": "关联运营工单",
    "deliverable": "关联交付物",
    "key_work": "关联重点工作",
}


def _gen_item_id() -> str:
    date = datetime.now().strftime("%Y%m%d")
    rand = str(datetime.now().microsecond % 1000).zfill(3)
    return f"KNOW-{date}-{rand}"


def _serialize(link: PmwbKnowledgeLink, item: Optional[PmwbKnowledgeItem]) -> dict:
    return {
        "link_id": link.id,
        "knowledge_item_id": link.knowledge_item_id,
        "item_id": item.item_id if item else None,
        "title": item.title if item else None,
        "obsidian_path": item.obsidian_path if item else None,
        "domain_code": link.domain_code,
        "link_type": link.link_type,
        "note": link.note,
        "source_type": link.source_type,
        "source_id": link.source_id,
        "created_at": link.created_at.strftime("%Y-%m-%d %H:%M:%S") if link.created_at else None,
    }


def _get_item(db: Session, knowledge_item_id: int) -> PmwbKnowledgeItem:
    item = db.query(PmwbKnowledgeItem).filter(PmwbKnowledgeItem.id == knowledge_item_id).first()
    if not item:
        raise NotFoundException(f"知识条目不存在：id={knowledge_item_id}")
    return item


def link_note(
    db: Session,
    knowledge_item_id: int,
    source_type: str,
    source_id: str,
    link_type: str = "main",
    domain_code: Optional[str] = None,
    note: Optional[str] = None,
) -> dict:
    """建立一条关联（幂等：已存在则更新 note/domain_code），并同步主笔记 frontmatter 与正文索引。"""
    item = _get_item(db, knowledge_item_id)

    existing = (
        db.query(PmwbKnowledgeLink)
        .filter(
            PmwbKnowledgeLink.knowledge_item_id == knowledge_item_id,
            PmwbKnowledgeLink.source_type == source_type,
            PmwbKnowledgeLink.source_id == str(source_id),
        )
        .first()
    )
    if existing:
        if note is not None:
            existing.note = note
        if domain_code:
            existing.domain_code = domain_code
        db.commit()
        db.refresh(existing)
    else:
        link = PmwbKnowledgeLink(
            knowledge_item_id=knowledge_item_id,
            source_type=source_type,
            source_id=str(source_id),
            link_type=link_type,
            domain_code=domain_code or item.domain_code,
            note=note,
        )
        db.add(link)
        db.commit()
        db.refresh(link)
        existing = link

    _sync_frontmatter_and_section(db, knowledge_item_id)
    return _serialize(existing, item)


def unlink(db: Session, knowledge_item_id: int, source_type: str, source_id: str) -> bool:
    """删除一条关联，并同步清理主笔记 frontmatter 与正文索引。"""
    link = (
        db.query(PmwbKnowledgeLink)
        .filter(
            PmwbKnowledgeLink.knowledge_item_id == knowledge_item_id,
            PmwbKnowledgeLink.source_type == source_type,
            PmwbKnowledgeLink.source_id == str(source_id),
        )
        .first()
    )
    if not link:
        return False
    db.delete(link)
    db.commit()
    _sync_frontmatter_and_section(db, knowledge_item_id)
    return True


def list_by_source(db: Session, source_type: str, source_id: str) -> List[dict]:
    """列出某过程性对象已关联的知识条目。"""
    rows = (
        db.query(PmwbKnowledgeLink)
        .filter(
            PmwbKnowledgeLink.source_type == source_type,
            PmwbKnowledgeLink.source_id == str(source_id),
        )
        .order_by(PmwbKnowledgeLink.created_at.desc())
        .all()
    )
    result = []
    for r in rows:
        item = db.query(PmwbKnowledgeItem).filter(PmwbKnowledgeItem.id == r.knowledge_item_id).first()
        if item:
            result.append(_serialize(r, item))
    return result


def list_by_item(db: Session, knowledge_item_id: int) -> List[dict]:
    """列出某知识条目已关联的全部过程性对象。"""
    rows = (
        db.query(PmwbKnowledgeLink)
        .filter(PmwbKnowledgeLink.knowledge_item_id == knowledge_item_id)
        .order_by(PmwbKnowledgeLink.created_at.desc())
        .all()
    )
    item = db.query(PmwbKnowledgeItem).filter(PmwbKnowledgeItem.id == knowledge_item_id).first()
    return [_serialize(r, item) for r in rows]


# ---------------------------------------------------------------------------
# frontmatter 与正文同步
# ---------------------------------------------------------------------------

def _sync_frontmatter_and_section(db: Session, knowledge_item_id: int):
    """根据 pmwb_knowledge_link 重建主笔记 frontmatter related_* 数组与正文索引章节。"""
    item = db.query(PmwbKnowledgeItem).filter(PmwbKnowledgeItem.id == knowledge_item_id).first()
    if not item or not item.obsidian_path:
        return
    links = (
        db.query(PmwbKnowledgeLink)
        .filter(PmwbKnowledgeLink.knowledge_item_id == knowledge_item_id)
        .all()
    )

    # 1. frontmatter related_* 数组
    grouped: Dict[str, List[str]] = {}
    for lk in links:
        key = SOURCE_FM_KEY.get(lk.source_type)
        if not key:
            continue
        grouped.setdefault(key, [])
        if lk.source_id not in grouped[key]:
            grouped[key].append(lk.source_id)

    fm = read_frontmatter(item.obsidian_path)
    changed = False
    for key in set(SOURCE_FM_KEY.values()):
        new_val = grouped.get(key, [])
        old_val = fm.get(key)
        old_list = old_val if isinstance(old_val, list) else ([] if old_val is None else [old_val])
        if old_list != new_val:
            fm[key] = new_val
            changed = True
    if changed:
        write_frontmatter(item.obsidian_path, fm)

    # 2. 正文「关联过程性内容索引」章节（## 7. 关联过程性内容索引）
    _rebuild_linked_section(db, item, links)


def _rebuild_linked_section(db: Session, item: PmwbKnowledgeItem, links: List[PmwbKnowledgeLink]):
    """重建主笔记正文第 7 章「关联过程性内容索引」的 [[...]] 链接列表。"""
    content = read_markdown(item.obsidian_path)
    if content is None:
        return
    by_type: Dict[str, List[str]] = {}
    for lk in links:
        by_type.setdefault(lk.source_type, [])
        if lk.source_id not in by_type[lk.source_type]:
            by_type[lk.source_type].append(lk.source_id)

    if not links:
        # 无关联：移除该章节（保留其余正文）
        body = _remove_section(content, "7. 关联过程性内容索引")
        body = _remove_section(body, "关联过程性内容索引")
        if body != content:
            write_markdown(item.obsidian_path, body)
        return

    lines = ["> 以下链接由系统自动维护，删除或新增关联时会同步更新。", ""]
    for st in ("requirement", "ticket", "meeting", "operation", "deliverable", "key_work"):
        ids = by_type.get(st)
        if not ids:
            continue
        label = SOURCE_LABELS.get(st, st)
        lines.append(f"### {label}")
        for sid in ids:
            lines.append(f"- [[{sid}]]")
        lines.append("")
    new_section = "\n".join(lines).rstrip()
    new_content = append_or_replace_section(content, "7. 关联过程性内容索引", new_section)
    if new_content != content:
        write_markdown(item.obsidian_path, new_content)


def _remove_section(content: str, heading: str) -> str:
    """删除正文中名为 `## heading` 的章节（含下级小节直到下一个同级/更高级标题）。"""
    import re

    lines = content.split("\n")
    out = []
    i = 0
    n = len(lines)
    pat = re.compile(r"^##\s+" + re.escape(heading) + r"\s*$")
    while i < n:
        if pat.match(lines[i]):
            j = i + 1
            while j < n and not re.match(r"^##\s+", lines[j]) and not re.match(r"^#\s+", lines[j]):
                j += 1
            i = j
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out).rstrip("\n") + "\n"


# ---------------------------------------------------------------------------
# 主笔记模板
# ---------------------------------------------------------------------------

def build_main_note_markdown(
    domain: PmwbBusinessDomain,
    item_id: str,
    created_date: str,
) -> str:
    """按方案 §4.1/4.2 生成业务知识主笔记 Markdown。"""
    title = f"{domain.domain_name} 业务知识主笔记"
    fm = {
        "item_id": item_id,
        "domain_code": domain.domain_code,
        "domain_name": domain.domain_name,
        "domain_group": domain.domain_group,
        "note_type": "business_main",
        "sub_type": "main",
        "title": title,
        "created_date": created_date,
        "updated_date": created_date,
        "source_type": "manual",
        "tags": ["业务知识", domain.domain_group, domain.domain_name, "主笔记"],
        "related_sub_notes": [],
        "related_reqs": [],
        "related_tickets": [],
        "related_meetings": [],
        "related_issues": [],
        "related_deliverables": [],
    }
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            lines.append(f"{k}: [{', '.join(v)}]" if v else f"{k}: []")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    lines.append("> 本笔记为该业务领域的唯一主入口，**不堆过程细节**；详细过程性内容请通过下方链接跳转到对应需求/工单/会议/运营笔记。")
    lines.append("")
    lines.append("## 1. 业务概述")
    lines.append("")
    lines.append("- **业务定义**：")
    lines.append("- **目标客户**：")
    lines.append("- **核心价值**：")
    lines.append("- **涉及系统**：")
    lines.append("- **业务Owner**：")
    lines.append("- **主笔记维护人**：")
    lines.append("")
    lines.append("## 2. 产商品与资费体系")
    lines.append("")
    lines.append("### 2.1 产品矩阵")
    lines.append("")
    lines.append("| 产品 | 定位 | 目标客户 | 备注 |")
    lines.append("|------|------|----------|------|")
    lines.append("|      |      |          |      |")
    lines.append("")
    lines.append("### 2.2 资费与计费规则")
    lines.append("")
    lines.append("- ")
    lines.append("")
    lines.append("## 3. 客户服务场景 SOP")
    lines.append("")
    lines.append("### 3.1 常见服务场景")
    lines.append("")
    lines.append("| 场景 | 责任角色 | 关键步骤 | SLA |")
    lines.append("|------|----------|----------|-----|")
    lines.append("|      |          |          |     |")
    lines.append("")
    lines.append("## 4. 业务规则")
    lines.append("")
    lines.append("### 4.1 通用规则")
    lines.append("")
    lines.append("- ")
    lines.append("")
    lines.append("### 4.2 场景规则")
    lines.append("")
    lines.append("- ")
    lines.append("")
    lines.append("## 5. 优化与变更轨迹")
    lines.append("")
    lines.append("| 日期 | 变更内容 | 原因/背景 | 影响范围 | 关联需求 |")
    lines.append("|------|----------|-----------|----------|----------|")
    lines.append("|      |          |           |          |          |")
    lines.append("")
    lines.append("## 6. 关联交付物")
    lines.append("")
    lines.append("| 交付物 | 类型 | 存储路径 | 来源工单 | 更新日期 |")
    lines.append("|--------|------|----------|----------|----------|")
    lines.append("|        |      |          |          |          |")
    lines.append("")
    lines.append("## 7. 关联过程性内容索引")
    lines.append("")
    lines.append("> 以下链接由系统自动维护，删除或新增关联时会同步更新。")
    lines.append("")
    lines.append("## 8. 相关子笔记 MOC")
    lines.append("")
    lines.append("")
    return "\n".join(lines) + "\n"


def create_main_note(db: Session, domain_code: str) -> dict:
    """新建业务知识主笔记：生成标准模板文件 + 建知识索引（幂等：已存在则返回现有）。

    返回 {created: bool, item: {...}}。
    """
    domain = (
        db.query(PmwbBusinessDomain)
        .filter(PmwbBusinessDomain.domain_code == domain_code)
        .first()
    )
    if not domain:
        raise NotFoundException(f"业务领域 '{domain_code}' 不存在")

    title = f"{domain.domain_name} 业务知识主笔记"
    # 已有主笔记则直接返回
    existing = (
        db.query(PmwbKnowledgeItem)
        .filter(PmwbKnowledgeItem.domain_code == domain_code)
        .filter(PmwbKnowledgeItem.title == title)
        .first()
    )
    if existing:
        return {"created": False, "item": _item_dict(existing)}

    # 目录：01-业务知识/{domain_group}/{domain_name}/
    base_dir = f"01-业务知识/{domain.domain_group}/{domain.domain_name}"
    rel_path = f"{base_dir}/{sanitize_filename(title)}.md"

    item_id = _gen_item_id()
    created_date = datetime.now().strftime("%Y-%m-%d")
    md = build_main_note_markdown(domain, item_id, created_date)
    write_markdown(rel_path, md)

    item = PmwbKnowledgeItem(
        item_id=item_id,
        title=title,
        category="product",
        sub_category="主笔记",
        tags="业务知识,主笔记",
        obsidian_path=rel_path,
        source_type="manual",
        source_id=domain_code,
        domain_code=domain_code,
        summary=f"{domain.domain_name} 业务知识主笔记（业务概述/产商品资费/SOP/规则/变更轨迹/交付物）",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"created": True, "item": _item_dict(item)}


def _item_dict(item: PmwbKnowledgeItem) -> dict:
    return {
        "id": item.id,
        "item_id": item.item_id,
        "title": item.title,
        "category": item.category,
        "sub_category": item.sub_category,
        "tags": item.tags,
        "obsidian_path": item.obsidian_path,
        "domain_code": item.domain_code,
        "summary": item.summary,
    }
