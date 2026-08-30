from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from schemas.knowledge import (
    KnowledgeItemCreate,
    KnowledgeItemUpdate,
    KnowledgeLinkCreate,
    KnowledgeLinkBatch,
)
from services.knowledge import knowledge_item_service
from services.knowledge_link_service import (
    link_to_item,
    link_to_path,
    list_links,
    unlink_by_link_id as unlink,
)
from services.knowledge_link_service import (
    business_timeline,
    business_timeline_global,
    create_main_note as create_main_note_service,
    ensure_domain_main_notes,
    get_main_note_structured,
    link_note,
    list_by_item,
    sync_main_note_from_links,
    unlink as unlink_by_source,
)
from services.obsidian_link import (
    archive_requirement_manual,
    sediment_operation_rules,
    sediment_requirement,
    sediment_requirement_rules,
    sediment_user_story,
)
from services.vault_sync import sync_from_vault

router = APIRouter(prefix="/knowledge", tags=["知识库"])


@router.get("/business-timeline")
def get_business_timeline(
    domain_code: str = Query(..., description="业务领域编码"),
    event_type: Optional[str] = Query(None, description="按事件类型过滤"),
    limit: Optional[int] = Query(None, description="截断条数"),
    db: Session = Depends(get_db),
):
    """业务全过程时间线：聚合某领域全部关联事件，按 event_date 倒序。"""
    data = business_timeline(db, domain_code, event_type=event_type, limit=limit)
    return success(data=data)


@router.get("/business-timeline/global")
def get_business_timeline_global(
    event_type: Optional[str] = Query(None, description="按事件类型过滤"),
    group: Optional[str] = Query(None, description="按业务分组过滤"),
    limit: Optional[int] = Query(50, description="截断条数"),
    db: Session = Depends(get_db),
):
    """全局业务全过程时间线：聚合所有领域关联事件，按 event_date 倒序。"""
    data = business_timeline_global(db, event_type=event_type, group=group, limit=limit)
    return success(data=data)


@router.get("")
def list_items(
    keyword: Optional[str] = Query(None, description="关键字搜索"),
    category: Optional[str] = Query(None, description="分类"),
    sub_category: Optional[str] = Query(None, description="子分类"),
    tag: Optional[str] = Query(None, description="标签"),
    source_type: Optional[str] = Query(None, description="来源类型"),
    domain_code: Optional[str] = Query(None, description="业务领域编码"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=1000, description="每页条数"),
    db: Session = Depends(get_db),
):
    """查询知识条目。"""
    return success(data=knowledge_item_service.list_with_filters(
        db=db,
        keyword=keyword,
        category=category,
        sub_category=sub_category,
        tag=tag,
        source_type=source_type,
        domain_code=domain_code,
        page=page,
        page_size=page_size,
    ))


# ---------------------------------------------------------------------------
# 多对多关联（需求/工单/会议 ↔ 知识笔记）
# 注意：必须注册在 /{item_id} 动态路由之前，否则 /links 会被 /{item_id} 抢匹配。
# ---------------------------------------------------------------------------

@router.get("/links")
def get_links(
    source_type: str = Query(..., description="来源类型 requirement/ticket/operation/meeting"),
    source_id: str = Query(..., description="来源业务ID"),
    db: Session = Depends(get_db),
):
    """获取某来源对象已关联的知识笔记列表。"""
    return success(data=list_links(db, source_type, source_id))


@router.post("/links")
def create_link(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """关联某来源对象到指定知识条目。

    payload: {source_type, source_id, knowledge_item_id, link_type?, note?, domain_code?}
    """
    return success(data=link_to_item(
        db,
        source_type=payload["source_type"],
        source_id=payload["source_id"],
        knowledge_item_id=payload["knowledge_item_id"],
        link_type=payload.get("link_type", "main"),
        note=payload.get("note"),
        domain_code=payload.get("domain_code"),
    ))


@router.post("/links/by-path")
def create_link_by_path(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """按 Obsidian 路径关联到已有/新建知识条目。"""
    return success(data=link_to_path(
        db,
        source_type=payload["source_type"],
        source_id=payload["source_id"],
        obsidian_path=payload["obsidian_path"],
        link_type=payload.get("link_type", "main"),
        note=payload.get("note"),
        domain_code=payload.get("domain_code"),
    ))


@router.delete("/links/{link_id}")
def delete_link(link_id: int, db: Session = Depends(get_db)):
    """取消关联。"""
    return success(data=unlink(db, link_id))


# ---------------------------------------------------------------------------
# 按知识条目维度管理关联（kc-2：标准实现，前端 KnowledgeLinker 使用）
# 注意：/main-note 与 /{item_id}/links 为多段路径，注册在 /{item_id} 之前以避免歧义。
# ---------------------------------------------------------------------------

@router.post("/main-note")
def create_main_note(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """新建业务知识主笔记（选领域后生成标准模板，幂等）。

    payload: {domain_code}
    """
    result = create_main_note_service(db, payload["domain_code"])
    return success(
        data=result,
        message="主笔记已生成" if result["created"] else "主笔记已存在",
    )


@router.get("/main-note/{domain_code}")
def get_main_note(domain_code: str, db: Session = Depends(get_db)):
    """知识标准化管理：读取某领域业务知识主笔记的标准结构（14 章节 + 时间线）。

    用于前端「知识标准化管理（主笔记标准结构）」展示，章节通过编号前缀
    匹配，兼容各域主笔记措辞差异。
    """
    data = get_main_note_structured(db, domain_code)
    return success(data=data)


@router.post("/ensure-main-notes")
def ensure_main_notes(db: Session = Depends(get_db)):
    """为所有「有子笔记但缺主笔记」的启用领域自动保活主笔记并重建子笔记摘要（批量回填）。"""
    result = ensure_domain_main_notes(db)
    return success(
        data=result,
        message=f"扫描 {result['domains_scanned']} 个领域，新建主笔记 {result['main_notes_created']} 个，保活/重建 {result['main_notes_ensured']} 个",
    )


@router.post("/sync-main-note")
def sync_main_note(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """把需求/用户故事/关联事件回流到指定领域主笔记的自动区（人工区零覆盖，幂等）。

    payload: {domain_code}
    """
    domain_code = payload.get("domain_code")
    if not domain_code:
        return success(data={"changed": False, "blocks_written": [], "error": "missing_domain_code"})
    result = sync_main_note_from_links(db, domain_code)
    return success(data=result, message="主笔记自动区已同步" if result["changed"] else "主笔记无变更")


@router.get("/{item_id}/links")
def get_item_links(item_id: int, db: Session = Depends(get_db)):
    """获取某知识条目已关联的全部过程性对象。"""
    return success(data=list_by_item(db, item_id))


@router.post("/{item_id}/links")
def create_item_link(
    item_id: int,
    payload: KnowledgeLinkCreate,
    db: Session = Depends(get_db),
):
    """给某知识条目建立一条关联（幂等），并同步主笔记 frontmatter related_* 数组。"""
    data = payload.model_dump()
    return success(data=link_note(
        db,
        knowledge_item_id=item_id,
        source_type=data["source_type"],
        source_id=data["source_id"],
        link_type=data.get("link_type", "main"),
        domain_code=data.get("domain_code"),
        note=data.get("note"),
    ))


@router.post("/{item_id}/links/batch")
def create_item_links_batch(
    item_id: int,
    payload: KnowledgeLinkBatch,
    db: Session = Depends(get_db),
):
    """给某知识条目批量建立关联（幂等）。"""
    created = []
    for lk in payload.links:
        created.append(link_note(
            db,
            knowledge_item_id=item_id,
            source_type=lk.source_type,
            source_id=lk.source_id,
            link_type=lk.link_type,
            domain_code=lk.domain_code,
            note=lk.note,
        ))
    return success(data=created)


@router.delete("/{item_id}/links/{source_type}/{source_id}")
def delete_item_link(
    item_id: int,
    source_type: str,
    source_id: str,
    db: Session = Depends(get_db),
):
    """删除某知识条目与指定过程性对象的关联，并同步清理 frontmatter。"""
    ok = unlink_by_source(db, item_id, source_type, source_id)
    return success(data=ok)


@router.post("/sediment/requirement/{req_id}")
def sediment_requirement_endpoint(req_id: str, force: bool = False, db: Session = Depends(get_db)):
    """把需求沉淀为知识条目（force=True 覆盖更新）。"""
    return success(data=sediment_requirement(db, req_id, force=force))


@router.post("/sediment/user-story/{story_id}")
def sediment_user_story_endpoint(
    story_id: int,
    force: bool = Query(False, description="true 时覆盖已存在的规则笔记"),
    db: Session = Depends(get_db),
):
    """把用户故事的业务规则沉淀为业务知识笔记（force=True 覆盖更新）。"""
    return success(data=sediment_user_story(db, story_id, force=force))


@router.post("/sediment/requirement/{req_id}/rules")
def sediment_requirement_rules_endpoint(req_id: str, db: Session = Depends(get_db)):
    """把某需求的用户故事业务规则追加到目标领域主笔记的「场景规则」子笔记（重复触发幂等更新）。"""
    return success(data=sediment_requirement_rules(db, req_id))


@router.post("/sediment/requirement/{req_id}/archive-manual")
def archive_requirement_manual_endpoint(req_id: str, db: Session = Depends(get_db)):
    """把需求关联开发工单的操作手册交付物归档到业务知识交付物目录并登记主笔记。"""
    return success(data=archive_requirement_manual(db, req_id))


@router.post("/sediment/operation/{issue_id}/rules")
def sediment_operation_rules_endpoint(issue_id: int, db: Session = Depends(get_db)):
    """把运营工单的结构化经验（根因分类/影响范围/解决方案类型/根因/方案/经验）追加到目标领域主笔记的「场景规则」子笔记（重复触发幂等更新）。"""
    return success(data=sediment_operation_rules(db, issue_id))


@router.get("/{item_id}")
def get_item(item_id: int, db: Session = Depends(get_db)):
    """获取知识条目详情。"""
    return success(data=knowledge_item_service.get(db, item_id))


@router.get("/{item_id}/content")
def get_item_content(item_id: int, db: Session = Depends(get_db)):
    """获取知识条目 Markdown 内容。"""
    data = knowledge_item_service.get_content(db, item_id)
    return success(data=data)


@router.post("")
def create_item(obj_in: KnowledgeItemCreate, db: Session = Depends(get_db)):
    """创建知识条目，可选同时写入 Obsidian。"""
    return success(data=knowledge_item_service.create_with_content(db, obj_in))


@router.put("/{item_id}")
def update_item(item_id: int, obj_in: KnowledgeItemUpdate, db: Session = Depends(get_db)):
    """更新知识条目元数据。"""
    return success(data=knowledge_item_service.update(db, item_id, obj_in.model_dump(exclude_unset=True)))


@router.put("/{item_id}/content")
def update_item_content(item_id: int, payload: Dict[str, Any], db: Session = Depends(get_db)):
    """更新知识条目 Markdown 内容。"""
    content = payload.get("content", "")
    ok = knowledge_item_service.update_content(db, item_id, content)
    return success(data=ok)


@router.delete("/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    """删除知识条目。"""
    ok = knowledge_item_service.delete(db, item_id)
    return success(data=ok)


@router.get("/meta/categories")
def get_categories(db: Session = Depends(get_db)):
    """获取所有分类。"""
    return success(data=knowledge_item_service.get_categories(db))


@router.get("/meta/sub-categories")
def get_sub_categories(
    category: Optional[str] = Query(None, description="分类"),
    db: Session = Depends(get_db),
):
    """获取子分类。"""
    return success(data=knowledge_item_service.get_sub_categories(db, category))


@router.get("/meta/tags")
def get_tags(db: Session = Depends(get_db)):
    """获取所有标签。"""
    return success(data=knowledge_item_service.get_tags(db))


@router.post("/sync-from-vault")
def sync_knowledge_from_vault(
    dirs: Optional[List[str]] = None,
    dry_run: bool = False,
    db: Session = Depends(get_db),
):
    """从 Obsidian Vault 反向同步笔记到知识索引。

    - dirs: 要扫描的目录列表，默认扫描业务知识/会议/业务建设/运营/知识沉淀等目录
    - dry_run: True 时只统计不写入
    """
    result = sync_from_vault(db, dirs=dirs, dry_run=dry_run)
    return success(data=result, message=f"同步完成：新增索引 {result['new_indexed']} 条，跳过已有 {result['skipped_existing']} 条")
