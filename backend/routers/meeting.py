import os
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from db.models import PmwbMeeting, PmwbMeetingAction
from schemas.meeting import (
    AttendeeTemplateCreate,
    AttendeeTemplateUpdate,
    MeetingActionItemOut,
    MeetingCreate,
    MeetingMailSendRequest,
    MeetingTypeDictCreate,
    MeetingTypeDictUpdate,
    MeetingUpdate,
)
from services.meeting import meeting_service
from services.meeting_attachment import meeting_attachment_service
from services.meeting_attendee_template import meeting_attendee_template_service
from services.meeting_attendee_template import meeting_attendee_template_service
from services.meeting_type import meeting_type_service
from services.obsidian_link import delete_meeting_minutes, sediment_meeting

router = APIRouter(prefix="/meetings", tags=["会议管理"])


# ---------------------------------------------------------------------------
# 会议类型字典（唯一真相源 = pmwb_meeting_type，services/meeting_type.py）
# 注意：字面路径必须注册在 GET /{meeting_id} 之前，否则 "types" 会被吞成 meeting_id
# ---------------------------------------------------------------------------


@router.get("/types")
def list_meeting_types(db: Session = Depends(get_db)):
    """类型管理视图：全量（含停用），带会议引用计数。"""
    return success(data=meeting_type_service.list_types(db))


@router.get("/types/options")
def list_meeting_type_options(db: Session = Depends(get_db)):
    """类型下拉选项：仅启用，按排序号排序，含展示色。"""
    return success(data=meeting_type_service.list_options(db))


@router.post("/types")
def create_meeting_type(obj_in: MeetingTypeDictCreate, db: Session = Depends(get_db)):
    """新增类型（名称去重校验）。"""
    try:
        data = meeting_type_service.create_type(db, obj_in.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(data=data, message=f"类型「{data['name']}」已创建")


@router.put("/types/{type_id}")
def update_meeting_type(type_id: int, obj_in: MeetingTypeDictUpdate, db: Session = Depends(get_db)):
    """更新类型；改名时级联更新存量会议的 meeting_type（保证统计口径不分裂）。"""
    try:
        data = meeting_type_service.update_type(db, type_id, obj_in.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(data=data)


@router.delete("/types/{type_id}")
def delete_meeting_type(type_id: int, db: Session = Depends(get_db)):
    """删除类型：被会议引用时 400 拒绝（提示改用停用）。"""
    try:
        data = meeting_type_service.delete_type(db, type_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(data=data, message=f"类型「{data.get('name')}」已删除")


# ---------------------------------------------------------------------------
# 参会人预制模板：同样属于字面路径，必须注册在 GET /{meeting_id} 之前
# ---------------------------------------------------------------------------


@router.get("/attendee-templates")
def list_attendee_templates(
    meeting_type: Optional[str] = Query(None, description="按会议类型过滤"),
    enabled_only: bool = Query(False, description="仅启用（会议弹窗下拉用）"),
    db: Session = Depends(get_db),
):
    """参会人模板列表：可按会议类型过滤、可仅取启用项。"""
    return success(
        data=meeting_attendee_template_service.list_templates(
            db, meeting_type=meeting_type, enabled_only=enabled_only
        )
    )


@router.post("/attendee-templates")
def create_attendee_template(obj_in: AttendeeTemplateCreate, db: Session = Depends(get_db)):
    """新增参会人模板（同类型下模板名去重）。"""
    try:
        data = meeting_attendee_template_service.create_template(db, obj_in.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(data=data, message=f"模板「{data['name']}」已创建")


@router.put("/attendee-templates/{template_id}")
def update_attendee_template(
    template_id: int, obj_in: AttendeeTemplateUpdate, db: Session = Depends(get_db)
):
    """更新参会人模板（部分更新）。"""
    try:
        data = meeting_attendee_template_service.update_template(
            db, template_id, obj_in.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(data=data)


@router.delete("/attendee-templates/{template_id}")
def delete_attendee_template(template_id: int, db: Session = Depends(get_db)):
    """删除参会人模板。"""
    try:
        data = meeting_attendee_template_service.delete_template(db, template_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(data=data, message="模板已删除")


def _with_parsed_attachments(payload: dict) -> dict:
    """把响应里 pmwb_meeting.attachments 的 JSON 文本统一解析成数组（前端不再二次解析）。"""
    data = payload.get("data") or {}
    rows = data.get("items") if isinstance(data, dict) and "items" in data else (
        [data] if isinstance(data, dict) and "attachments" in data else []
    )
    for row in rows:
        if isinstance(row, dict) and "attachments" in row:
            row["attachments"] = meeting_attachment_service.parse_attachments(row.get("attachments"))
    return payload


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
    return _with_parsed_attachments(success(data=meeting_service.list_with_filters(
        db=db,
        keyword=keyword,
        meeting_type=meeting_type,
        status=status,
        page=page,
        page_size=page_size,
    )))


@router.get("/{meeting_id}")
def get_meeting(meeting_id: int, db: Session = Depends(get_db)):
    """获取会议详情。"""
    obj = meeting_service.get(db, meeting_id)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"会议不存在：id={meeting_id}")
    return _with_parsed_attachments(success(data=obj))


# ---------------------------------------------------------------------------
# 会议附件：唯一实现 services/meeting_attachment.py（上传=同名替换，删除=文件+元数据同删）
# ---------------------------------------------------------------------------


@router.post("/{meeting_id}/attachments")
async def upload_meeting_attachment(
    meeting_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """上传会议附件（同名文件自动替换并刷新元数据）。"""
    content = await file.read()
    data = meeting_attachment_service.upload(db, meeting_id, file.filename or "未命名文件", content)
    msg = f"附件「{data['entry']['name']}」已替换" if data["replaced"] else "上传成功"
    return success(data={"items": data["items"], "replaced": data["replaced"]}, message=msg)


@router.delete("/{meeting_id}/attachments")
def delete_meeting_attachment(
    meeting_id: int,
    name: str = Query(..., description="附件文件名"),
    db: Session = Depends(get_db),
):
    """删除会议附件：文件实体与元数据同删。"""
    try:
        data = meeting_attachment_service.delete(db, meeting_id, name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(data={"items": data["items"]}, message=f"附件「{data['deleted']}」已删除")


@router.get("/{meeting_id}/attachments/download")
def download_meeting_attachment(
    meeting_id: int,
    name: str = Query(..., description="附件文件名"),
    db: Session = Depends(get_db),
):
    """下载会议附件（走 JWT 鉴权，前端统一 downloadWithAuth，禁裸 URL）。"""
    items = meeting_attachment_service.list_attachments(db, meeting_id)
    safe = meeting_attachment_service.sanitize_filename(name)
    if not any(it.get("name") == safe for it in items):
        raise HTTPException(status_code=404, detail=f"附件不存在：{safe}")
    fp = meeting_attachment_service.file_path(meeting_id, safe)
    if not os.path.exists(fp):
        raise HTTPException(status_code=404, detail="附件文件已丢失，请重新上传")
    return FileResponse(fp, filename=safe)


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
    附件：缺省自动带出全部会议附件；attachments 为邮件弹窗手工管理结果
    （会议附件裁剪 + 临时新增），见 MeetingMailSendRequest.attachments。
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
        attachments=obj_in.attachments,
        confirm_send=obj_in.confirm_send,
    ))
