"""业务资料库 - 接口层。

材料只登记指针、不搬迁物理文件：下载/预览按 storage_root+rel_path 还原绝对路径。
手工上传才落盘到 uploads/material/。
"""

from __future__ import annotations

import os
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from urllib.parse import quote

from core.config import settings
from core.response import success
from db.base import get_db
from db.models import PmwbMaterial
from schemas import material as sch
from services import material as mat_service
from services.material_sync import sync_all
from utils import file_storage as fs
from utils.file_preview import build_preview

router = APIRouter(prefix="/materials", tags=["业务资料库-材料"])


@router.get("")
def list_materials(
    keyword: str = Query("", description="模糊搜索：文件名/备注/标签/来源单号/标题"),
    source_type: str = Query("", description="来源类型筛选"),
    category_id: int = Query(None, description="分类ID（含其全部子孙）"),
    file_ext: str = Query("", description="扩展名筛选，如 xlsx"),
    domain_code: str = Query("", description="业务领域编码筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    data = mat_service.list_materials(
        db,
        keyword=keyword or None,
        source_type=source_type or None,
        category_id=category_id,
        file_ext=file_ext or None,
        domain_code=domain_code or None,
        page=page,
        page_size=page_size,
    )
    return success(data=data)


@router.post("/sync")
def trigger_sync(db: Session = Depends(get_db)):
    """手动触发全量汇聚（六来源扫描式 upsert）。"""
    res = sync_all(db)
    return success(data=sch.MaterialSyncResponse(**res).model_dump())


@router.get("/{mid}/download")
def download_material(mid: int, db: Session = Depends(get_db)):
    m = db.query(PmwbMaterial).filter(PmwbMaterial.id == mid).first()
    if not m:
        raise HTTPException(status_code=404, detail="材料不存在")
    full = fs.abs_path(m.storage_root, m.rel_path)
    if not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="物理文件已不存在")
    m.download_count = (m.download_count or 0) + 1
    db.commit()
    return FileResponse(full, filename=m.file_name)


@router.get("/{mid}/inline")
def inline_material(mid: int, db: Session = Depends(get_db)):
    """原样输出（inline），供 pdf/图片/htm 直接 iframe 预览。"""
    m = db.query(PmwbMaterial).filter(PmwbMaterial.id == mid).first()
    if not m:
        raise HTTPException(status_code=404, detail="材料不存在")
    full = fs.abs_path(m.storage_root, m.rel_path)
    if not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="物理文件已不存在")
    media = m.file_type or "application/octet-stream"
    disp = f"inline; filename*=UTF-8''{quote(m.file_name)}"
    return FileResponse(full, media_type=media, content_disposition_type="inline",
                        headers={"Content-Disposition": disp})


@router.get("/{mid}/preview")
def preview_material(mid: int, db: Session = Depends(get_db)):
    """在线预览：返回 {mode, html/text/reason} 或 404/不支持提示。"""
    m = db.query(PmwbMaterial).filter(PmwbMaterial.id == mid).first()
    if not m:
        raise HTTPException(status_code=404, detail="材料不存在")
    try:
        result = build_preview(m.storage_root, m.rel_path, file_ext_hint=m.file_ext)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="物理文件已不存在")
    if result["mode"] == "stream":
        return success(data={"mode": "stream", "ext": result["ext"]})
    return success(data=result)


@router.post("/{mid}/category")
def reassign_material_category(
    mid: int, body: sch.MaterialReassign, db: Session = Depends(get_db)
):
    try:
        m = mat_service.reassign_category(db, mid, body.category_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(data={"id": m.id, "category_id": m.category_id})


@router.delete("/{mid}")
def delete_material(
    mid: int,
    remove_physical: bool = Query(False, description="同时删除物理文件（仅手工上传生效）"),
    db: Session = Depends(get_db),
):
    try:
        info = mat_service.delete_material(db, mid, remove_physical=remove_physical)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return success(data=info)


@router.post("/upload")
def upload_material(
    file: UploadFile = File(...),
    category_id: int = Form(None, description="归属分类ID（multipart 表单字段）"),
    note: str = Form("", description="备注"),
    uploaded_by: str = Form("陈大海", description="上传人"),
    db: Session = Depends(get_db),
):
    """手工上传材料：落盘 uploads/material/ 并登记索引。

    大小限制与扩展名黑名单由 utils.file_storage.save_upload 统一校验，
    超限/非法类型会直接抛出 413 / 400。
    """
    try:
        m = mat_service.upload_material(
            db,
            file=file,
            category_id=category_id,
            note=note or None,
            uploaded_by=uploaded_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(
        data=sch.MaterialUploadResult(
            id=m.id,
            file_name=m.file_name,
            file_size=m.file_size or 0,
            file_ext=m.file_ext or "",
            category_id=m.category_id,
        ).model_dump()
    )


# ---------------------------------------------------------- 批量上传 / 批量归类
@router.post("/upload-check")
def check_upload_conflicts(body: sch.MaterialUploadCheckIn, db: Session = Depends(get_db)):
    """上传前重名预检：返回同分类下已存在的同名文件清单，供前端二次确认。不落盘。"""
    conflicts = mat_service.check_upload_conflicts(
        db, category_id=body.category_id, file_names=body.file_names
    )
    return success(data=sch.MaterialUploadCheckOut(conflicts=conflicts).model_dump())


@router.post("/upload-batch")
def upload_materials_batch(
    files: List[UploadFile] = File(..., description="批量文件，字段名 files"),
    category_id: int = Form(None, description="归属分类ID，统一设置（multipart 表单字段）"),
    note: str = Form("", description="备注，批量同写"),
    uploaded_by: str = Form("陈大海", description="上传人"),
    dup_action: str = Form("skip", description="重名处理：skip=跳过 / force=仍上传副本"),
    db: Session = Depends(get_db),
):
    """同类批量上传：一次选择多个文件 + 统一设置分类/备注，一步到位。

    逐文件独立落盘入库，单个文件失败（超限/非法类型/入库异常）不影响其他文件，
    失败清单连同原因一并返回；落盘后入库失败的会清理物理文件，不留孤儿。
    """
    if not files:
        raise HTTPException(status_code=400, detail="未选择任何文件")
    if len(files) > settings.MAX_BATCH_UPLOAD_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"单次最多上传 {settings.MAX_BATCH_UPLOAD_FILES} 个文件，当前 {len(files)} 个",
        )
    if dup_action not in ("skip", "force"):
        raise HTTPException(status_code=400, detail="dup_action 只能是 skip 或 force")
    try:
        res = mat_service.batch_upload_materials(
            db,
            files=files,
            category_id=category_id,
            note=note or None,
            uploaded_by=uploaded_by,
            dup_action=dup_action,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(data=sch.MaterialBatchUploadResult(**res).model_dump())


@router.post("/batch-reassign")
def batch_reassign_category(body: sch.MaterialBatchReassignIn, db: Session = Depends(get_db)):
    """批量改分类：多选材料统一归到同一分类（置空则取消分类）。"""
    try:
        res = mat_service.batch_reassign_category(
            db, ids=body.ids, category_id=body.category_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(data=sch.MaterialBatchReassignOut(**res).model_dump())


@router.post("/batch-delete")
def batch_delete_materials(body: sch.MaterialBatchDeleteIn, db: Session = Depends(get_db)):
    """批量删除索引。默认只取消登记，不删物理文件。"""
    res = mat_service.batch_delete_materials(
        db, ids=body.ids, remove_physical=body.remove_physical
    )
    return success(data=sch.MaterialBatchDeleteOut(**res).model_dump())


# ---------------------------------------------------------- 分类树接口
cat_router = APIRouter(prefix="/material-categories", tags=["业务资料库-分类"])


@cat_router.get("")
def list_categories(db: Session = Depends(get_db)):
    return success(data=mat_service.get_category_tree(db))


@cat_router.post("")
def create_category(body: sch.MaterialCategoryCreate, db: Session = Depends(get_db)):
    try:
        obj = mat_service.create_category(db, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(data=sch.MaterialCategoryOut.model_validate(obj).model_dump())


@cat_router.put("/{cat_id}")
def update_category(cat_id: int, body: sch.MaterialCategoryUpdate, db: Session = Depends(get_db)):
    try:
        obj = mat_service.update_category(db, cat_id, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(data=sch.MaterialCategoryOut.model_validate(obj).model_dump())


@cat_router.delete("/{cat_id}")
def delete_category(cat_id: int, db: Session = Depends(get_db)):
    try:
        mat_service.delete_category(db, cat_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(data={"deleted": cat_id})
