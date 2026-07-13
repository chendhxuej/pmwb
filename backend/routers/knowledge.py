from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from schemas.knowledge import KnowledgeItemCreate, KnowledgeItemUpdate
from services.knowledge import knowledge_item_service

router = APIRouter(prefix="/knowledge", tags=["知识库"])


@router.get("")
def list_items(
    keyword: Optional[str] = Query(None, description="关键字搜索"),
    category: Optional[str] = Query(None, description="分类"),
    sub_category: Optional[str] = Query(None, description="子分类"),
    tag: Optional[str] = Query(None, description="标签"),
    source_type: Optional[str] = Query(None, description="来源类型"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
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
        page=page,
        page_size=page_size,
    ))


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
