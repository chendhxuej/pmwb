"""需求交付相关端点：附件文件夹、DDD 用户故事、需求分析说明书生成。

挂在 /api/v1/requirements 下（与需求管理同前缀，路由不冲突）。
"""
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from schemas.requirement_delivery import (
    DocGenIn,
    DevEventIn,
    DevEventOut,
    FolderInitOut,
    GenerateDocOut,
    ManualSystemsOut,
    ManualUploadOut,
    StageLogOut,
    StageLogUpdate,
    UserStoryGenIn,
    UserStoryGenOut,
    UserStoryItem,
    UserStoryListOut,
)
from services import requirement_delivery as svc
from services import requirement_stage as stage_svc

router = APIRouter(prefix="/requirements", tags=["需求交付"])


@router.post("/{req_id}/delivery/init-folder")
def init_folder(req_id: str, db: Session = Depends(get_db)):
    """创建需求附件文件夹与说明书归档文件夹（幂等）。"""
    data: Dict[str, Any] = svc.init_folder(db, req_id)
    return success(data=FolderInitOut(**data).model_dump())


@router.get("/{req_id}/delivery/attachments")
def list_attachments(req_id: str, db: Session = Depends(get_db)):
    """列出需求附件文件夹内所有文件。"""
    data = svc.list_attachments(db, req_id)
    return success(data=data)


@router.post("/{req_id}/delivery/attachments/upload")
def upload_attachment(
    req_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """上传一个附件到需求附件文件夹。"""
    content = file.file.read()
    data = svc.upload_attachment(db, req_id, file.filename or "未命名文件", content)
    return success(data=data, message="上传成功")


@router.post("/{req_id}/delivery/attachments/delete")
def delete_attachment(
    req_id: str,
    filename: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    """删除需求附件文件夹内的一个文件。"""
    try:
        ok = svc.delete_attachment(db, req_id, filename)
    except OSError as e:
        # 某些受保护环境（如沙箱）禁止程序化删除，给出明确提示而非 500
        raise HTTPException(status_code=409, detail=f"删除被环境拒绝：{e}")
    return success(data={"deleted": ok}, message="删除成功" if ok else "文件不存在")


@router.post("/{req_id}/delivery/upload-manual")
def upload_manual(
    req_id: str,
    file: UploadFile = File(...),
    note: str = Form("操作手册"),
    db: Session = Depends(get_db),
):
    """上传操作手册并自动归档到业务知识交付物目录，同步主笔记 §6 内链。

    仅 status=closed 且已设置业务领域的需求可调用。
    """
    content = file.file.read()
    try:
        data = svc.upload_requirement_manual(
            db, req_id, file.filename or "未命名文件", content, note=note
        )
    except Exception as e:
        # 统一把业务异常消息抛给前端
        status = getattr(e, "status_code", 500)
        detail = getattr(e, "message", str(e))
        raise HTTPException(status_code=status, detail=detail)
    return success(data=ManualUploadOut(**data).model_dump(), message="操作手册已上传并关联主笔记")


@router.get("/{req_id}/delivery/attachments/download")
def download_attachment(
    req_id: str,
    filename: str = Query(..., description="附件文件名"),
    db: Session = Depends(get_db),
):
    """下载统一文件夹内的一个文件。"""
    from db.models import SentEmail

    item = db.query(SentEmail).filter(SentEmail.req_id == req_id).first()
    paths = svc._resolve_paths(req_id, item.req_name if item else None)
    fp = os.path.join(paths["folder"], os.path.basename(filename))
    if not os.path.abspath(fp).startswith(os.path.abspath(paths["folder"])):
        raise HTTPException(status_code=403, detail="非法路径")
    if not os.path.isfile(fp):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(fp, filename=os.path.basename(fp))


@router.get("/{req_id}/delivery/stories")
def list_user_stories(req_id: str, db: Session = Depends(get_db)):
    """读取需求下已持久化的用户故事。"""
    data = svc.get_user_stories(db, req_id)
    return success(data=UserStoryListOut(**data).model_dump())


@router.put("/{req_id}/delivery/stories")
def save_user_stories(
    req_id: str,
    payload: List[UserStoryItem],
    db: Session = Depends(get_db),
):
    """全量保存需求下的用户故事。"""
    stories = [p.model_dump() for p in payload]
    data = svc.save_user_stories(db, req_id, stories)
    return success(data=UserStoryListOut(**data).model_dump())


@router.post("/{req_id}/delivery/generate-user-stories")
def generate_user_stories(
    req_id: str,
    payload: UserStoryGenIn,
    db: Session = Depends(get_db),
):
    """基于澄清内容生成用户故事（策略可切换）。

    strategy 可选值：
    - rules_v2（默认/推荐）：合并优先策略，符合公司最新管理规范
    - rules_v1：旧版按行/人天拆分
    - llm：AI 智能生成（复用 AI 中心统一大模型注册表，无需单独配置）
    """
    data = svc.generate_user_stories(db, req_id, payload.content, strategy=payload.strategy)
    return success(data=UserStoryGenOut(**data).model_dump())


@router.get("/delivery/llm-status")
def get_llm_status(db: Session = Depends(get_db)):
    """查询 AI 中心统一大模型状态（用户故事 AI 生成可用性的前端提示）。

    复用 services.llm_provider.get_status，与「大模型管理」配置同源，
    不再依赖独立的 US_STORY_LLM_* 配置。

    Returns:
        { available, provider_name, provider_count, notice }
    """
    from services.llm_provider import get_status
    return success(data=get_status(db))


@router.post("/{req_id}/delivery/generate-doc")
def generate_doc(
    req_id: str,
    payload: DocGenIn,
    db: Session = Depends(get_db),
):
    """基于固定模板生成《需求分析说明书》，仅填充第1/2/3章，其余复用模板。"""
    data = svc.generate_doc(db, req_id, payload.stories, payload.clarification)
    return success(data=GenerateDocOut(**data).model_dump())


# ---------------------------------------------------------------------------
# 环节状态时间日志（6 环节进入/完成时间）
# ---------------------------------------------------------------------------


@router.get("/{req_id}/stage-logs")
def get_stage_logs(req_id: str, db: Session = Depends(get_db)):
    """获取需求 6 环节的时间日志（含存量数据推导回填）。"""
    data = stage_svc.get_stage_logs(db, req_id)
    return success(data=StageLogOut(**data).model_dump())


@router.put("/{req_id}/stage-logs/{stage}")
def update_stage_log(
    req_id: str,
    stage: str,
    payload: StageLogUpdate,
    db: Session = Depends(get_db),
):
    """手工修正某环节的进入/完成时间。"""
    data = stage_svc.update_stage_log(db, req_id, stage, payload.entered_at, payload.left_at)
    return success(data=data, message="环节时间已修正")


# ---------------------------------------------------------------------------
# 开发事件（启动开发环节）
# ---------------------------------------------------------------------------


@router.get("/{req_id}/dev-events")
def list_dev_events(req_id: str, db: Session = Depends(get_db)):
    """开发事件列表（按发生时间倒序）。"""
    return success(data=stage_svc.list_dev_events(db, req_id))


@router.post("/{req_id}/dev-events")
def create_dev_event(
    req_id: str,
    payload: DevEventIn,
    db: Session = Depends(get_db),
):
    """新增一条开发事件。"""
    data = stage_svc.create_dev_event(db, req_id, payload.model_dump())
    return success(data=DevEventOut(**data).model_dump(), message="开发事件已记录")


@router.put("/{req_id}/dev-events/{event_id}")
def update_dev_event(
    req_id: str,
    event_id: int,
    payload: DevEventIn,
    db: Session = Depends(get_db),
):
    """编辑一条开发事件。"""
    data = stage_svc.update_dev_event(db, req_id, event_id, payload.model_dump())
    return success(data=DevEventOut(**data).model_dump(), message="开发事件已更新")


@router.delete("/{req_id}/dev-events/{event_id}")
def delete_dev_event(req_id: str, event_id: int, db: Session = Depends(get_db)):
    """删除一条开发事件。"""
    ok = stage_svc.delete_dev_event(db, req_id, event_id)
    return success(data={"deleted": ok}, message="已删除" if ok else "事件不存在")


# ---------------------------------------------------------------------------
# 操作手册（生产部署环节，按系统/团队）
# ---------------------------------------------------------------------------


@router.get("/{req_id}/manuals")
def list_manuals(req_id: str, db: Session = Depends(get_db)):
    """按当前需求的团队（评估记录系统）列出操作手册；无手册的系统也返回（manual=None）。"""
    data = stage_svc.list_manual_systems(db, req_id)
    return success(data=ManualSystemsOut(**data).model_dump())


@router.post("/{req_id}/manuals/upload")
def upload_manual(
    req_id: str,
    file: UploadFile = File(...),
    system_name: str = Form(...),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    """上传/替换某系统的操作手册（一系统一份；已采纳/开发中/已上线均可）。"""
    content = file.file.read()
    try:
        data = stage_svc.upload_manual(
            db, req_id, system_name, file.filename or "操作手册", content, note=note
        )
    except Exception as e:
        status = getattr(e, "status_code", 500)
        detail = getattr(e, "message", str(e))
        raise HTTPException(status_code=status, detail=detail)
    msg = "操作手册已更新（替换旧版本）" if data.get("replaced") else "操作手册已上传"
    return success(data=data, message=msg)


@router.delete("/{req_id}/manuals/{manual_id}")
def delete_manual(req_id: str, manual_id: int, db: Session = Depends(get_db)):
    """删除某系统的操作手册（同时删除文件与交付物登记）。"""
    ok = stage_svc.delete_manual(db, req_id, manual_id)
    return success(data={"deleted": ok}, message="已删除" if ok else "手册不存在")


@router.get("/{req_id}/manuals/{manual_id}/download")
def download_manual(req_id: str, manual_id: int, db: Session = Depends(get_db)):
    """下载操作手册文件。"""
    m = stage_svc.get_manual(db, req_id, manual_id)
    fp = stage_svc.manual_abs_path(m)
    return FileResponse(fp, filename=m.file_name or os.path.basename(fp))


@router.get("/{req_id}/manuals/{manual_id}/preview")
def preview_manual(req_id: str, manual_id: int, db: Session = Depends(get_db)):
    """在线预览：docx 转 HTML；pdf 由前端直接以文件流打开。"""
    m = stage_svc.get_manual(db, req_id, manual_id)
    fp = stage_svc.manual_abs_path(m)
    ext = os.path.splitext(fp)[1].lower()
    if ext == ".docx":
        from fastapi.responses import HTMLResponse

        return HTMLResponse(stage_svc.manual_preview_html(m))
    if ext == ".pdf":
        return FileResponse(fp, media_type="application/pdf")
    raise HTTPException(status_code=400, detail="该格式不支持在线预览，请下载后查看")
