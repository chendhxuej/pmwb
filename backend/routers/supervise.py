"""督办邮件路由 - 统一出站口，各工单模块复用的督办接口。"""

import json
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
    body_md: Optional[str] = None  # 前端 Markdown 编辑区正文（为空则按字段自动生成）


class SupervisePreviewRequest(BaseModel):
    """督办邮件预览请求（只渲染不发送）。

    与 /ticket 共用同一装配链路（build_ticket_fields + 附件块 + 正文），
    修复此前「预览传空 variables、工单信息全空、改了不刷新」的问题。
    """
    scene: str
    ticket_type: str
    ticket_id: int | str
    recipients: list[str] = []
    extra_msg: Optional[str] = None
    body_md: Optional[str] = None


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
        atts: list = []
        try:
            atts = json.loads(row.attachments) if row.attachments else []
        except Exception:  # noqa: BLE001
            atts = []
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
            # 自动带出工单附件：供 supervise 服务把附件清单 + 真实文件塞进邮件
            "issue_id": ticket_id,
            "attachments": atts,
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

    result = supervise_service.supervise_ticket(
        req.scene,
        ticket,
        req.recipients,
        extra_msg=req.extra_msg,
        body_md=req.body_md,
    )
    return success(data=result)


@router.post("/preview")
def preview_supervise(req: SupervisePreviewRequest, db: Session = Depends(get_db)):
    """督办邮件预览：只渲染不发送，输出与实发逐字一致的 HTML。"""
    ticket = _build_ticket_info(req.ticket_type, req.ticket_id, db)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"工单不存在: {req.ticket_type}#{req.ticket_id}")

    fields = supervise_service.build_ticket_fields(ticket)
    att_section, _ = supervise_service.collect_attachment_block(ticket)
    out = supervise_service.render_supervise_preview(
        req.scene,
        fields,
        body_md=req.body_md,
        extra_msg=req.extra_msg,
        extra_html=att_section,
        recipients=req.recipients,
    )
    if not out.get("ok"):
        raise HTTPException(status_code=500, detail=out.get("error", "预览渲染失败"))
    return success(data={"html": out.get("html", ""), "subject": out.get("subject", "")})


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

    result = supervise_service.supervise_action(
        req.scene,
        action_data,
        req.recipients,
        extra_msg=req.extra_msg,
    )
    return success(data=result)
