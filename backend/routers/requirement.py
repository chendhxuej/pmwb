from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from schemas.requirement import EvaluationCreate, EvaluationUpdate, RequirementExtUpdate
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


@router.get("/{req_id}/evaluations")
def get_evaluations(req_id: str, db: Session = Depends(get_db)):
    """获取需求下所有团队评估记录（按SA/系统维度）。"""
    data = requirement_service.get_evaluations(db, req_id)
    return success(data=data)


@router.post("/{req_id}/evaluations")
def create_evaluation(req_id: str, obj_in: EvaluationCreate, db: Session = Depends(get_db)):
    """新增一条团队评估记录（手动录入）。"""
    data = requirement_service.create_evaluation(db, req_id, obj_in.model_dump(exclude_unset=True))
    return success(data=data)


@router.put("/{req_id}/evaluations/{eval_id}")
def update_evaluation(req_id: str, eval_id: int, obj_in: EvaluationUpdate, db: Session = Depends(get_db)):
    """更新团队评估记录（SA/系统/工作量/复核工作量/评估意见/开发单号）。"""
    data = requirement_service.update_evaluation(db, eval_id, obj_in.model_dump(exclude_unset=True))
    return success(data=data)


@router.delete("/{req_id}/evaluations/{eval_id}")
def delete_evaluation(req_id: str, eval_id: int, db: Session = Depends(get_db)):
    """删除一条团队评估记录。"""
    ok = requirement_service.delete_evaluation(db, eval_id)
    return success(data={"deleted": ok})


@router.put("/{req_id}")
def update_requirement(req_id: str, obj_in: RequirementExtUpdate, db: Session = Depends(get_db)):
    """更新需求个人跟踪信息。"""
    data = requirement_service.update_ext(db, req_id, obj_in.model_dump(exclude_unset=True))
    return success(data=data)
