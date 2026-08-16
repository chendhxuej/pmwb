from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from db.models import PmwbMeeting, PmwbMeetingAction
from schemas.meeting import MeetingActionItemOut, MeetingCreate, MeetingMailSendRequest, MeetingUpdate
from services.meeting import meeting_service
from services.obsidian_link import delete_meeting_minutes, sediment_meeting

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
def sediment_meeting_endpoint(
    meeting_id: int,
    force: bool = Query(False, description="true 时覆盖已存在的纪要文件与索引"),
    db: Session = Depends(get_db),
):
    """一键沉淀：把会议生成知识条目写入 Obsidian 并建双向索引。"""
    return success(data=sediment_meeting(db, meeting_id, force=force))


@router.delete("/{meeting_id}/minutes")
def delete_meeting_minutes_endpoint(meeting_id: int, db: Session = Depends(get_db)):
    """删除会议纪要：清理 Obsidian 文件、知识索引与关联记录。"""
    return success(data=delete_meeting_minutes(db, meeting_id))


@router.get("/actions/{related_id}")
def get_action(related_id: int, db: Session = Depends(get_db)):
    """根据 ID 获取行动项详情或会议详情（兼容待办关联查询）。

    - 待办中心 todo.related_id 实际存的是 PmwbMeeting.id（见 sync_action_todo），
      所以这里同时支持两种查询：
      1) 若 related_id 是 PmwbMeetingAction.id → 返回单个 action + 所属会议标题；
      2) 否则按 PmwbMeeting.id 查会议，返回「会议详情 + 该会议下所有 actions」。

    返回结构：
    - kind='action' → {kind, action, meeting_id, meeting_title}
    - kind='meeting' → {kind, meeting_id, meeting_no, meeting_title, meeting_type,
                        start_time, end_time, location, host, summary,
                        actions: [序列化 action, ...]}
    """
    def _serialize_action(action: PmwbMeetingAction, meeting: Optional[PmwbMeeting]) -> dict:
        """把 PmwbMeetingAction 序列化成 MeetingActionItemOut 兼容结构（手动注入 meeting 信息）。"""
        return {
            "id": action.id,
            "meeting_id": action.meeting_id,
            "meeting_title": meeting.title if meeting else "",
            "meeting_id_no": meeting.meeting_id if meeting else "",
            "content": action.content,
            "title": action.title,
            "owner": action.owner,
            "due_date": action.due_date.isoformat() if action.due_date else None,
            "status": action.status,
            "category": action.category,
            "template": action.template,
            "related_todo_id": action.related_todo_id,
            "created_at": action.created_at.isoformat() if action.created_at else None,
            "updated_at": action.updated_at.isoformat() if action.updated_at else None,
        }

    # 1) 优先按 action_id 查
    action = db.query(PmwbMeetingAction).filter(PmwbMeetingAction.id == related_id).first()
    if action:
        meeting = db.query(PmwbMeeting).filter(PmwbMeeting.id == action.meeting_id).first()
        return success(data={
            "kind": "action",
            "action": _serialize_action(action, meeting),
            "meeting_id": meeting.id if meeting else None,
            "meeting_title": meeting.title if meeting else None,
        })

    # 2) 回退按 meeting_id 查
    meeting = db.query(PmwbMeeting).filter(PmwbMeeting.id == related_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail=f"行动项或会议 {related_id} 不存在")

    actions = (
        db.query(PmwbMeetingAction)
        .filter(PmwbMeetingAction.meeting_id == meeting.id)
        .order_by(PmwbMeetingAction.id.asc())
        .all()
    )
    action_items = [_serialize_action(a, meeting) for a in actions]
    return success(data={
        "kind": "meeting",
        "meeting_id": meeting.id,
        "meeting_no": meeting.meeting_id,
        "meeting_title": meeting.title,
        "meeting_type": meeting.meeting_type,
        "start_time": meeting.start_time.isoformat() if meeting.start_time else None,
        "end_time": meeting.end_time.isoformat() if meeting.end_time else None,
        "location": meeting.location,
        "host": meeting.host,
        "summary": meeting.summary,
        "status": meeting.status,
        "actions": action_items,
    })


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
