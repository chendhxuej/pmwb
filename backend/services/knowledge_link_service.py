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
import json
import re
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
    extract_section,
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

# 自动区标记块（顺序即模板与同步引擎约定）
AUTO_BLOCK_KEYS = ["product", "process", "scenario_rules", "change_log", "deliverables", "timeline"]


def _auto_block(key: str, body: str = "") -> str:
    """生成一对自动区标记包裹的块（模板初始化用，body 为空即空块）。"""
    return f"<!-- PMWB:AUTO:BEGIN key={key} -->\n{body}<!-- PMWB:AUTO:END key={key} -->"


def _replace_auto_block(content: str, key: str, body: str) -> str:
    """替换主笔记中指定 key 的自动区内容（保留标记，不匹配则原样返回）。

    仅改写 BEGIN/END 标记之间的文本，人工区（标记之外）永不被动。幂等：
    重复调用结果一致，不会产生重复标记。
    """
    begin = f"<!-- PMWB:AUTO:BEGIN key={key} -->"
    end = f"<!-- PMWB:AUTO:END key={key} -->"
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.DOTALL)
    replacement = f"{begin}\n{body.rstrip(chr(10))}\n{end}"
    return pattern.sub(replacement, content, count=1)


def build_main_note_markdown(
    domain: PmwbBusinessDomain,
    item_id: str,
    created_date: str,
) -> str:
    """按方案 §4.1/4.2 生成业务知识主笔记 Markdown。

    结构：

    - 人工基线章节（业务概述/产商品资费/服务场景/通用规则/关联索引/MOC）由人维护；
    - 自动区（AUTO 标记块）承载系统回流内容，人工区永不被同步覆盖。
    """
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
    lines.append("### 2.1 产品矩阵（人工维护）")
    lines.append("")
    lines.append("| 产品 | 定位 | 目标客户 | 备注 |")
    lines.append("|------|------|----------|------|")
    lines.append("|      |      |          |      |")
    lines.append("")
    lines.append("### 2.2 资费与计费规则（人工维护）")
    lines.append("")
    lines.append("- ")
    lines.append("")
    lines.append("### 2.3 产品变更（自动区）")
    lines.append("")
    lines.append(_auto_block("product"))
    lines.append("")
    lines.append("## 3. 客户服务场景 SOP")
    lines.append("")
    lines.append("### 3.1 常见服务场景（人工维护）")
    lines.append("")
    lines.append("| 场景 | 责任角色 | 关键步骤 | SLA |")
    lines.append("|------|----------|----------|-----|")
    lines.append("|      |          |          |     |")
    lines.append("")
    lines.append("### 3.2 流程变更（自动区）")
    lines.append("")
    lines.append(_auto_block("process"))
    lines.append("")
    lines.append("## 4. 业务规则")
    lines.append("")
    lines.append("### 4.1 通用规则（人工维护）")
    lines.append("")
    lines.append("- ")
    lines.append("")
    lines.append("### 4.2 场景规则（自动区）")
    lines.append("")
    lines.append(_auto_block("scenario_rules"))
    lines.append("")
    lines.append("## 5. 优化与变更轨迹（自动区）")
    lines.append("")
    lines.append(_auto_block("change_log"))
    lines.append("")
    lines.append("## 6. 关联交付物（自动区）")
    lines.append("")
    lines.append(_auto_block("deliverables"))
    lines.append("")
    lines.append("## 7. 关联过程性内容索引")
    lines.append("")
    lines.append("> 以下链接由系统自动维护，删除或新增关联时会同步更新。")
    lines.append("")
    lines.append("## 8. 相关子笔记 MOC")
    lines.append("")
    lines.append("")
    lines.append("## 9. 业务全过程时间线（自动区）")
    lines.append("")
    lines.append(_auto_block("timeline"))
    lines.append("")
    return "\n".join(lines) + "\n"


# 主笔记标准结构章节定义（编号前缀用于跨域措辞差异匹配）。
# kind: baseline(人工维护) / auto(系统自动) / system(系统维护)，对应前端徽标颜色。
MAIN_NOTE_SECTIONS = [
    {"prefix": "1", "key": "overview", "kind": "baseline", "kind_label": "人工维护"},
    {"prefix": "2.1", "key": "product_matrix", "kind": "baseline", "kind_label": "人工维护"},
    {"prefix": "2.2", "key": "pricing", "kind": "baseline", "kind_label": "人工维护"},
    {"prefix": "2.3", "key": "product_change", "kind": "auto", "kind_label": "系统自动"},
    {"prefix": "3.1", "key": "service_scenario", "kind": "baseline", "kind_label": "人工维护"},
    {"prefix": "3.2", "key": "process_change", "kind": "auto", "kind_label": "系统自动"},
    {"prefix": "4.1", "key": "general_rules", "kind": "baseline", "kind_label": "人工维护"},
    {"prefix": "4.2", "key": "scenario_rules", "kind": "auto", "kind_label": "系统自动"},
    {"prefix": "5", "key": "change_track", "kind": "auto", "kind_label": "系统自动"},
    {"prefix": "6", "key": "deliverables", "kind": "auto", "kind_label": "系统自动"},
    {"prefix": "7", "key": "related_index", "kind": "system", "kind_label": "系统维护"},
    {"prefix": "8", "key": "moc", "kind": "system", "kind_label": "系统维护"},
    {"prefix": "9", "key": "timeline", "kind": "auto", "kind_label": "系统自动"},
    {"prefix": "10", "key": "related_systems", "kind": "baseline", "kind_label": "人工维护"},
]


def get_main_note_structured(db: Session, domain_code: str) -> Dict:
    """读取某业务领域主笔记，按标准结构返回分章节内容。

    用于前端「知识标准化管理（主笔记标准结构）」展示。章节通过编号前缀
    匹配（如 "2.1"），兼容各域主笔记措辞差异（「系统自动」/「自动区」等）。
    """
    item = (
        db.query(PmwbKnowledgeItem)
        .filter(PmwbKnowledgeItem.domain_code == domain_code)
        .filter(PmwbKnowledgeItem.note_type == "main")
        .first()
    )
    if not item or not item.obsidian_path:
        return {"domain_code": domain_code, "title": "", "obsidian_path": "", "sections": []}
    content = read_markdown(item.obsidian_path) or ""

    # 解析全部标题（层级 + 文本）
    headings = []
    for line in content.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if m:
            headings.append(m.group(2).strip())

    sections = []
    for sec in MAIN_NOTE_SECTIONS:
        matched = None
        for text in headings:
            pm = re.match(r"^(\d+(?:\.\d+)*)\b\s*(.*)$", text)
            if pm and pm.group(1) == sec["prefix"]:
                matched = text
                break
        if not matched:
            sections.append({
                "key": sec["key"],
                "title": "",
                "kind": sec["kind"],
                "kind_label": sec["kind_label"],
                "markdown": "_暂无数据_",
            })
            continue
        md = extract_section(content, matched) or "_暂无数据_"
        sections.append({
            "key": sec["key"],
            "title": matched,
            "kind": sec["kind"],
            "kind_label": sec["kind_label"],
            "markdown": md,
        })
    return {
        "domain_code": domain_code,
        "title": item.title or "",
        "obsidian_path": item.obsidian_path,
        "sections": sections,
    }


def sync_main_note_from_links(db: Session, domain_code: str) -> dict:
    """把需求/用户故事/关联事件回流到主笔记的自动区，人工区零覆盖，幂等。

    分级策略（kc4-2 保守回流）：

    - 产商品区：已关闭且 product_changed=1 的需求；
    - 业务流程区：已关闭且 process_changed=1 的需求；
    - 变更轨迹：已关闭且 (product_changed|process_changed) 的需求；
    - 场景规则：用户故事 rules 非空（不依赖需求状态，低风险结构化）；
    - 时间线：该 domain 全部 knowledge_link，按 event_date 倒序；
    - 交付物：已关闭需求的 deliverables JSON。

    返回 {domain_code, changed, blocks_written, main_note_path}。
    """
    item = (
        db.query(PmwbKnowledgeItem)
        .filter(PmwbKnowledgeItem.domain_code == domain_code)
        .filter(PmwbKnowledgeItem.note_type == "main")
        .first()
    )
    if not item:
        return {
            "domain_code": domain_code,
            "changed": False,
            "blocks_written": [],
            "main_note_path": None,
            "error": "no_main_note",
        }

    content = read_markdown(item.obsidian_path) or ""
    blocks_written: List[str] = []

    reqs = (
        db.query(PmwbRequirementExt)
        .filter(PmwbRequirementExt.domain_code == domain_code)
        .all()
    )

    # 产商品区：已关闭 + 勾选产商品变更
    product_lines = []
    for r in reqs:
        if r.status == "closed" and (r.product_changed or 0) == 1:
            ver = r.version_required_date.strftime("%Y-%m-%d") if r.version_required_date else "未定"
            product_lines.append(f"- [{r.req_id}] {r.req_name or ''} — 版本要求日 {ver}")
    product_body = "\n".join(product_lines) if product_lines else "_暂无产商品变更_"

    # 业务流程区：已关闭 + 勾选流程变更
    process_lines = []
    for r in reqs:
        if r.status == "closed" and (r.process_changed or 0) == 1:
            process_lines.append(f"- [{r.req_id}] {r.req_name or ''}（流程变更）")
    process_body = "\n".join(process_lines) if process_lines else "_暂无流程变更_"

    # 变更轨迹：已关闭 + 任一变更标记
    change_lines = []
    for r in reqs:
        if r.status == "closed" and ((r.product_changed or 0) == 1 or (r.process_changed or 0) == 1):
            kind = "业务流程" if (r.process_changed or 0) == 1 else "产商品"
            ver = r.version_required_date.strftime("%Y-%m-%d") if r.version_required_date else "未定"
            change_lines.append(f"- {ver} · {kind} · [{r.req_id}] {r.req_name or ''}")
    change_body = "\n".join(change_lines) if change_lines else "_暂无变更轨迹_"

    # 交付物：已关闭需求的 deliverables JSON
    deliv_lines = []
    for r in reqs:
        if r.status == "closed":
            try:
                ds = json.loads(r.deliverables) if r.deliverables else []
            except Exception:
                ds = []
            if isinstance(ds, list):
                for d in ds:
                    if isinstance(d, dict):
                        deliv_lines.append(
                            f"- [{r.req_id}] {d.get('file_name', '')}（{d.get('note', '')}）"
                        )
    deliv_body = "\n".join(deliv_lines) if deliv_lines else "_暂无交付物_"

    # 场景规则：用户故事 rules 非空（不依赖需求状态）
    rules_lines = []
    for r in reqs:
        stories = (
            db.query(PmwbUserStory).filter(PmwbUserStory.req_id == r.req_id).all()
        )
        for st in stories:
            if st.rules:
                try:
                    arr = json.loads(st.rules)
                except Exception:
                    arr = []
                if isinstance(arr, list):
                    for rule in arr:
                        rules_lines.append(f"- [{r.req_id}] {rule}")
    rules_body = "\n".join(rules_lines) if rules_lines else "_暂无场景规则_"

    # 时间线：该 domain 全部关联事件，按 event_date 倒序
    tl = business_timeline(db, domain_code)
    tl_events = tl.get("events", [])
    tl_lines = []
    for e in tl_events:
        date_s = e.get("event_date") or "未定日期"
        title = e.get("source_title") or e.get("source_id")
        tl_lines.append(
            f"- {date_s} · [{e.get('event_label')}] {title}（{e.get('summary') or ''}）"
        )
    tl_body = "\n".join(tl_lines) if tl_lines else "_暂无关联事件_"

    # 应用替换（仅更改标记内文本）
    new_content = content
    block_map = {
        "product": product_body,
        "process": process_body,
        "change_log": change_body,
        "deliverables": deliv_body,
        "scenario_rules": rules_body,
        "timeline": tl_body,
    }
    for key, body in block_map.items():
        new_content = _replace_auto_block(new_content, key, body)
        if not body.startswith("_暂无"):
            blocks_written.append(key)

    changed = False
    if new_content != content:
        write_markdown(item.obsidian_path, new_content)
        changed = True

    return {
        "domain_code": domain_code,
        "changed": changed,
        "blocks_written": blocks_written,
        "main_note_path": item.obsidian_path,
    }



# source_type -> 时间线事件中文标签
EVENT_LABELS = {
    "requirement": "需求",
    "ticket": "开发工单",
    "meeting": "会议",
    "operation": "运营",
    "deliverable": "交付物",
    "key_work": "重点工作",
}

# source_type -> 前端跳转路由
SOURCE_ROUTES = {
    "requirement": "/requirement-delivery",
    "ticket": "/dev-tickets",
    "meeting": "/meeting/list",
    "operation": "/operation/overview",
    "deliverable": "/requirements",
    "key_work": "/key-works",
}


def _resolve_source_title(db: Session, source_type: str, source_id: str):
    """反查关联源记录的标题，用于时间线展示。"""
    if source_type == "requirement":
        r = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == source_id).first()
        return r.req_name if r else None
    if source_type == "meeting":
        m = db.query(PmwbMeeting).filter(PmwbMeeting.meeting_id == source_id).first()
        return m.title if m else None
    if source_type == "operation":
        o = db.query(PmwbOperationIssue).filter(PmwbOperationIssue.issue_no == source_id).first()
        return o.title if o else None
    if source_type == "ticket":
        t = db.query(PmwbDevTicket).filter(PmwbDevTicket.id == source_id).first()
        return t.title if t else None
    if source_type == "key_work":
        k = db.query(PmwbKeyWork).filter(PmwbKeyWork.id == source_id).first()
        return k.title if k else None
    return None


def _ticket_event(source_type: str, source_id, title, event_dt, summary) -> Dict:
    """把一条「按 domain_code 归属的工单」规范成与时间线事件同构的字典。"""
    et = source_type
    label = EVENT_LABELS.get(et) or et
    route = SOURCE_ROUTES.get(source_type, "")
    ev_date = event_dt.strftime("%Y-%m-%d") if event_dt else None
    return {
        "source_type": source_type,
        "source_id": str(source_id),
        "event_type": et,
        "event_label": label,
        "source_title": title,
        "source_route": route,
        "obsidian_path": None,
        "knowledge_title": None,
        "event_date": ev_date,
        "month": event_dt.strftime("%Y-%m") if event_dt else None,
        "summary": summary,
    }


def _collect_domain_tickets(db: Session, domain_code: str, covered: set) -> List[Dict]:
    """收集按 domain_code 归属但未显式建 knowledge_link 的工单（需求/会议/运营）。

    与 business_timeline API 同源，保证「知识标准化管理」主笔记 §9 时间线与
    时间线 API 一致：既含显式 knowledge_link，也含按 domain_code 归属但
    未显式建关联的工单（去重由 covered 集合控制）。
    """
    out = []
    for r in db.query(PmwbRequirementExt).filter(PmwbRequirementExt.domain_code == domain_code).all():
        sid = r.req_id
        if ("requirement", str(sid)) in covered:
            continue
        out.append(_ticket_event("requirement", sid, r.req_name, r.created_at, ""))
    for m in db.query(PmwbMeeting).filter(PmwbMeeting.domain_code == domain_code).all():
        sid = m.meeting_id
        if ("meeting", str(sid)) in covered:
            continue
        out.append(_ticket_event("meeting", sid, m.title, m.start_time, m.summary or ""))
    for o in db.query(PmwbOperationIssue).filter(PmwbOperationIssue.domain_code == domain_code).all():
        sid = o.issue_no
        if ("operation", str(sid)) in covered:
            continue
        out.append(_ticket_event("operation", sid, o.title, o.created_at or o.discovery_date, o.situation_desc or ""))
    return out


def business_timeline(
    db: Session,
    domain_code: str,
    event_type: Optional[str] = None,
    limit: Optional[int] = None,
) -> Dict:
    """聚合某业务领域全过程时间线。

    数据权威源为 pmwb_knowledge_link（按 domain_code 过滤），每条关联事件携带
    源记录标题、跳转路由、关联主笔记路径，便于双向跳转。按 event_date 倒序，
    缺失日期垫底；类型统计始终为全量口径（供筛选器展示）。
    """
    domain = (
        db.query(PmwbBusinessDomain)
        .filter(PmwbBusinessDomain.domain_code == domain_code)
        .first()
    )
    domain_name = domain.domain_name if domain else domain_code

    links = (
        db.query(PmwbKnowledgeLink)
        .filter(PmwbKnowledgeLink.domain_code == domain_code)
        .all()
    )

    # 全量类型统计（不受过滤影响）
    type_counts: Dict[str, int] = {}
    events = []
    for link in links:
        et = link.event_type or link.source_type
        type_counts[et] = type_counts.get(et, 0) + 1
        item = (
            db.query(PmwbKnowledgeItem)
            .filter(PmwbKnowledgeItem.id == link.knowledge_item_id)
            .first()
        )
        label = EVENT_LABELS.get(et) or EVENT_LABELS.get(link.source_type) or link.source_type
        route = SOURCE_ROUTES.get(link.source_type, "")
        ev_date = link.event_date.strftime("%Y-%m-%d") if link.event_date else None
        events.append(
            {
                "source_type": link.source_type,
                "source_id": link.source_id,
                "event_type": et,
                "event_label": label,
                "source_title": _resolve_source_title(db, link.source_type, link.source_id),
                "source_route": route,
                "obsidian_path": item.obsidian_path if item else None,
                "knowledge_title": item.title if item else None,
                "event_date": ev_date,
                "month": link.event_date.strftime("%Y-%m") if link.event_date else None,
                "summary": link.summary or link.note,
            }
        )

    # 双源：纳入按 domain_code 归属但未显式建关联的工单（需求/会议/运营），
    # 与「知识标准化管理」主笔记 §9 时间线同源去重，保证两端一致。
    covered = {(link.source_type, str(link.source_id)) for link in links}
    for t in _collect_domain_tickets(db, domain_code, covered):
        type_counts[t["event_type"]] = type_counts.get(t["event_type"], 0) + 1
        events.append(t)

    # 倒序：event_date 大的在前，缺失日期垫底（空日期用 0 标志 + 小值保证垫底）
    def _sort_key(e):
        if e["event_date"] is None:
            return (0, "")
        return (1, e["event_date"])

    events.sort(key=_sort_key, reverse=True)

    # 按类型过滤（不影响类型统计）
    if event_type:
        events = [e for e in events if e["event_type"] == event_type]
    total = len(events)

    # 截断
    if limit is not None:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = None
    returned = total
    if limit is not None:
        returned = min(limit, total)
        events = events[:limit]

    event_types = [
        {"value": k, "count": v, "label": EVENT_LABELS.get(k, k)}
        for k, v in sorted(type_counts.items())
    ]

    return {
        "domain_code": domain_code,
        "domain_name": domain_name,
        "total": total,
        "returned": returned,
        "events": events,
        "event_types": event_types,
    }


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
