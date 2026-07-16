from typing import Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from schemas.reminder import ReminderRecordOut, ReminderSendRequest, ReminderSendResponse
from services.reminder import reminder_service
from services.requirement import requirement_service

router = APIRouter(prefix="/reminders", tags=["邮件催办"])


class ContactResolveRequest(BaseModel):
    names: List[str]


@router.get("/pending")
def list_pending(db=Depends(get_db)):
    """按 SA 分组的待催办需求列表（用于催办中心批量催办）。"""
    data = requirement_service.pending_by_sa(db)
    return success(data=data)


@router.get("/records")
def list_records(limit: int = 50, db=Depends(get_db)):
    """全局邮件发送记录（最近 N 条）。"""
    data = reminder_service.list_all(db, limit)
    return success(data=data)


@router.post("/resolve-contacts")
def resolve_contacts(req: ContactResolveRequest):
    """按 SA 姓名列表解析真实邮箱（来自统一邮件中心通讯录）。"""
    data: Dict[str, str] = reminder_service.resolve_contacts(req.names)
    return success(data=data)


@router.post("/send")
def send_reminder(obj_in: ReminderSendRequest, db=Depends(get_db)):
    """发送催办邮件。"""
    data = reminder_service.send_reminder(db, obj_in)
    return success(data=data)


@router.get("/{req_id}")
def list_reminders(req_id: str, db=Depends(get_db)):
    """获取需求催办记录。"""
    data = reminder_service.list_by_req_id(db, req_id)
    return success(data=data)
