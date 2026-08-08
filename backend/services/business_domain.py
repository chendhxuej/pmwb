"""业务领域管理 — Service"""

from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.exceptions import NotFoundException, ValidationException
from db.models import (
    PmwbBusinessDomain,
    PmwbKnowledgeItem,
    PmwbKnowledgeLink,
    PmwbMeeting,
    PmwbOperationIssue,
    PmwbRequirementExt,
    SentEmail,
)
from schemas.business_domain import (
    BusinessDomainCreate,
    BusinessDomainOut,
    BusinessDomainTreeNode,
    BusinessDomainUpdate,
    DomainRelatedItem,
    DomainRelatedOut,
)


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


def _related_counts(db: Session) -> Tuple[dict, dict, dict, dict]:
    """聚合各业务领域的关联计数（知识/需求/运营工单/会议），4 条 group-by 查询。"""
    k = dict(
        db.query(PmwbKnowledgeItem.domain_code, func.count(PmwbKnowledgeItem.id))
        .filter(PmwbKnowledgeItem.domain_code.isnot(None))
        .group_by(PmwbKnowledgeItem.domain_code)
        .all()
    )
    r = dict(
        db.query(PmwbRequirementExt.domain_code, func.count(PmwbRequirementExt.id))
        .filter(PmwbRequirementExt.domain_code.isnot(None))
        .group_by(PmwbRequirementExt.domain_code)
        .all()
    )
    i = dict(
        db.query(PmwbOperationIssue.domain_code, func.count(PmwbOperationIssue.id))
        .filter(PmwbOperationIssue.domain_code.isnot(None))
        .group_by(PmwbOperationIssue.domain_code)
        .all()
    )
    m = dict(
        db.query(PmwbMeeting.domain_code, func.count(PmwbMeeting.id))
        .filter(PmwbMeeting.domain_code.isnot(None))
        .group_by(PmwbMeeting.domain_code)
        .all()
    )
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

    req_rows = (
        db.query(PmwbRequirementExt, SentEmail)
        .outerjoin(SentEmail, SentEmail.req_id == PmwbRequirementExt.req_id)
        .filter(PmwbRequirementExt.domain_code == domain_code)
        .all()
    )
    requirements = []
    for ext, sent in req_rows:
        name = ext.req_name or (sent.req_name if sent else None) or ext.req_id
        requirements.append(
            DomainRelatedItem(code=ext.req_id, title=name, status=ext.status or "proposed")
        )

    m_rows = (
        db.query(PmwbMeeting)
        .filter(PmwbMeeting.domain_code == domain_code)
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

    i_rows = (
        db.query(PmwbOperationIssue)
        .filter(PmwbOperationIssue.domain_code == domain_code)
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
        requirements=requirements,
        meetings=meetings,
        issues=issues,
        timeline=timeline,
    )


def list_tree(db: Session, enabled_only: bool = True) -> List[BusinessDomainTreeNode]:
    """返回树形结构（一级大类 + 二级细分领域）。"""
    all_domains = list_all(db, enabled_only=enabled_only)

    # 按 domain_code 索引
    by_code = {d.domain_code: d for d in all_domains}

    # 构建树：先收集根节点（parent_domain_code 为 None）
    roots = []
    for d in all_domains:
        if d.parent_domain_code is None:
            node = BusinessDomainTreeNode(**d.model_dump(), children=[])
            roots.append(node)
            # 挂载子节点
            for child in all_domains:
                if child.parent_domain_code == d.domain_code:
                    node.children.append(
                        BusinessDomainTreeNode(**child.model_dump(), children=[])
                    )

    # 兜底：如果有子节点但没找到父节点（数据异常），挂到「其他」根节点
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

    for key, val in update_data.items():
        setattr(domain, key, val)

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
