"""AI 工作总结报告相关 Schema。"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field

REPORT_STATUSES = ["draft", "finalized", "sent"]
REPORT_STATUS_LABELS = {
    "draft": "草稿",
    "finalized": "已定稿",
    "sent": "已发送",
}
REPORT_TYPE_LABELS = {
    "daily": "日报",
    "weekly": "周报",
    "monthly": "月报",
    "custom": "自定义",
}
OBSIDIAN_REPORT_ROOT = "15-工作总结"


class WorkReportGenerateRequest(BaseModel):
    report_type: str = Field("daily", description="daily/weekly/monthly/custom")
    date_start: Optional[date] = Field(None, description="统计起始日期，缺省按类型自动推算")
    date_end: Optional[date] = Field(None, description="统计结束日期，缺省为今天")


class WorkReportCreate(BaseModel):
    report_type: str = "daily"
    title: Optional[str] = None
    content: Optional[str] = None
    date_start: Optional[date] = None
    date_end: Optional[date] = None


class WorkReportUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    date_start: Optional[date] = None
    date_end: Optional[date] = None
    report_type: Optional[str] = None


class WorkReportSendRequest(BaseModel):
    """发送邮件请求。to/cc 支持姓名或邮箱混合输入，后端经人员中台解析。"""

    to: List[str] = Field(..., description="收件人（姓名或邮箱，可混合）")
    cc: List[str] = Field(default_factory=list, description="抄送（姓名或邮箱，可混合）")
    subject: str = Field(..., description="邮件主题")
    body: str = Field(..., description="邮件正文(Markdown/纯文本)")


class WorkReportOut(BaseModel):
    id: int
    report_type: str
    report_type_label: str
    title: Optional[str]
    content: Optional[str]
    date_start: Optional[date]
    date_end: Optional[date]
    status: str
    status_label: str
    recipient: Optional[str]
    cc: Optional[str]
    obsidian_path: Optional[str]
    finalized_at: Optional[datetime]
    sent_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
