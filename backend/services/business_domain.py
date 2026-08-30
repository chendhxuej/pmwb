"""业务领域管理 — Service"""

from typing import List, Optional, Tuple

from sqlalchemy import cast, func, Integer, or_
from sqlalchemy.orm import Session

from core.exceptions import NotFoundException, ValidationException
from db.models import (
    PmwbBusinessDomain,
    PmwbDevTicket,
    PmwbKeyWork,
    PmwbKnowledgeItem,
    PmwbKnowledgeLink,
    PmwbMeeting,
    PmwbOperationIssue,
    PmwbRequirementExt,
    SentEmail,
)
from pathlib import Path

import logging
import os
import re
import uuid

from core.config import settings
from schemas.business_domain import (
    BusinessDomainCreate,
    BusinessDomainOut,
    BusinessDomainTreeNode,
    BusinessDomainUpdate,
    DomainLinkItem,
    DomainRelatedItem,
    DomainRelatedOut,
)
from services import obsidian_paths as op

logger = logging.getLogger(__name__)


def _to_out(domain: PmwbBusinessDomain, counts: Optional[Tuple[dict, dict, dict, dict]] = None) -> BusinessDomainOut:
    """模型 → 输出 Schema（包含 parent_domain_code 而非 parent_id）。"""
    parent_code = None
    if domain.parent_id:
        parent = domain.parent
        if parent:
            parent_code = parent.domain_code
    kc = rc = ic = mc = 0
    if counts:
        kc = counts[0].get(domain.domain_code, 0)
        rc = counts[1].get(domain.domain_code, 0)
        ic = counts[2].get(domain.domain_code, 0)
        mc = counts[3].get(domain.domain_code, 0)
    return BusinessDomainOut(
        id=domain.id,
        domain_code=domain.domain_code,
        domain_name=domain.domain_name,
        domain_group=domain.domain_group,
        vault_path=domain.vault_path,
        match_keywords=domain.match_keywords,
        parent_domain_code=parent_code,
        description=domain.description,
        sort_order=domain.sort_order or 0,
        enabled=bool(domain.enabled),
        created_at=domain.created_at,
        updated_at=domain.updated_at,
        knowledge_count=kc,
        req_count=rc,
        issue_count=ic,
        meeting_count=mc,
    )


def _group_by_domain(db: Session, model) -> dict:
    """统计某模型按 domain_code 分组的计数。"""
    return dict(
        db.query(model.domain_code, func.count(model.id))
        .filter(model.domain_code.isnot(None))
        .group_by(model.domain_code)
        .all()
    )


def _related_counts(db: Session) -> Tuple[dict, dict, dict, dict]:
    """聚合各业务领域的关联计数（知识/需求/运营工单/会议）。

    采用「源表直接归属 + 知识关联链接回溯」的并集口径：一条需求/运营工单/会议
    只要【自身 domain_code == 某领域】或【存在指向它的 pmwb_knowledge_link 且该
    link.domain_code == 某领域】，即计入该领域计数。这样领域浏览页的
    「需求/运营/会议」卡片与「时间线」口径一致，不会出现"时间线有、需求/运营空"。
    """
    k = _group_by_domain(db, PmwbKnowledgeItem)
    r_direct = _group_by_domain(db, PmwbRequirementExt)
    i_direct = _group_by_domain(db, PmwbOperationIssue)
    m_direct = _group_by_domain(db, PmwbMeeting)

    # 收集所有带 domain_code 的关联链接，按 source_type 归并 source_id
    links = (
        db.query(
            PmwbKnowledgeLink.source_type,
            PmwbKnowledgeLink.source_id,
            PmwbKnowledgeLink.domain_code,
        )
        .filter(PmwbKnowledgeLink.domain_code.isnot(None))
        .all()
    )
    req_ids: set = set()
    issue_ids: set = set()
    meet_ids: set = set()
    for st, sid, _ in links:
        if st == "requirement":
            req_ids.add(sid)
        elif st == "operation":
            try:
                issue_ids.add(int(sid))
            except (ValueError, TypeError):
                pass
        elif st == "meeting":
            try:
                meet_ids.add(int(sid))
            except (ValueError, TypeError):
                pass

    # 批量取源记录自身的 domain_code
    req_dc = (
        dict(
            db.query(PmwbRequirementExt.req_id, PmwbRequirementExt.domain_code)
            .filter(PmwbRequirementExt.req_id.in_(req_ids))
            .all()
        )
        if req_ids
        else {}
    )
    issue_dc = (
        dict(
            db.query(PmwbOperationIssue.id, PmwbOperationIssue.domain_code)
            .filter(PmwbOperationIssue.id.in_(issue_ids))
            .all()
        )
        if issue_ids
        else {}
    )
    meet_dc = (
        dict(
            db.query(PmwbMeeting.id, PmwbMeeting.domain_code)
            .filter(PmwbMeeting.id.in_(meet_ids))
            .all()
        )
        if meet_ids
        else {}
    )

    r = dict(r_direct)
    i = dict(i_direct)
    m = dict(m_direct)
    for st, sid, dc in links:
        if st == "requirement":
            src = req_dc.get(sid)
            target = r
        elif st == "operation":
            try:
                src = issue_dc.get(int(sid))
            except (ValueError, TypeError):
                src = None
            target = i
        elif st == "meeting":
            try:
                src = meet_dc.get(int(sid))
            except (ValueError, TypeError):
                src = None
            target = m
        else:
            continue
        # 源记录 domain_code 与该链接 domain_code 不同（含源记录为空）→ 计入增量，
        # 避免与「直接归属」重复计数
        if src != dc:
            target[dc] = target.get(dc, 0) + 1
    return k, r, i, m


def _resolve_parent(db: Session, parent_domain_code: Optional[str]) -> Optional[int]:
    """将 parent_domain_code 转成 parent_id。"""
    if not parent_domain_code:
        return None
    parent = db.query(PmwbBusinessDomain).filter(
        PmwbBusinessDomain.domain_code == parent_domain_code
    ).first()
    if not parent:
        raise ValidationException(message=f"父领域 '{parent_domain_code}' 不存在")
    return parent.id


# ---------------------------------------------------------------------------
# 只读查询（供前端组件使用）
# ---------------------------------------------------------------------------

def list_all(db: Session, enabled_only: bool = True) -> List[BusinessDomainOut]:
    """返回所有业务领域（扁平列表），并附带关联计数。"""
    q = db.query(PmwbBusinessDomain)
    if enabled_only:
        q = q.filter(PmwbBusinessDomain.enabled == True)
    q = q.order_by(PmwbBusinessDomain.domain_group, PmwbBusinessDomain.sort_order, PmwbBusinessDomain.id)
    counts = _related_counts(db)
    return [_to_out(d, counts) for d in q.all()]


def get_related(db: Session, domain_code: str) -> DomainRelatedOut:
    """聚合某业务领域关联的知识条目 / 需求 / 会议 / 运营工单，供知识中心按领域浏览详情。"""
    domain = db.query(PmwbBusinessDomain).filter(
        PmwbBusinessDomain.domain_code == domain_code
    ).first()
    if not domain:
        raise NotFoundException(message=f"业务领域 '{domain_code}' 不存在")

    k_items = (
        db.query(PmwbKnowledgeItem)
        .filter(PmwbKnowledgeItem.domain_code == domain_code)
        .order_by(PmwbKnowledgeItem.title)
        .all()
    )
    knowledge_items = [
        DomainRelatedItem(
            id=i.id,
            code=str(i.id),
            title=i.title or "",
            sub_title=i.sub_category,
            category=i.category,
            status=i.source_type,
            obsidian_path=i.obsidian_path,
        )
        for i in k_items
    ]

    # 主笔记体系：区分 main(业务知识主笔记) 与 sub(子笔记/过程性内容)
    main_note = next((i for i in k_items if i.note_type == "main"), None)
    sub_notes = [i for i in k_items if i.note_type != "main"]
    main_note_out = (
        DomainRelatedItem(
            id=main_note.id,
            code=str(main_note.id),
            title=main_note.title or "",
            sub_title=main_note.sub_category,
            category=main_note.category,
            status=main_note.source_type,
            obsidian_path=main_note.obsidian_path,
        )
        if main_note
        else None
    )
    sub_notes_out = [
        DomainRelatedItem(
            id=i.id,
            code=str(i.id),
            title=i.title or "",
            sub_title=i.sub_category,
            category=i.category,
            status=i.source_type,
            obsidian_path=i.obsidian_path,
        )
        for i in sub_notes
    ]

    # 需求：自身 domain_code == 领域，或存在指向它的关联链接且该链接 domain_code == 领域
    req_linked = (
        db.query(PmwbKnowledgeLink)
        .filter(
            PmwbKnowledgeLink.source_type == "requirement",
            PmwbKnowledgeLink.domain_code == domain_code,
            PmwbKnowledgeLink.source_id == PmwbRequirementExt.req_id,
        )
        .exists()
    )
    req_rows = (
        db.query(PmwbRequirementExt, SentEmail)
        .outerjoin(SentEmail, SentEmail.req_id == PmwbRequirementExt.req_id)
        .filter(or_(PmwbRequirementExt.domain_code == domain_code, req_linked))
        .all()
    )
    requirements = []
    _seen_req = set()
    for ext, sent in req_rows:
        if ext.id in _seen_req:
            continue  # 同一需求有多封关联邮件时 outerjoin 会产生重复行，按需求去重
        _seen_req.add(ext.id)
        name = ext.req_name or (sent.req_name if sent else None) or ext.req_id
        requirements.append(
            DomainRelatedItem(code=ext.req_id, title=name, status=ext.status or "proposed")
        )

    # 会议：自身 domain_code == 领域，或存在指向它的关联链接（source_id == meeting.id）
    meet_linked = (
        db.query(PmwbKnowledgeLink)
        .filter(
            PmwbKnowledgeLink.source_type == "meeting",
            PmwbKnowledgeLink.domain_code == domain_code,
            cast(PmwbKnowledgeLink.source_id, Integer) == PmwbMeeting.id,
        )
        .exists()
    )
    m_rows = (
        db.query(PmwbMeeting)
        .filter(or_(PmwbMeeting.domain_code == domain_code, meet_linked))
        .order_by(PmwbMeeting.start_time.desc())
        .all()
    )
    meetings = [
        DomainRelatedItem(
            code=m.meeting_id,
            title=m.title or "",
            sub_title=m.start_time.strftime("%Y-%m-%d") if m.start_time else None,
            obsidian_path=m.obsidian_path,
        )
        for m in m_rows
    ]

    # 运营工单：自身 domain_code == 领域，或存在指向它的关联链接（source_id == issue.id）
    issue_linked = (
        db.query(PmwbKnowledgeLink)
        .filter(
            PmwbKnowledgeLink.source_type == "operation",
            PmwbKnowledgeLink.domain_code == domain_code,
            cast(PmwbKnowledgeLink.source_id, Integer) == PmwbOperationIssue.id,
        )
        .exists()
    )
    i_rows = (
        db.query(PmwbOperationIssue)
        .filter(or_(PmwbOperationIssue.domain_code == domain_code, issue_linked))
        .all()
    )
    issues = [
        DomainRelatedItem(code=i.issue_no, title=i.title or "", category=i.category, status=i.status)
        for i in i_rows
    ]

    # 关联表驱动的跨对象关联（覆盖通过 KnowledgeLinker 关联、笔记自身 domain_code 不同的场景）
    link_rows = (
        db.query(PmwbKnowledgeLink, PmwbKnowledgeItem)
        .join(PmwbKnowledgeItem, PmwbKnowledgeItem.id == PmwbKnowledgeLink.knowledge_item_id)
        .filter(PmwbKnowledgeLink.domain_code == domain_code)
        .order_by(PmwbKnowledgeLink.created_at.desc())
        .all()
    )
    timeline = [
        DomainLinkItem(
            link_id=lk.id,
            source_type=lk.source_type,
            source_id=lk.source_id,
            knowledge_item_id=lk.knowledge_item_id,
            note_title=item.title,
            link_note=lk.note,
            created_at=lk.created_at.strftime("%Y-%m-%d %H:%M") if lk.created_at else None,
        )
        for lk, item in link_rows
    ]

    return DomainRelatedOut(
        domain_code=domain_code,
        domain_name=domain.domain_name,
        knowledge_items=knowledge_items,
        main_note=main_note_out,
        sub_notes=sub_notes_out,
        requirements=requirements,
        meetings=meetings,
        issues=issues,
        timeline=timeline,
    )


def list_tree(db: Session, enabled_only: bool = True) -> List[BusinessDomainTreeNode]:
    """返回树形结构（一级大类 + 二级细分领域）。

    孤儿领域兜底：parent_domain_code 为空但 domain_group 指向已有大类的记录
    （历史数据或旧入口创建时未选父领域），自动挂到 domain_group 对应大类下，
    保证所有选择点位（BusinessDomainSelect / HubPanel 等）都能看到并选到。
    """
    all_domains = list_all(db, enabled_only=enabled_only)

    # 按 domain_code 索引
    by_code = {d.domain_code: d for d in all_domains}

    # 正式根节点：作为 parent 被其他领域引用的节点
    parent_codes = {d.parent_domain_code for d in all_domains if d.parent_domain_code}
    real_roots = [d for d in all_domains if d.parent_domain_code is None and d.domain_code in parent_codes]
    orphans = [
        d for d in all_domains
        if d.parent_domain_code is None and d.domain_code not in parent_codes
    ]

    # 构建树：根节点 + 直接子节点
    roots = []
    for d in real_roots:
        node = BusinessDomainTreeNode(**d.model_dump(), children=[])
        roots.append(node)
        for child in all_domains:
            if child.parent_domain_code == d.domain_code:
                node.children.append(
                    BusinessDomainTreeNode(**child.model_dump(), children=[])
                )

    # 孤儿领域 → 按 domain_group 归入对应大类（匹配 root 的 domain_group 或 domain_name）
    root_by_group = {}
    for r in roots:
        root_by_group.setdefault(r.domain_group, r)
        root_by_group.setdefault(r.domain_name, r)
    for o in orphans:
        target = root_by_group.get(o.domain_group)
        if target:
            target.children.append(BusinessDomainTreeNode(**o.model_dump(), children=[]))
        else:
            # 找不到归属大类 → 作为独立根展示（不留丢）
            roots.append(BusinessDomainTreeNode(**o.model_dump(), children=[]))

    # 兜底：子节点父领域被停用（enabled_only 过滤掉）时，挂到「其他」根节点
    orphaned = [
        d for d in all_domains
        if d.parent_domain_code and d.parent_domain_code not in by_code
    ]
    if orphaned and not any(r.domain_code == "_other" for r in roots):
        other_node = BusinessDomainTreeNode(
            id=0, domain_code="_other", domain_name="其他", domain_group="通用",
            children=[
                BusinessDomainTreeNode(**o.model_dump(), children=[])
                for o in orphaned
            ],
        )
        roots.append(other_node)

    return roots


# ---------------------------------------------------------------------------
# CRUD（管理入口使用）
# ---------------------------------------------------------------------------

def create(db: Session, data: BusinessDomainCreate) -> BusinessDomainOut:
    """新增业务领域。"""
    # 检查 domain_code 唯一性
    if db.query(PmwbBusinessDomain).filter(
        PmwbBusinessDomain.domain_code == data.domain_code
    ).first():
        raise ValidationException(message=f"业务编码 '{data.domain_code}' 已存在")

    parent_id = _resolve_parent(db, data.parent_domain_code)

    domain = PmwbBusinessDomain(
        domain_code=data.domain_code,
        domain_name=data.domain_name,
        domain_group=data.domain_group,
        vault_path=data.vault_path,
        match_keywords=data.match_keywords,
        parent_id=parent_id,
        description=data.description,
        sort_order=data.sort_order,
        enabled=data.enabled,
    )
    db.add(domain)
    db.commit()
    db.refresh(domain)

    # 页面化同步创建：建 vault 目录树 + 主笔记 + 回写 vault_path（§3.8.5）
    _sync_create_vault(db, domain)

    return _to_out(domain)


def update(db: Session, domain_code: str, data: BusinessDomainUpdate) -> BusinessDomainOut:
    """修改业务领域。"""
    domain = db.query(PmwbBusinessDomain).filter(
        PmwbBusinessDomain.domain_code == domain_code
    ).first()
    if not domain:
        raise NotFoundException(message=f"业务领域 '{domain_code}' 不存在")

    update_data = data.model_dump(exclude_unset=True)

    # 特殊处理 parent_domain_code → parent_id
    if "parent_domain_code" in update_data:
        pc = update_data.pop("parent_domain_code")
        domain.parent_id = _resolve_parent(db, pc)

    # 改名/改组前记录旧路径（用于原子重命名 vault 目录 + 主笔记）
    old_rel = domain.vault_path or op.resolve_domain_path(db, domain_code)
    old_name = domain.domain_name
    old_group = domain.domain_group

    for key, val in update_data.items():
        setattr(domain, key, val)

    new_rel = op.resolve_domain_path(db, domain_code)
    if new_rel != old_rel:
        _sync_rename_vault(old_rel, new_rel, old_name, domain.domain_name, domain.domain_group)
        domain.vault_path = new_rel
    db.commit()
    db.refresh(domain)
    return _to_out(domain)


def delete(db: Session, domain_code: str) -> dict:
    """删除业务领域（软删除：设 enabled=False）。"""
    domain = db.query(PmwbBusinessDomain).filter(
        PmwbBusinessDomain.domain_code == domain_code
    ).first()
    if not domain:
        raise NotFoundException(message=f"业务领域 '{domain_code}' 不存在")

    domain.enabled = False
    db.commit()
    return {"domain_code": domain_code, "deleted": True}


# ---------------------------------------------------------------------------
# 页面化同步创建（§3.8.5）：vault 目录/主笔记/子笔记与 DB 单一来源同步
# ---------------------------------------------------------------------------

def _sync_create_vault(db: Session, domain: PmwbBusinessDomain) -> None:
    """写 DB 后同步建 vault 目录树 + 主笔记骨架，并回写 vault_path。

    vault 不可达（盘符缺失/无权限/路径非法）时仅告警，不阻断 DB 记录，
    保证「页面建领域」永远成功（绝不因 vault 故障回滚业务数据）。
    """
    try:
        if not domain.vault_path:
            domain.vault_path = op.resolve_domain_path(db, domain.domain_code)
        op.ensure_domain_dir(db, domain.domain_code)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        try:
            if not domain.vault_path:
                domain.vault_path = op.resolve_domain_path(db, domain.domain_code)
            db.commit()
        except Exception:
            db.rollback()
        logger.warning("领域[%s] 同步建 vault 失败(已忽略，DB 仍建): %s", domain.domain_code, exc)


def _patch_note_frontmatter(note_path: Path, name: str, group: str) -> None:
    """重命名后将主笔记 frontmatter 的 domain/group 与标题对齐新名称。"""
    try:
        txt = note_path.read_text(encoding="utf-8")
        txt = re.sub(r"^group: .*$", f"group: {group}", txt, flags=re.M)
        txt = re.sub(r"^domain: .*$", f"domain: {name}", txt, flags=re.M)
        txt = re.sub(r"^# .*业务知识主笔记$", f"# {name} 业务知识主笔记", txt, flags=re.M)
        note_path.write_text(txt, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("主笔记 frontmatter 更新失败(已忽略): %s", exc)


def _sync_rename_vault(old_rel, new_rel, old_name, new_name, new_group) -> None:
    """领域改名/改组时原子重命名 vault 目录 + 主笔记文件名，并校正 frontmatter。

    规则：旧目录存在且新目录不存在才移动（不覆盖已有内容）；若新目录已存在
    则视为手工预建，仅校正主笔记 frontmatter 的 group/domain。
    """
    try:
        vroot = Path(settings.OBSIDIAN_VAULT_PATH)
        old_abs = vroot / old_rel
        new_abs = vroot / new_rel
        if old_abs.exists() and not new_abs.exists():
            new_abs.parent.mkdir(parents=True, exist_ok=True)
            old_abs.rename(new_abs)
            old_note = new_abs / op.main_note_filename(old_name)
            new_note = new_abs / op.main_note_filename(new_name)
            if old_note.exists() and not new_note.exists():
                old_note.rename(new_note)
            if new_note.exists():
                _patch_note_frontmatter(new_note, new_name, new_group)
        elif new_abs.exists() and not old_abs.exists():
            new_note = new_abs / op.main_note_filename(new_name)
            if new_note.exists():
                _patch_note_frontmatter(new_note, new_name, new_group)
    except Exception as exc:  # noqa: BLE001
        logger.warning("领域重命名 vault 同步失败(已忽略): %s", exc)


def create_note(db: Session, domain_code: str, note_name: str,
                note_type: str = "sub", category: str = "operation") -> PmwbKnowledgeItem:
    """页面化新建业务子笔记：在 vault 建 .md 并登记 pmwb_knowledge_item。

    主笔记(main)由领域字典唯一保活，子笔记走此入口登记，避免再开 Obsidian 手工建。
    vault 不可达仅告警，DB 索引仍登记（路径解析不依赖可达）。
    """
    domain = db.query(PmwbBusinessDomain).filter(
        PmwbBusinessDomain.domain_code == domain_code
    ).first()
    if not domain:
        raise NotFoundException(message=f"业务领域不存在：{domain_code}")

    root_rel = op.resolve_domain_path(db, domain_code)
    rel = f"{root_rel}/{note_name}.md"
    try:
        vroot = Path(settings.OBSIDIAN_VAULT_PATH)
        (vroot / root_rel).mkdir(parents=True, exist_ok=True)
        note_path = vroot / rel
        if not note_path.exists():
            note_path.write_text(
                "---\n"
                "type: 业务子笔记\n"
                f"domain: {domain.domain_name}\n"
                f"group: {domain.domain_group}\n"
                "tags: []\n"
                "---\n\n"
                f"# {note_name}\n\n"
                "> 由 PMWB 知识中心页面化创建。\n",
                encoding="utf-8",
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("子笔记建 vault 失败(已忽略): %s", exc)

    item = PmwbKnowledgeItem(
        item_id=f"kn-{uuid.uuid4().hex[:10]}",
        title=note_name,
        category=category,
        obsidian_path=rel,
        source_type="manual",
        domain_code=domain_code,
        note_type=note_type,
        summary="",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def batch_set_domain(db: Session, payloads: List[dict], overwrite: bool = True) -> dict:
    """批量设置业务领域关联（关联便捷性优化 §3.11）。

    payloads: [{source_type, source_id, domain_code}]
    source_type -> (模型, 主键字段)：
        requirement=PmwbRequirementExt.req_id / ticket=PmwbDevTicket.id /
        meeting=PmwbMeeting.meeting_id / operation=PmwbOperationIssue.issue_no /
        note=PmwbKnowledgeItem.item_id / key_work=PmwbKeyWork.id
    overwrite=False 时跳过已有关联(domain_code 非空)的记录，避免批量操作污染存量。
    返回 {updated, skipped, errors}；未知 source_type / 不存在记录计入 errors 不阻断其他。
    """
    MODEL_KEY = {
        "requirement": (PmwbRequirementExt, "req_id"),
        "ticket": (PmwbDevTicket, "id"),
        "meeting": (PmwbMeeting, "meeting_id"),
        "operation": (PmwbOperationIssue, "issue_no"),
        "note": (PmwbKnowledgeItem, "item_id"),
        "key_work": (PmwbKeyWork, "id"),
    }
    updated = skipped = 0
    errors = []
    for p in payloads:
        st = (p.get("source_type") or "").strip()
        sid = p.get("source_id")
        dc = p.get("domain_code")
        if st not in MODEL_KEY or not sid:
            errors.append({"source_type": st, "source_id": sid, "reason": "unknown_or_missing"})
            continue
        model, key_field = MODEL_KEY[st]
        rec = db.query(model).filter(getattr(model, key_field) == sid).first()
        if not rec:
            errors.append({"source_type": st, "source_id": sid, "reason": "not_found"})
            continue
        if not overwrite and getattr(rec, "domain_code", None):
            skipped += 1
            continue
        rec.domain_code = dc
        updated += 1
    db.commit()
    return {"updated": updated, "skipped": skipped, "errors": errors}


def suggest_domains(
    db: Session, title: str, top: int = 5, recent_codes: Optional[List[str]] = None
) -> List[dict]:
    """根据标题智能推荐业务领域。

    匹配规则（按优先级排序）：
    1. 最近使用（recent_codes 置顶，取前 3）
    2. 精确命中 domain_name
    3. 命中 match_keywords
    4. 命中 domain_code / 拼音首字母（简单包含）
    返回列表含 reason 字段说明推荐理由。
    """
    if not title or not title.strip():
        return []
    title = title.strip().lower()
    recent_codes = recent_codes or []

    domains = (
        db.query(PmwbBusinessDomain)
        .filter(PmwbBusinessDomain.enabled == True)
        .order_by(PmwbBusinessDomain.sort_order, PmwbBusinessDomain.domain_name)
        .all()
    )

    def _score(d: PmwbBusinessDomain):
        name = (d.domain_name or "").lower()
        code = (d.domain_code or "").lower()
        keywords = (d.match_keywords or "").lower().split(",")
        if d.domain_code in recent_codes:
            return 100
        if title == name:
            return 90
        if title in name or name in title:
            return 80
        if any(title in k.strip() for k in keywords if k.strip()):
            return 70
        if title in code or title in code.replace("-", ""):
            return 60
        # 简单首字母匹配：例如 ywt -> 一网通
        if title and name:
            initials = "".join([c[0] for c in name.split() if c]).lower()
            if title in initials:
                return 50
        return 0

    scored = []
    for d in domains:
        s = _score(d)
        if s > 0:
            if s >= 100:
                reason = "最近使用"
            elif s >= 90:
                reason = "精确匹配"
            elif s >= 80:
                reason = "名称包含"
            elif s >= 70:
                reason = "关键词匹配"
            elif s >= 60:
                reason = "编码匹配"
            else:
                reason = "首字母匹配"
            scored.append({
                "domain_code": d.domain_code,
                "domain_name": d.domain_name,
                "domain_group": d.domain_group,
                "score": s,
                "reason": reason,
            })

    scored.sort(key=lambda x: (-x["score"], x["domain_name"]))
    return scored[:top]
