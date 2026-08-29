import io
import json
import os
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from db.models import PmwbResearchIssue
from schemas.research import ResearchIssueCreate, ResearchIssueUpdate
from services.research import research_issue_service

# 一线调研工单附件统一存放目录（backend/uploads/research/{issue_id}/）
UPLOAD_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "uploads",
    "research",
)


def _human_size(num: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024:
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def _issue_folder(issue_id: int) -> str:
    folder = os.path.join(UPLOAD_ROOT, str(issue_id))
    os.makedirs(folder, exist_ok=True)
    return folder


def _parse_attachments(obj) -> List[dict]:
    if not getattr(obj, "attachments", None):
        return []
    try:
        data = json.loads(obj.attachments)
        return data if isinstance(data, list) else []
    except Exception:
        return []


router = APIRouter(prefix="/research", tags=["一线调研"])


@router.get("/issues")
def list_issues(
    keyword: Optional[str] = Query(None, description="关键字搜索"),
    city: Optional[str] = Query(None, description="地市"),
    sub_type: Optional[str] = Query(None, description="子类"),
    status: Optional[str] = Query(None, description="状态"),
    issue_nature: Optional[str] = Query(None, description="问题性质"),
    vendor_handler: Optional[str] = Query(None, description="厂家责任人"),
    business_admin: Optional[str] = Query(None, description="业务管理员"),
    related_req_id: Optional[str] = Query(None, description="关联需求编号"),
    related_issue_id: Optional[int] = Query(None, description="关联运营/调研工单ID"),
    related_meeting_id: Optional[int] = Query(None, description="关联会议ID"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=1000, description="每页条数"),
    db: Session = Depends(get_db),
):
    """查询一线调研工单列表。"""
    data = research_issue_service.list_with_filters(
        db=db,
        keyword=keyword,
        city=city,
        sub_type=sub_type,
        status=status,
        issue_nature=issue_nature,
        vendor_handler=vendor_handler,
        business_admin=business_admin,
        related_req_id=related_req_id,
        related_issue_id=related_issue_id,
        related_meeting_id=related_meeting_id,
        page=page,
        page_size=page_size,
    )
    return success(data=data)


@router.get("/issues/{issue_id}")
def get_issue(issue_id: int, db: Session = Depends(get_db)):
    """获取一线调研工单详情。"""
    obj = research_issue_service.get(db, issue_id)
    if not obj:
        raise HTTPException(status_code=404, detail="工单不存在")
    return success(data=obj)


@router.post("/issues")
def create_issue(obj_in: ResearchIssueCreate, db: Session = Depends(get_db)):
    """创建一线调研工单。"""
    obj = research_issue_service.create(db, obj_in.model_dump())
    return success(data=obj)


@router.put("/issues/{issue_id}")
def update_issue(issue_id: int, obj_in: ResearchIssueUpdate, db: Session = Depends(get_db)):
    """更新一线调研工单。"""
    obj = research_issue_service.update(db, issue_id, obj_in.model_dump(exclude_unset=True))
    if not obj:
        raise HTTPException(status_code=404, detail="工单不存在")
    return success(data=obj)


@router.delete("/issues/{issue_id}")
def delete_issue(issue_id: int, db: Session = Depends(get_db)):
    """删除一线调研工单。"""
    ok = research_issue_service.delete(db, issue_id)
    return success(data=ok)


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """获取一线调研工单统计。"""
    return success(data=research_issue_service.get_stats(db))


@router.post("/issues/{issue_id}/status")
def update_issue_status(
    issue_id: int,
    status: str = Query(..., description="新状态"),
    db: Session = Depends(get_db),
):
    """变更一线调研工单状态。"""
    obj = research_issue_service.update_status(db, issue_id, status)
    if not obj:
        raise HTTPException(status_code=404, detail="工单不存在")
    return success(data=obj)


@router.get("/issues/{issue_id}/attachments")
def list_issue_attachments(issue_id: int, db: Session = Depends(get_db)):
    """列出工单当前附件（元信息）。"""
    obj = research_issue_service.get(db, issue_id)
    if not obj:
        raise HTTPException(status_code=404, detail="工单不存在")
    return success(data=_parse_attachments(obj))


@router.post("/issues/{issue_id}/attachments/upload")
def upload_issue_attachment(
    issue_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """上传一线调研工单附件。"""
    obj = research_issue_service.get(db, issue_id)
    if not obj:
        raise HTTPException(status_code=404, detail="工单不存在")
    folder = _issue_folder(issue_id)
    safe_name = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", file.filename or "未命名文件")
    fp = os.path.join(folder, safe_name)
    content = file.file.read()
    with open(fp, "wb") as f:
        f.write(content)
    meta = {"name": safe_name, "bytes": len(content), "size": _human_size(len(content))}
    atts = _parse_attachments(obj)
    atts.append(meta)
    obj.attachments = json.dumps(atts, ensure_ascii=False)
    db.commit()
    return success(data=atts, message="上传成功")


@router.post("/issues/{issue_id}/attachments/delete")
def delete_issue_attachment(
    issue_id: int,
    filename: str = Query(..., description="附件文件名"),
    db: Session = Depends(get_db),
):
    """删除一线调研工单附件。"""
    obj = research_issue_service.get(db, issue_id)
    if not obj:
        raise HTTPException(status_code=404, detail="工单不存在")
    folder = os.path.join(UPLOAD_ROOT, str(issue_id))
    fp = os.path.join(folder, os.path.basename(filename))
    if not os.path.abspath(fp).startswith(os.path.abspath(folder)):
        raise HTTPException(status_code=403, detail="非法路径")
    if os.path.isfile(fp):
        os.remove(fp)
    atts = [a for a in _parse_attachments(obj) if a.get("name") != filename]
    obj.attachments = json.dumps(atts, ensure_ascii=False)
    db.commit()
    return success(data=atts, message="删除成功")


@router.get("/issues/{issue_id}/attachments/download")
def download_issue_attachment(
    issue_id: int,
    filename: str = Query(..., description="附件文件名"),
    db: Session = Depends(get_db),
):
    """下载一线调研工单附件。"""
    folder = os.path.join(UPLOAD_ROOT, str(issue_id))
    fp = os.path.join(folder, os.path.basename(filename))
    if not os.path.abspath(fp).startswith(os.path.abspath(folder)) or not os.path.isfile(fp):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(fp, filename=os.path.basename(fp))
