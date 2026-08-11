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
from datetime import date, datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from core.exceptions import NotFoundException
from db.models import (
    PmwbBusinessDomain,
    PmwbDevTicket,
    PmwbKeyWork,
    PmwbKnowledgeItem,
    PmwbKnowledgeLink,
    PmwbMeeting,
    PmwbOperationIssue,
    PmwbRequirementExt,
    PmwbUserStory,
)
from utils.obsidian import (
    append_or_replace_section,
    read_frontmatter,
    read_markdown,
    render_auto_block,
    replace_section,
    sanitize_filename,
    upsert_auto_block,
    write_frontmatter,
    write_markdown,
)

# ---------------------------------------------------------------------------
# kc4-2 主笔记「自动区」契约
# ---------------------------------------------------------------------------
# 主笔记分「人工区」与「自动区」两类内容：
#   人工区（系统永不写）：1.业务概述 / 4.1通用规则 / 3.1人工补充的SOP细节 / 关联系统
#   自动区（由 sync_main_note_from_links 从关联表重算）：见下表 key
# 自动区一律用 <!-- PMWB:AUTO:BEGIN key=xxx --> 标记包裹，重算时整块替换，标记外内容零覆盖。
AUTO_BLOCKS = {
    "product": "2. 产商品与资费体系",       # 仅 closed + product_changed=1 的需求
    "process": "3. 客户服务场景 SOP",        # 仅 closed + process_changed=1 的需求
    "scenario_rules": "4. 业务规则",         # 用户故事 rules 非空即回写
    "change_log": "5. 优化与变更轨迹",       # 已关闭且带变更标记的需求
    "deliverables": "6. 关联交付物",         # 需求交付物 / 已归档操作手册
    "timeline": "9. 业务全过程时间线",       # 全部关联事件按 event_date 倒序
}

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
        "event_type": link.event_type,
        "event_date": link.event_date.strftime("%Y-%m-%d") if link.event_date else None,
        "summary": link.summary,
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
    event_type: Optional[str] = None,
    event_date: Optional[date] = None,
    summary: Optional[str] = None,
) -> dict:
    """建立一条关联（幂等：已存在则更新 note/domain_code/event_*），并同步主笔记 frontmatter 与正文索引。

    kc4-1 扩展：新增 event_type/event_date/summary 业务事件语义，支撑业务时间线(kc4-3)
    与主笔记 §8 变更轨迹自动生成。调用点不传时按 source_type 兜底、event_date 兜底为写入日，
    保证两列非空（存量数据由 alembic 迁移用 created_at 回填）。
    """
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
        if event_type is not None:
            existing.event_type = event_type
        if event_date is not None:
            existing.event_date = event_date
        if summary is not None:
            existing.summary = summary
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
            event_type=event_type or source_type,
            event_date=event_date or datetime.now().date(),
            summary=summary,
        )
        db.add(link)
        db.commit()
        db.refresh(link)
        existing = link

    # 回填源记录 domain_code，使源表与关联链接口径一致（避免领域浏览错位）
    _writeback_domain_code(db, source_type, str(source_id), existing.domain_code)

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


def _writeback_domain_code(db: Session, source_type: str, source_id: str, domain_code: Optional[str]):
    """关联建立后回填源记录的 domain_code（仅当源记录领域为空时）。

    用于修复「需求/运营/会议经 KnowledgeLinker 关联后，链接带 domain_code 但源记录
    仍为 NULL」导致领域浏览页"时间线有、需求/运营空"的错位。不覆盖源记录已有领域。
    """
    if not domain_code:
        return
    rec = None
    try:
        if source_type == "requirement":
            rec = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == source_id).first()
        elif source_type == "operation":
            rec = db.query(PmwbOperationIssue).filter(PmwbOperationIssue.id == int(source_id)).first()
        elif source_type == "meeting":
            rec = db.query(PmwbMeeting).filter(PmwbMeeting.id == int(source_id)).first()
        elif source_type == "ticket":
            rec = db.query(PmwbDevTicket).filter(PmwbDevTicket.ticket_no == source_id).first()
        elif source_type == "key_work":
            rec = db.query(PmwbKeyWork).filter(PmwbKeyWork.id == int(source_id)).first()
        else:
            return
    except (ValueError, TypeError):
        return
    if rec is None or rec.domain_code:
        return
    rec.domain_code = domain_code
    db.commit()


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
    lines.append("> 🤖 系统自动汇总：来源为「已关闭且标记产商品变更」的需求，人工无需手改。")
    lines.append("")
    lines.append(render_auto_block("product", ""))
    lines.append("")
    lines.append("### 2.2 资费与计费规则（人工维护）")
    lines.append("")
    lines.append("- ")
    lines.append("")
    lines.append("## 3. 客户服务场景 SOP")
    lines.append("")
    lines.append("### 3.1 常见服务场景（人工维护）")
    lines.append("")
    lines.append("| 场景 | 责任角色 | 关键步骤 | SLA |")
    lines.append("|------|----------|----------|-----|")
    lines.append("|      |          |          |     |")
    lines.append("")
    lines.append("### 3.2 流程变更记录")
    lines.append("")
    lines.append("> 🤖 系统自动汇总：来源为「已关闭且标记业务流程变更」的需求。")
    lines.append("")
    lines.append(render_auto_block("process", ""))
    lines.append("")
    lines.append("## 4. 业务规则")
    lines.append("")
    lines.append("### 4.1 通用规则（人工维护）")
    lines.append("")
    lines.append("- ")
    lines.append("")
    lines.append("### 4.2 场景规则")
    lines.append("")
    lines.append("> 🤖 系统自动汇总：来源为需求用户故事中沉淀的业务规则，按需求编号分组。")
    lines.append("")
    lines.append(render_auto_block("scenario_rules", ""))
    lines.append("")
    lines.append("## 5. 优化与变更轨迹")
    lines.append("")
    lines.append("> 🤖 系统自动汇总：来源为带变更标记的已关闭需求。")
    lines.append("")
    lines.append(render_auto_block("change_log", ""))
    lines.append("")
    lines.append("## 6. 关联交付物")
    lines.append("")
    lines.append("> 🤖 系统自动汇总：来源为需求直挂交付物与已归档操作手册。")
    lines.append("")
    lines.append(render_auto_block("deliverables", ""))
    lines.append("")
    lines.append("## 7. 关联过程性内容索引")
    lines.append("")
    lines.append("> 以下链接由系统自动维护，删除或新增关联时会同步更新。")
    lines.append("")
    lines.append("## 8. 相关子笔记 MOC")
    lines.append("")
    lines.append("## 9. 业务全过程时间线")
    lines.append("")
    lines.append("> 🤖 系统自动汇总：该业务全部关联事件（需求/会议/运营工单/交付物）按发生日期倒序。")
    lines.append("")
    lines.append(render_auto_block("timeline", ""))
    lines.append("")
    lines.append("## 10. 关联系统与接口（人工维护）")
    lines.append("")
    lines.append("- ")
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
        note_type="main",
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
        "note_type": getattr(item, "note_type", "sub"),
        "summary": item.summary,
    }


def ensure_domain_main_note(db: Session, domain_code: str) -> dict:
    """确保某业务领域存在唯一主笔记（系统自动保活）；不存在则按标准模板创建。

    返回 {created: bool, item: {...}}。
    """
    domain = (
        db.query(PmwbBusinessDomain)
        .filter(PmwbBusinessDomain.domain_code == domain_code)
        .first()
    )
    if not domain:
        raise NotFoundException(f"业务领域 '{domain_code}' 不存在")
    existing = (
        db.query(PmwbKnowledgeItem)
        .filter(PmwbKnowledgeItem.domain_code == domain_code)
        .filter(PmwbKnowledgeItem.note_type == "main")
        .first()
    )
    if existing:
        return {"created": False, "item": _item_dict(existing)}
    return create_main_note(db, domain_code)


def ensure_domain_main_notes(db: Session) -> dict:
    """为所有「有子笔记但缺主笔记」的启用业务领域自动保活主笔记，并重建子笔记摘要索引。"""
    domains = db.query(PmwbBusinessDomain).filter(PmwbBusinessDomain.enabled == True).all()
    created = 0
    ensured = 0
    for d in domains:
        has_sub = (
            db.query(PmwbKnowledgeItem.id)
            .filter(PmwbKnowledgeItem.domain_code == d.domain_code)
            .filter(PmwbKnowledgeItem.note_type != "main")
            .first()
        )
        main = (
            db.query(PmwbKnowledgeItem.id)
            .filter(PmwbKnowledgeItem.domain_code == d.domain_code)
            .filter(PmwbKnowledgeItem.note_type == "main")
            .first()
        )
        if has_sub and not main:
            ensure_domain_main_note(db, d.domain_code)
            created += 1
        if main or (has_sub and not main):
            rebuild_main_note_subnotes(db, d.domain_code)
            ensured += 1
    return {
        "domains_scanned": len(domains),
        "main_notes_created": created,
        "main_notes_ensured": ensured,
    }


def rebuild_main_note_subnotes(db: Session, domain_code: str) -> bool:
    """重建主笔记正文「## 相关子笔记 MOC」章节：聚合该领域全部子笔记的标题+摘要（自动汇总）。"""
    main = (
        db.query(PmwbKnowledgeItem)
        .filter(PmwbKnowledgeItem.domain_code == domain_code)
        .filter(PmwbKnowledgeItem.note_type == "main")
        .first()
    )
    if not main or not main.obsidian_path:
        return False
    sub_notes = (
        db.query(PmwbKnowledgeItem)
        .filter(PmwbKnowledgeItem.domain_code == domain_code)
        .filter(PmwbKnowledgeItem.note_type != "main")
        .order_by(PmwbKnowledgeItem.updated_at.desc())
        .all()
    )
    lines = [
        "> 以下子笔记摘要由系统自动维护（按更新时间倒序），新增/删除子笔记或改动摘要时同步更新。",
        "",
    ]
    if not sub_notes:
        lines.append("_暂无子笔记_")
        lines.append("")
    else:
        for n in sub_notes:
            summary = (n.summary or "").strip().replace("\n", " ")
            lines.append(f"- **[{n.title}]({n.obsidian_path})** — {summary or '（无摘要）'}")
        lines.append("")
    section = "\n".join(lines).rstrip()
    content = read_markdown(main.obsidian_path)
    if content is None:
        return False
    new_content = append_or_replace_section(content, "相关子笔记 MOC", section)
    if new_content != content:
        write_markdown(main.obsidian_path, new_content)
    return True


# ---------------------------------------------------------------------------
# kc4-2：主笔记自动区回流引擎（缺口 A 修复）
# ---------------------------------------------------------------------------

def _parse_json_list(raw) -> List[str]:
    """解析 JSON 数组字段（用户故事 rules / acceptance），容错为纯文本换行拆分。"""
    if not raw:
        return []
    text = raw if isinstance(raw, str) else str(raw)
    text = text.strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            import json

            data = json.loads(text)
            if isinstance(data, list):
                return [str(x).strip() for x in data if str(x).strip()]
        except (ValueError, TypeError):
            pass
    return [ln.strip("-• \t") for ln in text.splitlines() if ln.strip("-• \t")]


def _req_label(req: PmwbRequirementExt) -> str:
    name = (req.req_name or "").strip()
    return f"{req.req_id} {name}".strip()


def _md_cell(text: Optional[str], limit: int = 120) -> str:
    """转义 Markdown 表格单元格内容（去换行、转义竖线、限长）。"""
    s = (text or "").replace("\n", " ").replace("\r", " ").replace("|", "\\|").strip()
    if len(s) > limit:
        s = s[: limit - 1] + "…"
    return s or "—"


def _fmt_date(d) -> str:
    if not d:
        return "—"
    try:
        return d.strftime("%Y-%m-%d")
    except AttributeError:
        return str(d)


def _build_product_block(reqs: List[PmwbRequirementExt]) -> str:
    """§2.1 产商品：仅「已关闭 + 勾选产商品变更」的需求（保守回写，防误写业务事实）。"""
    rows = [r for r in reqs if r.status == "closed" and (r.product_changed or 0) == 1]
    if not rows:
        return "_暂无产商品体系变更记录（仅收录「已关闭且标记产商品变更」的需求）_"
    lines = [
        "| 需求编号 | 需求名称 | 变更要点 | 版本要求 |",
        "|----------|----------|----------|----------|",
    ]
    for r in sorted(rows, key=lambda x: (x.version_required_date or date.min), reverse=True):
        lines.append(
            f"| [[{r.req_id}]] | {_md_cell(r.req_name)} | "
            f"{_md_cell(r.description or r.background, 80)} | {_fmt_date(r.version_required_date)} |"
        )
    return "\n".join(lines)


def _build_process_block(reqs: List[PmwbRequirementExt]) -> str:
    """§3.2 业务流程：仅「已关闭 + 勾选流程变更」的需求。"""
    rows = [r for r in reqs if r.status == "closed" and (r.process_changed or 0) == 1]
    if not rows:
        return "_暂无业务流程变更记录（仅收录「已关闭且标记流程变更」的需求）_"
    lines = [
        "| 需求编号 | 需求名称 | 流程变更说明 | 涉及系统 | 版本要求 |",
        "|----------|----------|--------------|----------|----------|",
    ]
    for r in sorted(rows, key=lambda x: (x.version_required_date or date.min), reverse=True):
        lines.append(
            f"| [[{r.req_id}]] | {_md_cell(r.req_name)} | "
            f"{_md_cell(r.description or r.clarification, 80)} | {_md_cell(r.system_name, 40)} | "
            f"{_fmt_date(r.version_required_date)} |"
        )
    return "\n".join(lines)


def _build_scenario_rules_block(db: Session, reqs: List[PmwbRequirementExt]) -> str:
    """§4.2 场景规则：用户故事 rules 非空即回写（结构化字段、带需求编号可追溯，风险低）。"""
    req_ids = [r.req_id for r in reqs]
    if not req_ids:
        return "_暂无场景规则_"
    stories = (
        db.query(PmwbUserStory)
        .filter(PmwbUserStory.req_id.in_(req_ids))
        .order_by(PmwbUserStory.req_id, PmwbUserStory.seq)
        .all()
    )
    name_map = {r.req_id: (r.req_name or "") for r in reqs}
    grouped: Dict[str, List[str]] = {}
    for s in stories:
        rules = _parse_json_list(s.rules)
        if not rules:
            continue
        grouped.setdefault(s.req_id, [])
        for rule in rules:
            entry = f"{rule}（来源：故事{s.seq} {(s.title or '').strip()}）".rstrip("（来源： ）")
            if entry not in grouped[s.req_id]:
                grouped[s.req_id].append(entry)
    if not grouped:
        return "_暂无场景规则（需求用户故事中尚未沉淀业务规则）_"
    lines: List[str] = []
    for req_id in sorted(grouped.keys(), reverse=True):
        title = name_map.get(req_id) or ""
        lines.append(f"#### {req_id} {title}".rstrip())
        for rule in grouped[req_id]:
            lines.append(f"- {rule}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _build_change_log_block(reqs: List[PmwbRequirementExt], links: List[PmwbKnowledgeLink]) -> str:
    """§5 变更轨迹：带变更标记的已关闭需求，按事件日期倒序。"""
    link_date = {
        lk.source_id: lk.event_date
        for lk in links
        if lk.source_type == "requirement" and lk.event_date
    }
    rows = [
        r
        for r in reqs
        if r.status == "closed" and ((r.product_changed or 0) == 1 or (r.process_changed or 0) == 1)
    ]
    if not rows:
        return "_暂无变更轨迹_"

    def _key(r: PmwbRequirementExt):
        return link_date.get(r.req_id) or r.version_required_date or date.min

    lines = [
        "| 日期 | 变更内容 | 变更类型 | 影响范围 | 关联需求 |",
        "|------|----------|----------|----------|----------|",
    ]
    for r in sorted(rows, key=_key, reverse=True):
        kinds = []
        if (r.product_changed or 0) == 1:
            kinds.append("产商品")
        if (r.process_changed or 0) == 1:
            kinds.append("业务流程")
        lines.append(
            f"| {_fmt_date(_key(r) if _key(r) != date.min else None)} | {_md_cell(r.req_name, 60)} | "
            f"{'/'.join(kinds)} | {_md_cell(r.system_name, 40)} | [[{r.req_id}]] |"
        )
    return "\n".join(lines)


def _build_deliverables_block(reqs: List[PmwbRequirementExt], links: List[PmwbKnowledgeLink]) -> str:
    """§6 交付物：需求已归档操作手册 + deliverable 类关联（客观记录，全部放开）。"""
    lines = [
        "| 交付物 | 类型 | 存储路径 | 来源需求 | 归档日期 |",
        "|--------|------|----------|----------|----------|",
    ]
    count = 0
    for r in reqs:
        if (r.manual_archived or 0) == 1 and r.manual_obsidian_path:
            lines.append(
                f"| {_md_cell(r.manual_obsidian_path.split('/')[-1], 60)} | 操作手册 | "
                f"`{_md_cell(r.manual_obsidian_path, 90)}` | [[{r.req_id}]] | "
                f"{_fmt_date(r.updated_at)} |"
            )
            count += 1
    for lk in links:
        if lk.source_type != "deliverable" and lk.event_type != "delivery":
            continue
        if lk.source_type == "requirement" and lk.event_type == "delivery":
            src = f"[[{lk.source_id}]]"
        else:
            src = _md_cell(lk.source_id, 40)
        lines.append(
            f"| {_md_cell(lk.summary or lk.note, 60)} | 交付物 | — | {src} | {_fmt_date(lk.event_date)} |"
        )
        count += 1
    if count == 0:
        return "_暂无关联交付物_"
    return "\n".join(lines)


def _build_timeline_block(links: List[PmwbKnowledgeLink]) -> str:
    """§9 业务时间线：全部关联事件按 event_date 倒序（客观记录，全部放开）。

    这是"以业务为中心看历史各时间点干了什么"的核心呈现。
    """
    if not links:
        return "_暂无关联事件_"
    ordered = sorted(links, key=lambda x: (x.event_date or date.min), reverse=True)
    label_map = {
        "requirement": "需求",
        "meeting": "会议",
        "operation": "运营工单",
        "ticket": "开发工单",
        "deliverable": "交付物",
        "delivery": "交付归档",
        "key_work": "重点工作",
        "rule": "业务规则",
        "manual": "操作手册",
    }
    lines: List[str] = []
    current_month = None
    for lk in ordered:
        d = lk.event_date
        month = d.strftime("%Y-%m") if d else "未知日期"
        if month != current_month:
            lines.append(f"### {month}")
            current_month = month
        kind = label_map.get(lk.event_type or lk.source_type, lk.event_type or lk.source_type or "事件")
        desc = (lk.summary or lk.note or "").replace("\n", " ").strip()
        suffix = f" — {desc}" if desc else ""
        lines.append(f"- `{_fmt_date(d)}` **[{kind}]** [[{lk.source_id}]]{suffix}")
    return "\n".join(lines)


def sync_main_note_from_links(db: Session, domain_code: str) -> dict:
    """把关联表中的过程性事实回流到业务知识主笔记「自动区」（kc4-2 核心）。

    分级回写策略（防误写业务事实，见 docs/knowledge_center_redesign_v2.md §10）：
    - 产商品 / 业务流程：仅 `status='closed'` 且勾选对应变更标记的需求才回写；
    - 场景规则：用户故事 rules 非空即回写（结构化、可追溯）；
    - 交付物 / 时间线：客观记录，全部放开；
    - **人工区（业务概述 / 通用规则 / 资费 / SOP细节 / 关联系统）永不触碰**。

    返回 {domain_code, main_note_path, blocks_written, changed}。
    """
    ensured = ensure_domain_main_note(db, domain_code)
    main = (
        db.query(PmwbKnowledgeItem)
        .filter(PmwbKnowledgeItem.domain_code == domain_code)
        .filter(PmwbKnowledgeItem.note_type == "main")
        .first()
    )
    if not main or not main.obsidian_path:
        return {
            "domain_code": domain_code,
            "main_note_path": None,
            "blocks_written": [],
            "changed": False,
            "message": "主笔记不存在或缺少 Obsidian 路径",
        }

    content = read_markdown(main.obsidian_path)
    if content is None:
        return {
            "domain_code": domain_code,
            "main_note_path": main.obsidian_path,
            "blocks_written": [],
            "changed": False,
            "message": "主笔记文件未找到（可能被移动或删除）",
        }

    reqs = (
        db.query(PmwbRequirementExt)
        .filter(PmwbRequirementExt.domain_code == domain_code)
        .all()
    )
    links = (
        db.query(PmwbKnowledgeLink)
        .filter(PmwbKnowledgeLink.domain_code == domain_code)
        .all()
    )

    bodies = {
        "product": _build_product_block(reqs),
        "process": _build_process_block(reqs),
        "scenario_rules": _build_scenario_rules_block(db, reqs),
        "change_log": _build_change_log_block(reqs, links),
        "deliverables": _build_deliverables_block(reqs, links),
        "timeline": _build_timeline_block(links),
    }

    original = content
    written = []
    for key, body in bodies.items():
        new_content = upsert_auto_block(content, key, body, anchor_heading=AUTO_BLOCKS[key])
        if new_content != content:
            written.append(key)
        content = new_content

    changed = content != original
    if changed:
        write_markdown(main.obsidian_path, content)
        try:
            fm = read_frontmatter(main.obsidian_path)
            fm["auto_sections_generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            write_frontmatter(main.obsidian_path, fm)
        except Exception:
            pass

    return {
        "domain_code": domain_code,
        "main_note_path": main.obsidian_path,
        "main_note_created": ensured.get("created", False),
        "blocks_written": written,
        "changed": changed,
        "requirements_scanned": len(reqs),
        "links_scanned": len(links),
    }


def sync_main_note_safe(db: Session, domain_code: Optional[str]) -> None:
    """沉淀动作完成后的自动回流（失败不影响主流程，仅静默跳过）。"""
    if not domain_code:
        return
    try:
        sync_main_note_from_links(db, domain_code)
    except Exception:
        pass
