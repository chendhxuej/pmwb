from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from schemas.operation import OperationIssueCreate, OperationIssueUpdate
from services.obsidian_link import sediment_operation_issue
from services.operation import operation_issue_service

router = APIRouter(prefix="/operation", tags=["业务运营监控"])


@router.get("/issues")
def list_issues(
    keyword: Optional[str] = Query(None, description="关键字搜索"),
    category: Optional[str] = Query(None, description="工单大类"),
    issue_type: Optional[str] = Query(None, description="问题子类"),
    status: Optional[str] = Query(None, description="状态"),
    impact_level: Optional[str] = Query(None, description="影响等级"),
    handler: Optional[str] = Query(None, description="处理人"),
    related_system: Optional[str] = Query(None, description="关联系统"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=1000, description="每页条数"),
    db: Session = Depends(get_db),
):
    """查询工单列表。"""
    data = operation_issue_service.list_with_filters(
        db=db,
        keyword=keyword,
        category=category,
        issue_type=issue_type,
        status=status,
        impact_level=impact_level,
        handler=handler,
        related_system=related_system,
        page=page,
        page_size=page_size,
    )
    return success(data=data)


@router.get("/issues/{issue_id}")
def get_issue(issue_id: int, db: Session = Depends(get_db)):
    """获取问题详情。"""
    obj = operation_issue_service.get(db, issue_id)
    return success(data=obj)


@router.post("/issues")
def create_issue(obj_in: OperationIssueCreate, db: Session = Depends(get_db)):
    """创建问题。"""
    obj = operation_issue_service.create(db, obj_in.model_dump())
    return success(data=obj)


@router.put("/issues/{issue_id}")
def update_issue(issue_id: int, obj_in: OperationIssueUpdate, db: Session = Depends(get_db)):
    """更新问题。"""
    obj = operation_issue_service.update(db, issue_id, obj_in.model_dump(exclude_unset=True))
    return success(data=obj)


@router.delete("/issues/{issue_id}")
def delete_issue(issue_id: int, db: Session = Depends(get_db)):
    """删除问题。"""
    ok = operation_issue_service.delete(db, issue_id)
    return success(data=ok)


@router.post("/issues/{issue_id}/sediment")
def sediment_issue(issue_id: int, db: Session = Depends(get_db)):
    """一键沉淀：把运营工单生成知识条目写入 Obsidian 并建双向索引。"""
    return success(data=sediment_operation_issue(db, issue_id))


@router.get("/stats")
def get_stats(
    category: Optional[str] = Query(None, description="工单大类(不传则返回全部)"),
    db: Session = Depends(get_db),
):
    """获取运营工单统计。"""
    return success(data=operation_issue_service.get_stats(db, category=category))
