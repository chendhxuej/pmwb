import io
import json
import os
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from db.models import PmwbOperationAnalysis
from schemas.operation import OperationIssueCreate, OperationIssueUpdate
from services.obsidian_link import sediment_operation_issue
from services.operation import operation_issue_service
from services.operation_analysis import (
    build_analysis_template_bytes,
    get_analysis_detail,
    import_analysis_workbook,
)

# 运营工单附件统一存放目录（backend/uploads/operation/{issue_id}/）
UPLOAD_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "uploads",
    "operation",
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

router = APIRouter(prefix="/operation", tags=["业务运营监控"])


@router.get("/issues")
def list_issues(
    keyword: Optional[str] = Query(None, description="关键字搜索"),
    category: Optional[str] = Query(None, description="工单大类"),
    issue_type: Optional[str] = Query(None, description="问题子类"),
    status: Optional[str] = Query(None, description="状态"),
    impact_level: Optional[str] = Query(None, description="影响等级"),
    handler: Optional[str] = Query(None, description="处理人"),
    related_system: Optional[str] = Query(None, description="关联系统"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=1000, description="每页条数"),
    db: Session = Depends(get_db),
):
    """查询工单列表。"""
    data = operation_issue_service.list_with_filters(
        db=db,
        keyword=keyword,
        category=category,
        issue_type=issue_type,
        status=status,
        impact_level=impact_level,
        handler=handler,
        related_system=related_system,
        page=page,
        page_size=page_size,
    )
    return success(data=data)


@router.get("/issues/{issue_id}")
def get_issue(issue_id: int, db: Session = Depends(get_db)):
    """获取问题详情。"""
    obj = operation_issue_service.get(db, issue_id)
    return success(data=obj)


@router.post("/issues")
def create_issue(obj_in: OperationIssueCreate, db: Session = Depends(get_db)):
    """创建问题。"""
    obj = operation_issue_service.create(db, obj_in.model_dump())
    return success(data=obj)


@router.put("/issues/{issue_id}")
def update_issue(issue_id: int, obj_in: OperationIssueUpdate, db: Session = Depends(get_db)):
    """更新问题。"""
    obj = operation_issue_service.update(db, issue_id, obj_in.model_dump(exclude_unset=True))
    return success(data=obj)


@router.delete("/issues/{issue_id}")
def delete_issue(issue_id: int, db: Session = Depends(get_db)):
    """删除问题。"""
    ok = operation_issue_service.delete(db, issue_id)
    return success(data=ok)


@router.post("/issues/{issue_id}/sediment")
def sediment_issue(
    issue_id: int,
    force: bool = Query(False, description="true 时覆盖已存在的工单知识文件"),
    db: Session = Depends(get_db),
):
    """一键沉淀：把运营工单生成知识条目写入 Obsidian 并建双向索引。"""
    return success(data=sediment_operation_issue(db, issue_id, force=force))


@router.get("/issues/{issue_id}/attachments")
def list_issue_attachments(issue_id: int, db: Session = Depends(get_db)):
    """列出工单当前附件（元信息）。"""
    obj = operation_issue_service.get(db, issue_id)
    if not obj:
        return success(data=[])
    return success(data=_parse_attachments(obj))


@router.post("/issues/{issue_id}/attachments/upload")
def upload_issue_attachment(
    issue_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """上传工单附件：落盘到 backend/uploads/operation/{issue_id}/，并把元信息写入工单 attachments 字段。"""
    obj = operation_issue_service.get(db, issue_id)
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
    """删除工单附件：同时移除文件与工单 attachments 中的元信息。"""
    obj = operation_issue_service.get(db, issue_id)
    if not obj:
        raise HTTPException(status_code=404, detail="工单不存在")
    folder = os.path.join(UPLOAD_ROOT, str(issue_id))
    fp = os.path.join(folder, os.path.basename(filename))
    # 防止路径穿越：必须落在工单统一文件夹内
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
    """下载工单附件。"""
    folder = os.path.join(UPLOAD_ROOT, str(issue_id))
    fp = os.path.join(folder, os.path.basename(filename))
    if not os.path.abspath(fp).startswith(os.path.abspath(folder)) or not os.path.isfile(fp):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(fp, filename=os.path.basename(fp))


@router.get("/stats")
def get_stats(
    category: Optional[str] = Query(None, description="工单大类(不传则返回全部)"),
    db: Session = Depends(get_db),
):
    """获取运营工单统计。"""
    return success(data=operation_issue_service.get_stats(db, category=category))


@router.get("/analysis-template/download")
def download_analysis_template():
    """下载主动运营分析工单 Excel 模板（双 sheet：填写区 + 填写说明）。"""
    data = build_analysis_template_bytes()
    from urllib.parse import quote

    fname = "主动运营分析工单模版.xlsx"
    # HTTP 响应头只能含 latin-1 字符，中文文件名须按 RFC 5987 用 filename* 编码，
    # 同时保留一个 ASCII 的 filename 作为兼容回退，避免 Starlette 编码中文时 500。
    disp = f"attachment; filename=\"analysis_template.xlsx\"; filename*=UTF-8''{quote(fname)}"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": disp},
    )


@router.post("/analysis/import")
def import_analysis(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """导入主动运营分析工单：解析 Excel → 建分析工单+明细 → 遗留任务自动建人员代办任务工单。"""
    content = file.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")
    try:
        result = import_analysis_workbook(db, content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"解析失败：{e}")
    return success(data=result, message="导入成功")


@router.get("/issues/{issue_id}/analysis")
def get_analysis(issue_id: int, db: Session = Depends(get_db)):
    """获取分析工单明细 + 关联遗留任务工单（人员代办任务）。"""
    data = get_analysis_detail(db, issue_id)
    if not data["issue"]:
        raise HTTPException(status_code=404, detail="工单不存在")
    return success(data=data)
