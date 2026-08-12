from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from schemas.meeting import (
    MeetingActionQuery,
    MeetingActionStatusUpdateRequest,
    MeetingActionSuperviseRequest,
    MeetingActionUpdate,
)
from services.meeting import meeting_service

router = APIRouter(prefix="/meetings", tags=["会议行动项"])


@router.get("/actions")
def list_actions(
    meeting_id: Optional[int] = Query(None, description="关联会议ID"),
    owner: Optional[str] = Query(None, description="负责人姓名模糊匹配"),
    status: Optional[str] = Query(None, description="行动项状态"),
    keyword: Optional[str] = Query(None, description="内容/会议主题关键字"),
    due_start: Optional[str] = Query(None, description="截止日期起（YYYY-MM-DD）"),
    due_end: Optional[str] = Query(None, description="截止日期止（YYYY-MM-DD）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=1000, description="每页条数"),
    db: Session = Depends(get_db),
):
    """会议行动项列表：跨会议查询所有行动项，支持筛选与分页。"""
    data = meeting_service.list_actions(
        db,
        meeting_id=meeting_id,
        owner=owner,
        status=status,
        keyword=keyword,
        due_start=due_start,
        due_end=due_end,
        page=page,
        page_size=page_size,
    )
    return success(data=data)


@router.put("/{meeting_id}/actions/{action_id}")
def update_action(
    meeting_id: int,
    action_id: int,
    obj_in: MeetingActionUpdate,
    db: Session = Depends(get_db),
):
    """编辑会议行动项内容/负责人/截止日期/状态。"""
    obj = meeting_service.update_action(
        db,
        meeting_id=meeting_id,
        action_id=action_id,
        obj_in=obj_in.model_dump(exclude_unset=True),
    )
    return success(data=obj)


@router.put("/{meeting_id}/actions/{action_id}/status")
def update_action_status(
    meeting_id: int,
    action_id: int,
    obj_in: MeetingActionStatusUpdateRequest,
    db: Session = Depends(get_db),
):
    """更新会议行动项状态。"""
    obj = meeting_service.update_action_status(db, meeting_id, action_id, obj_in.status.value)
    return success(data=obj)


@router.post("/{meeting_id}/actions/{action_id}/supervise")
def supervise_action(
    meeting_id: int,
    action_id: int,
    obj_in: MeetingActionSuperviseRequest,
    db: Session = Depends(get_db),
):
    """对会议行动项发起督办邮件。"""
    result = meeting_service.supervise_action(
        db,
        meeting_id=meeting_id,
        action_id=action_id,
        scene=obj_in.scene,
        recipients=obj_in.recipients,
    )
    return success(data=result)
