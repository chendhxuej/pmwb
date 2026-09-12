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

# 注意：本文件就叫 routers/supervise.py，早期写成 `from . import supervise as supervise_service`
# 会导入到自己（routers.supervise），导致 build_ticket_fields 等函数不存在 → /supervise/* 全 500。
# 服务实现在 services/supervise.py，必须从 services 包导入。
from services import supervise as supervise_service

logger = logging.getLogger("pmwb.routers.supervise")

router = APIRouter(prefix="/supervise", tags=["邮件督办"])


def _date_str(v) -> str:
    """日期/时间 → 'YYYY-MM-DD' 字符串（空值返回空串）。

    运营工单 go_live_date 是 Date、resolve_date 是 DateTime，统一截前 10 位，
    避免邮件里出现 '2026-09-17 00:00:00' 这类脏值。
    """
    return str(v)[:10] if v else ""


def _pick(obj, *keys):
    """兼容 ORM 对象与 dict 的取值：按顺序返回第一个非空值。

    历史坑：此处曾直写 `row.plan_end`，而 PmwbDevTicket 根本没有该列
    （计划完成时间是 planned_finish_date），dict 型需求更会 KeyError → 督办 500。
    """
    for k in keys:
        if isinstance(obj, dict):
            val = obj.get(k)
        else:
            val = getattr(obj, k, None)
        if val:
            return val
    return None


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
            # 计划完成时间 = go_live_date（工单详情「计划完成时间」列）；
            # 旧版取 resolve_date（解决时间），未闭环工单恒空 → 邮件该项空白
            "due": _date_str(_pick(row, "go_live_date", "resolve_date")),
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
            "title": _pick(row, "title"),
            "issue_type": "开发工单",
            "category": _pick(row, "category") or "",
            # PmwbDevTicket 无 owner/assignee 列，责任人是 developer/created_by
            "handler": _pick(row, "developer", "created_by", "owner", "assignee") or "",
            # 开发工单计划完成时间 = planned_finish_date，回退实际上线日期 go_live_date
            "due": _date_str(_pick(row, "planned_finish_date", "go_live_date")),
            "status": _pick(row, "status"),
            "description": _pick(row, "description") or "",
            "source": "开发工单",
        }

    if ticket_type == "requirement":
        from services.requirement import requirement_service
        row = requirement_service.get(db, ticket_id)
        if not row:
            return None
        # 注意：requirement_service.get 返回的是 dict，属性访问会 AttributeError → 500，
        # 一律用 _pick 取值；version_required_date/delivered_date 等扩展字段嵌套在 ext 子字典
        ext = row.get("ext") if isinstance(row, dict) else None
        due_src = (
            _pick(row, "version_required_date", "delivered_date", "plan_end", "expected_month")
            or _pick(ext, "version_required_date", "delivered_date")
        )
        return {
            "issue_no": _pick(row, "req_no", "req_id") or str(_pick(row, "id") or ticket_id),
            "title": _pick(row, "title", "req_name") or "",
            "issue_type": "需求",
            "category": _pick(row, "system_name", "category") or "",
            "handler": _pick(row, "sa_name", "owner", "sa") or "",
            "due": _date_str(due_src),
            "status": _pick(row, "status") or _pick(ext, "status") or "",
            "description": _pick(row, "description", "req_desc", "background") or "",
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
