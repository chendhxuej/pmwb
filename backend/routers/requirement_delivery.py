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
    FolderInitOut,
    GenerateDocOut,
    UserStoryGenIn,
    UserStoryGenOut,
)
from services import requirement_delivery as svc

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


@router.get("/{req_id}/delivery/attachments/download")
def download_attachment(
    req_id: str,
    filename: str = Query(..., description="附件文件名"),
    db: Session = Depends(get_db),
):
    """下载需求附件文件夹内的一个文件。"""
    from db.models import SentEmail

    item = db.query(SentEmail).filter(SentEmail.req_id == req_id).first()
    paths = svc._resolve_paths(req_id, item.req_name if item else None)
    fp = os.path.join(paths["att_folder"], os.path.basename(filename))
    if not os.path.abspath(fp).startswith(os.path.abspath(paths["att_folder"])):
        raise HTTPException(status_code=403, detail="非法路径")
    if not os.path.isfile(fp):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(fp, filename=os.path.basename(fp))


@router.post("/{req_id}/delivery/generate-user-stories")
def generate_user_stories(
    req_id: str,
    payload: UserStoryGenIn,
    db: Session = Depends(get_db),
):
    """基于澄清内容，按 DDD 理念生成固定 4 段模板用户故事。"""
    data = svc.generate_user_stories(db, req_id, payload.content)
    return success(data=UserStoryGenOut(**data).model_dump())


@router.post("/{req_id}/delivery/generate-doc")
def generate_doc(
    req_id: str,
    payload: DocGenIn,
    db: Session = Depends(get_db),
):
    """基于固定模板生成《需求分析说明书》，仅填充第1/2/3章，其余复用模板。"""
    data = svc.generate_doc(db, req_id, payload.stories, payload.clarification)
    return success(data=GenerateDocOut(**data).model_dump())
