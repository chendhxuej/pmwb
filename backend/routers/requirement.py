from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from schemas.requirement import RequirementExtUpdate
from services.requirement import requirement_service

router = APIRouter(prefix="/requirements", tags=["需求管理"])


@router.get("")
def list_requirements(
    keyword: Optional[str] = Query(None, description="关键字搜索"),
    status: Optional[str] = Query(None, description="个人跟踪状态"),
    priority: Optional[str] = Query(None, description="优先级"),
    system_name: Optional[str] = Query(None, description="系统名称"),
    is_involved: Optional[int] = Query(None, description="是否涉及开发"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db),
):
    """查询需求列表。"""
    data = requirement_service.list_with_filters(
        db=db,
        keyword=keyword,
        status=status,
        priority=priority,
        system_name=system_name,
        is_involved=is_involved,
        page=page,
        page_size=page_size,
    )
    return success(data=data)


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """获取需求统计。"""
    return success(data=requirement_service.get_stats(db))


@router.get("/meta/systems")
def get_systems(db: Session = Depends(get_db)):
    """获取所有系统名称。"""
    return success(data=requirement_service.get_systems(db))


@router.get("/{req_id}")
def get_requirement(req_id: str, db: Session = Depends(get_db)):
    """获取需求详情。"""
    data = requirement_service.get(db, req_id)
    return success(data=data)


@router.put("/{req_id}")
def update_requirement(req_id: str, obj_in: RequirementExtUpdate, db: Session = Depends(get_db)):
    """更新需求个人跟踪信息。"""
    data = requirement_service.update_ext(db, req_id, obj_in.model_dump(exclude_unset=True))
    return success(data=data)
