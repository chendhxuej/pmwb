from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from schemas.active_optimization import (
    ActiveOptimizationCreate,
    ActiveOptimizationListResponse,
    ActiveOptimizationStats,
    ActiveOptimizationUpdate,
)
from services.active_optimization import active_optimization_service

router = APIRouter(prefix="/active-optimizations", tags=["主动优化"])


@router.get("")
def list_active_optimizations(
    keyword: Optional[str] = Query(None, description="关键字搜索"),
    status: Optional[str] = Query(None, description="状态：pending/adopted/rejected"),
    admin_name: Optional[str] = Query(None, description="业务管理员"),
    req_id: Optional[str] = Query(None, description="关联需求文号"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=1000, description="每页条数"),
    db: Session = Depends(get_db),
):
    """查询主动优化建议列表。"""
    data = active_optimization_service.list_with_filters(
        db=db,
        keyword=keyword,
        status=status,
        admin_name=admin_name,
        req_id=req_id,
        page=page,
        page_size=page_size,
    )
    return success(data=data)


@router.get("/stats/summary")
def get_summary_stats(db: Session = Depends(get_db)):
    """获取主动优化统计摘要。"""
    data = active_optimization_service.get_summary_stats(db)
    return success(data=data)


@router.get("/{opt_id}")
def get_active_optimization(opt_id: int, db: Session = Depends(get_db)):
    """获取主动优化建议详情。"""
    obj = active_optimization_service.get(db, opt_id)
    return success(data=obj)


@router.post("")
def create_active_optimization(
    obj_in: ActiveOptimizationCreate,
    db: Session = Depends(get_db),
):
    """创建主动优化建议。"""
    obj = active_optimization_service.create(db, obj_in.model_dump())
    return success(data=obj)


@router.put("/{opt_id}")
def update_active_optimization(
    opt_id: int,
    obj_in: ActiveOptimizationUpdate,
    db: Session = Depends(get_db),
):
    """更新主动优化建议。"""
    obj = active_optimization_service.update(db, opt_id, obj_in.model_dump(exclude_unset=True))
    return success(data=obj)


@router.delete("/{opt_id}")
def delete_active_optimization(opt_id: int, db: Session = Depends(get_db)):
    """删除主动优化建议。"""
    ok = active_optimization_service.delete(db, opt_id)
    return success(data=ok)
