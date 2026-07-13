from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from schemas.dev_ticket import DevTicketCreate, DevTicketStatusUpdate, DevTicketUpdate
from services.dev_ticket import dev_ticket_service

router = APIRouter(prefix="/dev-tickets", tags=["开发工单"])


@router.get("")
def list_tickets(
    keyword: Optional[str] = Query(None, description="关键字搜索"),
    status: Optional[str] = Query(None, description="状态"),
    priority: Optional[str] = Query(None, description="优先级"),
    system_name: Optional[str] = Query(None, description="系统名称"),
    req_id: Optional[str] = Query(None, description="关联需求编号"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db),
):
    """查询开发工单列表。"""
    data = dev_ticket_service.list_with_filters(
        db=db,
        keyword=keyword,
        status=status,
        priority=priority,
        system_name=system_name,
        req_id=req_id,
        page=page,
        page_size=page_size,
    )
    return success(data=data)


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """获取开发工单统计。"""
    return success(data=dev_ticket_service.get_stats(db))


@router.get("/meta/systems")
def get_systems(db: Session = Depends(get_db)):
    """获取所有系统名称。"""
    return success(data=dev_ticket_service.get_systems(db))


@router.get("/{ticket_id}")
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    """获取工单详情。"""
    obj = dev_ticket_service.get(db, ticket_id)
    return success(data=obj)


@router.post("")
def create_ticket(obj_in: DevTicketCreate, db: Session = Depends(get_db)):
    """创建开发工单。"""
    obj = dev_ticket_service.create(db, obj_in.model_dump())
    return success(data=obj)


@router.put("/{ticket_id}")
def update_ticket(ticket_id: int, obj_in: DevTicketUpdate, db: Session = Depends(get_db)):
    """更新工单信息。"""
    obj = dev_ticket_service.update(db, ticket_id, obj_in.model_dump(exclude_unset=True))
    return success(data=obj)


@router.put("/{ticket_id}/status")
def update_ticket_status(ticket_id: int, obj_in: DevTicketStatusUpdate, db: Session = Depends(get_db)):
    """更新工单状态。"""
    obj = dev_ticket_service.update_status(
        db, ticket_id, obj_in.status, obj_in.operator or "", obj_in.note or ""
    )
    return success(data=obj)


@router.delete("/{ticket_id}")
def delete_ticket(ticket_id: int, db: Session = Depends(get_db)):
    """删除工单。"""
    ok = dev_ticket_service.delete(db, ticket_id)
    return success(data=ok)


@router.get("/{ticket_id}/logs")
def get_ticket_logs(ticket_id: int, db: Session = Depends(get_db)):
    """获取工单状态变更日志。"""
    logs = dev_ticket_service.get_logs(db, ticket_id)
    return success(data=logs)


@router.get("/{ticket_id}/deliverables")
def get_ticket_deliverables(ticket_id: int, db: Session = Depends(get_db)):
    """获取工单交付物列表。"""
    items = dev_ticket_service.get_deliverables(db, ticket_id)
    return success(data=items)
