from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from schemas.meeting import MeetingCreate, MeetingMailSendRequest, MeetingUpdate
from services.meeting import meeting_service
from services.obsidian_link import sediment_meeting

router = APIRouter(prefix="/meetings", tags=["会议管理"])


@router.get("")
def list_meetings(
    keyword: Optional[str] = Query(None, description="关键字搜索"),
    meeting_type: Optional[str] = Query(None, description="会议类型"),
    status: Optional[str] = Query(None, description="状态"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=1000, description="每页条数"),
    db: Session = Depends(get_db),
):
    """查询会议列表。"""
    return success(data=meeting_service.list_with_filters(
        db=db,
        keyword=keyword,
        meeting_type=meeting_type,
        status=status,
        page=page,
        page_size=page_size,
    ))


@router.get("/{meeting_id}")
def get_meeting(meeting_id: int, db: Session = Depends(get_db)):
    """获取会议详情。"""
    obj = meeting_service.get(db, meeting_id)
    return success(data=obj)


@router.post("")
def create_meeting(obj_in: MeetingCreate, db: Session = Depends(get_db)):
    """创建会议。"""
    obj = meeting_service.create_with_relations(db, obj_in.model_dump())
    return success(data=obj)


@router.put("/{meeting_id}")
def update_meeting(meeting_id: int, obj_in: MeetingUpdate, db: Session = Depends(get_db)):
    """更新会议。"""
    obj = meeting_service.update(db, meeting_id, obj_in.model_dump(exclude_unset=True))
    return success(data=obj)


@router.delete("/{meeting_id}")
def delete_meeting(meeting_id: int, db: Session = Depends(get_db)):
    """删除会议。"""
    ok = meeting_service.delete(db, meeting_id)
    return success(data=ok)


@router.post("/{meeting_id}/sediment")
def sediment_meeting_endpoint(meeting_id: int, db: Session = Depends(get_db)):
    """一键沉淀：把会议生成知识条目写入 Obsidian 并建双向索引。"""
    return success(data=sediment_meeting(db, meeting_id))


@router.post("/{meeting_id}/actions/{action_id}/sync-todo")
def sync_action_todo_endpoint(meeting_id: int, action_id: int, db: Session = Depends(get_db)):
    """把会议行动项同步为 PMWB 待办任务（带分类/模板元数据，source=meeting）。"""
    return success(data=meeting_service.sync_action_todo(db, meeting_id, action_id))


@router.post("/{meeting_id}/send-mail")
def send_meeting_mail(meeting_id: int, obj_in: MeetingMailSendRequest, db: Session = Depends(get_db)):
    """一键发送会议邮件（通知/纪要）。

    - 计划中(planned)：发送会议通知，mail_type=meeting_notice
    - 已召开(held)：发送会议纪要，mail_type=meeting_minutes
    收件人邮箱严格校验，记录入 email_records，走统一邮件中心(3210)发信。
    """
    return success(data=meeting_service.send_mail(
        db,
        meeting_id,
        to=obj_in.to,
        cc=obj_in.cc,
        subject=obj_in.subject,
        body=obj_in.body,
        mail_type=obj_in.mail_type,
        recipient_names=obj_in.recipient_names,
    ))
