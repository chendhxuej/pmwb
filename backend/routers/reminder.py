from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from schemas.reminder import ReminderRecordOut, ReminderSendRequest, ReminderSendResponse
from services.reminder import reminder_service

router = APIRouter(prefix="/reminders", tags=["邮件催办"])


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
