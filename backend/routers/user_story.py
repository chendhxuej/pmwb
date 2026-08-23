"""用户故事全局检索路由。

独立前缀 /api/v1/user-stories，避开需求交付的 /requirements/{req_id}/delivery/... 路由。
仅提供跨需求的只读模糊查询（默认全量、按创建时间倒序、分页）。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from schemas.requirement_delivery import UserStorySearchOut
from services import requirement_delivery as svc

router = APIRouter(prefix="/user-stories", tags=["用户故事"])


@router.get("/stats")
def get_user_story_stats(db: Session = Depends(get_db)):
    """用户故事全局统计。"""
    data = svc.get_user_story_stats(db)
    return success(data=data)


@router.get("/search")
def search_user_stories(
    keyword: Optional[str] = Query(None, description="模糊关键字，空格分词多词 AND"),
    finalized: Optional[int] = Query(None, description="定稿状态：0草稿 1已定稿，空为全部"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页条数"),
    db: Session = Depends(get_db),
):
    """全局用户故事模糊查询：默认全量，按创建时间倒序，分页返回。"""
    result = svc.search_user_stories(
        db,
        keyword=keyword,
        finalized=finalized,
        page=page,
        page_size=page_size,
    )
    return success(data=UserStorySearchOut(**result).model_dump())
