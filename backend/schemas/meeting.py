from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class MeetingType(str, Enum):
    requirement_discussion = "requirement_discussion"
    problem_analysis = "problem_analysis"
    internal_regular = "internal_regular"
    external_sync = "external_sync"
    party_meeting = "party_meeting"
    group_meeting = "group_meeting"
    other = "other"


class MeetingStatus(str, Enum):
    planned = "planned"
    held = "held"
    cancelled = "cancelled"
    not_attended = "not_attended"


class MeetingActionStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"
    not_attended = "not_attended"


class MeetingAttendeeBase(BaseModel):
    name: str = Field(..., max_length=64, description="参会人姓名")
    email: Optional[str] = Field(None, max_length=128, description="邮箱")
    dept: Optional[str] = Field(None, max_length=128, description="部门")
    is_required: int = Field(1, description="是否必须参加")


class MeetingAttendeeCreate(MeetingAttendeeBase):
    pass


class MeetingAttendeeOut(MeetingAttendeeBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class MeetingActionBase(BaseModel):
    id: Optional[int] = Field(None, description="行动项ID（更新时携带，新建留空）")
    content: str = Field(..., description="行动项内容")
    owner: Optional[str] = Field(None, max_length=64, description="负责人")
    due_date: Optional[str] = Field(None, description="截止日期")
    status: MeetingActionStatus = Field(MeetingActionStatus.pending, description="状态")
    category: Optional[str] = Field(None, description="待办分类（对应 pmwb_todo.category）")
    template: Optional[str] = Field(None, max_length=128, description="Obsidian 待办模板名（仅元数据标签）")
    related_todo_id: Optional[int] = Field(None, description="关联待办ID")

    @field_validator("due_date", mode="before")
    @classmethod
    def _empty_due_date_to_none(cls, v):
        return None if v in ("", None) else v


class MeetingActionCreate(MeetingActionBase):
    pass


class MeetingActionOut(MeetingActionBase):
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MeetingAgendaBase(BaseModel):
    seq: int = Field(1, description="议题序号（用于排序）")
    topic: str = Field(..., max_length=255, description="议题标题")
    conclusion: Optional[str] = Field(None, description="商讨结论")
    division: Optional[str] = Field(None, description="分工说明")


class MeetingAgendaCreate(MeetingAgendaBase):
    pass


class MeetingAgendaOut(MeetingAgendaBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class MeetingBase(BaseModel):
    meeting_id: str = Field(..., max_length=64, description="会议编号")
    title: str = Field(..., max_length=255, description="会议主题")
    meeting_type: MeetingType = Field(MeetingType.other, description="会议类型")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    location: Optional[str] = Field(None, max_length=255, description="会议地点/线上链接")
    host: Optional[str] = Field(None, max_length=64, description="主持人")
    convener: Optional[str] = Field(None, max_length=64, description="召集人")
    recorder: Optional[str] = Field(None, max_length=64, description="记录人")
    absentees: Optional[str] = Field(None, description="缺席人/请假说明")
    attendee_notes: Optional[str] = Field(None, description="参会注意点")
    summary: Optional[str] = Field(None, description="会议纪要摘要")
    obsidian_path: Optional[str] = Field(None, max_length=512, description="Obsidian 纪要路径")
    related_req_id: Optional[str] = Field(None, max_length=64, description="关联需求编号")
    related_ticket_no: Optional[str] = Field(None, max_length=64, description="关联开发工单编号")
    status: MeetingStatus = Field(MeetingStatus.planned, description="状态")


class MeetingCreate(MeetingBase):
    attendees: List[MeetingAttendeeCreate] = Field([], description="参会人列表")
    agendas: List[MeetingAgendaCreate] = Field([], description="会议议题列表")
    actions: List[MeetingActionCreate] = Field([], description="行动项列表")

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def _empty_datetime_to_none(cls, v):
        return None if v in ("", None) else v


class MeetingUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    meeting_type: Optional[MeetingType] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = Field(None, max_length=255)
    host: Optional[str] = Field(None, max_length=64)
    convener: Optional[str] = Field(None, max_length=64)
    recorder: Optional[str] = Field(None, max_length=64)
    absentees: Optional[str] = None
    attendee_notes: Optional[str] = None
    summary: Optional[str] = None
    obsidian_path: Optional[str] = Field(None, max_length=512)
    related_req_id: Optional[str] = Field(None, max_length=64)
    related_ticket_no: Optional[str] = Field(None, max_length=64)
    status: Optional[MeetingStatus] = None
    attendees: Optional[List[MeetingAttendeeCreate]] = None
    agendas: Optional[List[MeetingAgendaCreate]] = None
    actions: Optional[List[MeetingActionCreate]] = None

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def _empty_datetime_to_none_update(cls, v):
        return None if v in ("", None) else v


class MeetingOut(MeetingBase):
    id: int
    attendees: List[MeetingAttendeeOut]
    agendas: List[MeetingAgendaOut]
    actions: List[MeetingActionOut]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MeetingListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int
    items: List[MeetingOut]


class MeetingMailSendRequest(BaseModel):
    """会议一键发邮件请求（通知/纪要）。"""

    to: List[str] = Field(..., description="收件人邮箱列表")
    cc: Optional[List[str]] = Field(None, description="抄送人邮箱列表")
    subject: str = Field(..., max_length=500, description="邮件主题")
    body: str = Field(..., description="邮件正文（纯文本）")
    mail_type: str = Field(
        "meeting_notice",
        description="邮件类型：meeting_notice(会议通知) / meeting_minutes(会议纪要)",
    )
    recipient_names: Optional[List[str]] = Field(None, description="收件人姓名列表（用于记录展示）")
