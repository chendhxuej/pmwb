from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from schemas.active_optimization import (
    ActiveOptimizationCreate,
    ActiveOptimizationListResponse,
    ActiveOptimizationReqLinkIn,
    ActiveOptimizationStats,
    ActiveOptimizationUpdate,
)
from services.active_optimization import active_optimization_service

router = APIRouter(prefix="/active-optimizations", tags=["主动优化"])


def _load_or_404(db: Session, opt_id: int):
    """取工单 ORM 对象，不存在则 404。"""
    obj = active_optimization_service._get(db, opt_id)
    if not obj:
        from core.exceptions import NotFoundException

        raise NotFoundException(f"主动优化工单不存在：{opt_id}")
    return obj


@router.get("")
def list_active_optimizations(
    keyword: Optional[str] = Query(None, description="关键字搜索"),
    status: Optional[str] = Query(None, description="状态：pending/adopted/rejected"),
    priority: Optional[str] = Query(None, description="优先级：P0/P1/P2/P3"),
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
        priority=priority,
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


# ─────────── 关联需求文号（一对多） ───────────
# 声明在 /{opt_id} 之前（项目防御习惯：路径参数路由放最后）


@router.get("/{opt_id}/req-links")
def list_req_links(opt_id: int, db: Session = Depends(get_db)):
    """关联需求文号列表（含 req_exists 有效性标记）。"""
    return success(data=active_optimization_service.list_req_links(db, opt_id))


@router.put("/{opt_id}/req-links")
def replace_req_links(
    opt_id: int, obj_in: ActiveOptimizationReqLinkIn, db: Session = Depends(get_db)
):
    """全量覆盖关联需求文号（幂等，为主写入方式）。"""
    obj = _load_or_404(db, opt_id)
    return success(
        data=active_optimization_service._replace_req_links(
            db, obj, obj_in.req_ids, strict=obj_in.strict
        )
    )


@router.post("/{opt_id}/req-links")
def add_req_links(
    opt_id: int, obj_in: ActiveOptimizationReqLinkIn, db: Session = Depends(get_db)
):
    """增量添加关联需求文号（不删除已有）。"""
    obj = _load_or_404(db, opt_id)
    return success(
        data=active_optimization_service._replace_req_links(
            db, obj, obj_in.req_ids, strict=obj_in.strict, incremental=True
        )
    )


@router.delete("/{opt_id}/req-links/{link_id}")
def remove_req_link(opt_id: int, link_id: int, db: Session = Depends(get_db)):
    """删除单条关联（不存在返回 deleted=False）。"""
    return success(data=active_optimization_service.remove_req_link(db, opt_id, link_id))


@router.delete("/{opt_id}/req-links")
def remove_req_links_by_req_id(
    opt_id: int, req_id: str = Query(..., description="需求文号"), db: Session = Depends(get_db)
):
    """按文号批量删除关联（清理失效文号用）。"""
    return success(data=active_optimization_service.remove_req_links_by_req_id(db, opt_id, req_id))


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
