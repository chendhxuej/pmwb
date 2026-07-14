from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ReminderSendRequest(BaseModel):
    req_id: str = Field(..., description="需求编号")
    req_name: Optional[str] = Field(None, description="需求名称")
    to: str = Field(..., description="收件人邮箱")
    cc: Optional[str] = Field(None, description="抄送人邮箱，多个用逗号分隔")
    subject: str = Field(..., description="邮件主题")
    body: str = Field(..., description="邮件正文")
    template_id: Optional[str] = Field(None, description="邮件模板ID")
    template_data: Optional[Dict[str, Any]] = Field(None, description="模板数据")
    operator: Optional[str] = Field(None, description="操作人")


class ReminderSendResponse(BaseModel):
    success: bool
    record_id: int
    message: str


class ReminderRecordOut(BaseModel):
    id: int
    req_id: Optional[str] = None
    req_name: Optional[str] = None
    email_type: Optional[str] = None
    recipient: Optional[str] = None
    recipient_name: Optional[str] = None
    subject: Optional[str] = None
    send_status: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
