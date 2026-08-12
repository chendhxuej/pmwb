"""知识笔记与过程性对象（需求/工单/会议/交付物）的多对多关联服务。

关联关系以数据库 `pmwb_knowledge_link` 为权威源；同时在被关联的知识笔记中
维护一个「## 关联对象」章节（人类可读的反向链接），便于在 Obsidian 中直接查看
"这个业务到底关联了哪些需求/工单/会议"。
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from core.exceptions import NotFoundException
from db.models import PmwbKnowledgeItem, PmwbKnowledgeLink
from services.knowledge import knowledge_item_service
from utils.obsidian import (
    read_markdown,
    write_markdown,
    replace_section,
    parse_title,
)


# 来源类型中文名（用于笔记中的可读展示）
SOURCE_LABELS = {
    "requirement": "需求",
    "ticket": "开发工单",
    "operation": "运营工单",
    "meeting": "会议",
    "deliverable": "交付物",
    "key_work": "重点工作",
}


def _source_label(source_type: str, source_id: str) -> str:
    label = SOURCE_LABELS.get(source_type, source_type)
    return f"{label} {source_id}"


def list_links(db: Session, source_type: str, source_id: str) -> List[dict]:
    """列出某来源对象已关联的知识条目（含索引信息）。"""
    rows = (
        db.query(PmwbKnowledgeLink)
        .filter(
            PmwbKnowledgeLink.source_type == source_type,
            PmwbKnowledgeLink.source_id == str(source_id),
        )
        .all()
    )
    result = []
    for r in rows:
        item = db.query(PmwbKnowledgeItem).filter(PmwbKnowledgeItem.id == r.knowledge_item_id).first()
        if not item:
            continue
        result.append(
            {
                "link_id": r.id,
                "knowledge_item_id": r.knowledge_item_id,
                "item_id": item.item_id,
                "title": item.title,
                "obsidian_path": item.obsidian_path,
                "domain_code": item.domain_code,
                "link_type": r.link_type,
                "note": r.note,
                "source_type": r.source_type,
                "source_id": r.source_id,
            }
        )
    return result


def _get_or_create_item_by_path(db: Session, obsidian_path: str, domain_code: Optional[str] = None) -> PmwbKnowledgeItem:
    existing = (
        db.query(PmwbKnowledgeItem)
        .filter(PmwbKnowledgeItem.obsidian_path == obsidian_path)
        .first()
    )
    if existing:
        return existing
    content = read_markdown(obsidian_path) or ""
    title = parse_title(content) or obsidian_path.split("/")[-1].replace(".md", "")
    return knowledge_item_service.create(
        db,
        {
            "item_id": f"KNOW-AUTO-{abs(hash(obsidian_path)) % 100000:05d}",
            "title": title,
            "category": "关联",
            "sub_category": "业务知识",
            "tags": "关联",
            "obsidian_path": obsidian_path,
            "source_type": "manual",
            "source_id": obsidian_path,
            "domain_code": domain_code,
            "summary": title,
        },
    )


def link_to_item(
    db: Session,
    source_type: str,
    source_id: str,
    knowledge_item_id: int,
    link_type: str = "main",
    note: Optional[str] = None,
    domain_code: Optional[str] = None,
) -> dict:
    """把某来源对象关联到指定知识条目（幂等：已存在则返回已有记录）。"""
    item = db.query(PmwbKnowledgeItem).filter(PmwbKnowledgeItem.id == knowledge_item_id).first()
    if not item:
        raise NotFoundException(f"知识条目不存在：id={knowledge_item_id}")

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
            db.commit()
        _sync_backlinks(db, existing.knowledge_item_id)
        return _serialize(existing, item)

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
    _sync_backlinks(db, knowledge_item_id)
    return _serialize(link, item)


def link_to_path(
    db: Session,
    source_type: str,
    source_id: str,
    obsidian_path: str,
    link_type: str = "main",
    note: Optional[str] = None,
    domain_code: Optional[str] = None,
) -> dict:
    """按 Obsidian 路径关联到已有/新建知识条目。"""
    item = _get_or_create_item_by_path(db, obsidian_path, domain_code)
    return link_to_item(db, source_type, source_id, item.id, link_type, note, domain_code)


def unlink(db: Session, link_id: int) -> bool:
    """取消关联，并清理知识笔记中的反向链接章节。"""
    link = db.query(PmwbKnowledgeLink).filter(PmwbKnowledgeLink.id == link_id).first()
    if not link:
        return False
    knowledge_item_id = link.knowledge_item_id
    db.delete(link)
    db.commit()
    _sync_backlinks(db, knowledge_item_id)
    return True


def _serialize(link: PmwbKnowledgeLink, item: PmwbKnowledgeItem) -> dict:
    return {
        "link_id": link.id,
        "knowledge_item_id": link.knowledge_item_id,
        "item_id": item.item_id,
        "title": item.title,
        "obsidian_path": item.obsidian_path,
        "domain_code": item.domain_code,
        "link_type": link.link_type,
        "note": link.note,
        "source_type": link.source_type,
        "source_id": link.source_id,
    }


def _sync_backlinks(db: Session, knowledge_item_id: int):
    """根据关联表重建知识笔记「## 关联对象」章节（权威源为 DB）。"""
    item = db.query(PmwbKnowledgeItem).filter(PmwbKnowledgeItem.id == knowledge_item_id).first()
    if not item or not item.obsidian_path:
        return
    content = read_markdown(item.obsidian_path)
    if content is None:
        return
    links = (
        db.query(PmwbKnowledgeLink)
        .filter(PmwbKnowledgeLink.knowledge_item_id == knowledge_item_id)
        .all()
    )
    if not links:
        # 无关联则移除该章节
        new_content = replace_section(content, "关联对象", "_NO_SECTION_")
        if "_NO_SECTION_" in new_content:
            # replace_section 不会真正删除，这里做整段移除
            new_content = _remove_section(content, "关联对象")
        write_markdown(item.obsidian_path, new_content)
        return
    bullets = []
    for lk in links:
        label = _source_label(lk.source_type, lk.source_id)
        extra = f"（{lk.note}）" if lk.note else ""
        bullets.append(f"- {label}{extra}")
    section_body = "本业务知识关联的过程性对象：\n\n" + "\n".join(bullets)
    new_content = replace_section(content, "关联对象", section_body)
    write_markdown(item.obsidian_path, new_content)


def _remove_section(content: str, heading: str) -> str:
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
