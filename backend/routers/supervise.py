"""督办邮件路由 - 统一出站口，各工单模块复用的督办接口。"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from db.models import PmwbMeetingAction
from services.dev_ticket import dev_ticket_service
from services.meeting import meeting_service
from services.operation import operation_issue_service as operation_service

from . import supervise as supervise_service

logger = logging.getLogger("pmwb.routers.supervise")

router = APIRouter(prefix="/supervise", tags=["邮件督办"])


class SuperviseTicketRequest(BaseModel):
    """督办工单请求。"""
    scene: str  # "sync" | "urge"
    ticket_type: str  # "work_order" | "operation" | "dev_ticket" | "requirement"
    ticket_id: int | str
    recipients: list[str]
    extra_msg: Optional[str] = None


class SuperviseActionRequest(BaseModel):
    """督办会议行动项请求。"""
    scene: str  # "sync" | "urge"
    meeting_id: int
    action_id: int
    recipients: list[str]
    extra_msg: Optional[str] = None


def _build_ticket_info(ticket_type: str, ticket_id: int | str, db: Session) -> dict | None:
    """根据工单类型查询工单详情并构建 template_data。"""
    if ticket_type in ("work_order", "operation"):
        row = operation_service.get(db, ticket_id)
        if not row:
            return None
        return {
            "issue_no": row.issue_no,
            "title": row.title,
            "issue_type": row.issue_type,
            "category": row.category,
            "handler": row.handler,
            "due": str(row.resolve_date) if row.resolve_date else "",
            "status": row.status,
            "situation_desc": row.situation_desc or "",
            "source": "运营问题/工单",
        }

    if ticket_type == "dev_ticket":
        row = dev_ticket_service.get(db, ticket_id)
        if not row:
            return None
        return {
            "issue_no": str(row.id),
            "title": row.title,
            "issue_type": "开发工单",
            "category": row.category or "",
            "handler": row.owner or row.assignee or "",
            "due": str(row.plan_end) if row.plan_end else "",
            "status": row.status,
            "description": row.description or "",
            "source": "开发工单",
        }

    if ticket_type == "requirement":
        from services.requirement import requirement_service
        row = requirement_service.get(db, ticket_id)
        if not row:
            return None
        return {
            "issue_no": row.req_no or str(row.id),
            "title": row.title or row.req_name or "",
            "issue_type": "需求",
            "category": row.category or "",
            "handler": row.owner or row.sa or "",
            "due": str(row.plan_end) if row.plan_end else str(row.expected_month) if row.expected_month else "",
            "status": row.status,
            "description": row.req_desc or row.description or "",
            "source": "需求管理",
        }

    return None


@router.post("/ticket")
def supervise_ticket(req: SuperviseTicketRequest, db: Session = Depends(get_db)):
    """发起工单督办邮件（支持 4 类工单）。"""
    ticket = _build_ticket_info(req.ticket_type, req.ticket_id, db)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"工单不存在: {req.ticket_type}#{req.ticket_id}")

    result = supervise_service.supervise_ticket(req.scene, ticket, req.recipients)
    return success(data=result)


@router.post("/action")
def supervise_action(req: SuperviseActionRequest, db: Session = Depends(get_db)):
    """发起会议行动项督办邮件。"""
    action = db.query(PmwbMeetingAction).filter(
        PmwbMeetingAction.meeting_id == req.meeting_id,
        PmwbMeetingAction.id == req.action_id,
    ).first()
    if not action:
        raise HTTPException(status_code=404, detail=f"行动项不存在: meeting#{req.meeting_id} action#{req.action_id}")

    # 查询所属会议标题
    meeting = meeting_service.get(db, req.meeting_id)
    meeting_title = meeting.title if meeting else ""

    action_data = {
        "id": str(action.id),
        "content": action.content or "",
        "owner": action.owner or "",
        "due_date": str(action.due_date) if action.due_date else "",
        "status": action.status if hasattr(action, "status") else "",
        "meeting_title": meeting_title,
    }

    result = supervise_service.supervise_action(req.scene, action_data, req.recipients)
    return success(data=result)
