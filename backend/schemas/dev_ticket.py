from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class DevTicketStatus(str):
    created = "created"
    design_reviewed = "design_reviewed"
    dev_completed = "dev_completed"
    test_completed = "test_completed"
    live = "live"
    archived = "archived"


class DevTicketBase(BaseModel):
    ticket_no: str = Field(..., max_length=64, description="开发工单编号")
    req_id: str = Field(..., max_length=64, description="关联需求编号")
    system_name: str = Field(..., max_length=128, description="涉及系统")
    dev_team: Optional[str] = Field(None, max_length=64, description="开发团队/厂商")
    developer: Optional[str] = Field(None, max_length=64, description="开发负责人")
    dev_contact: Optional[str] = Field(None, max_length=128, description="开发联系方式")
    description: Optional[str] = None
    risk_note: Optional[str] = None
    priority: str = Field("P2", description="优先级")
    status: str = Field("created", description="当前状态")
    progress: int = Field(0, ge=0, le=100, description="进度百分比")
    design_reviewed_date: Optional[date] = None
    dev_completed_date: Optional[date] = None
    test_completed_date: Optional[date] = None
    go_live_date: Optional[date] = None
    archived_date: Optional[date] = None


class DevTicketCreate(DevTicketBase):
    pass


class DevTicketUpdate(BaseModel):
    dev_team: Optional[str] = None
    developer: Optional[str] = None
    dev_contact: Optional[str] = None
    description: Optional[str] = None
    risk_note: Optional[str] = None
    priority: Optional[str] = None
    progress: Optional[int] = None


class DevTicketStatusUpdate(BaseModel):
    status: str = Field(..., description="目标状态")
    note: Optional[str] = Field(None, description="变更备注")
    operator: Optional[str] = Field(None, description="操作人")


class DevTicketOut(DevTicketBase):
    id: int
    deliverable_path: Optional[str]
    is_overdue: bool
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DevTicketListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int
    items: List[DevTicketOut]


class DevTicketStats(BaseModel):
    total: int
    created: int
    design_reviewed: int
    dev_completed: int
    test_completed: int
    live: int
    archived: int
    overdue: int


class DevTicketDeliverableBase(BaseModel):
    deliverable_type: str = Field("other", description="交付物类型")
    file_name: str = Field(..., max_length=255, description="文件名")
    original_name: Optional[str] = Field(None, max_length=255)
    file_size: Optional[int] = None
    file_type: Optional[str] = Field(None, max_length=64)
    obsidian_path: Optional[str] = Field(None, max_length=512)
    local_path: Optional[str] = Field(None, max_length=512)
    source: Optional[str] = Field("upload", max_length=32)
    source_url: Optional[str] = Field(None, max_length=1024)
    note: Optional[str] = None


class DevTicketDeliverableOut(DevTicketDeliverableBase):
    id: int
    ticket_id: int
    created_at: datetime

    class Config:
        from_attributes = True
