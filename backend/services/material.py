"""业务资料库 - 业务逻辑层。

材料只登记指针、不搬迁物理文件；手工上传才落盘到 uploads/material/。
"""

from __future__ import annotations

import os
import uuid
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import PmwbMaterial, PmwbMaterialCategory
from schemas.common import PaginationResponse
from utils import file_storage as fs

SOURCE_LABELS = {
    "operation_issue": "运营工单",
    "research_issue": "一线调研工单",
    "requirement": "需求交付物",
    "dev_deliverable": "开发交付物",
    "keywork_deliverable": "重点工作交付物",
    "req_manual": "需求操作手册",
    "manual_upload": "手工上传",
}

_PREVIEWABLE_EXT = {
    "xlsx", "xlsm", "csv", "docx", "pptx", "zip", "txt", "log", "sql", "json",
    "xml", "yaml", "yml", "ini", "py", "js", "css", "md", "markdown",
    "pdf", "png", "jpg", "jpeg", "gif", "bmp", "webp", "svg", "htm", "html",
}


# --------------------------------------------------------------- 材料列表
def _to_item(m: PmwbMaterial, category_name: Optional[str]) -> dict:
    return {
        "id": m.id,
        "category_id": m.category_id,
        "category_name": category_name,
        "domain_code": m.domain_code,
        "source_type": m.source_type,
        "source_label": SOURCE_LABELS.get(m.source_type, m.source_type),
        "source_id": m.source_id,
        "source_no": m.source_no or "",
        "source_title": m.source_title or "",
        "file_name": m.file_name,
        "file_size": m.file_size,
        "file_size_human": fs.human_size(m.file_size) if m.file_size else "",
        "file_ext": m.file_ext or "",
        "file_type": m.file_type,
        "origin": m.origin or "manual",
        "note": m.note,
        "tags": m.tags,
        "download_count": m.download_count or 0,
        "can_preview": (m.file_ext or "").lower() in _PREVIEWABLE_EXT,
        "created_at": m.created_at,
    }


def list_materials(
    db: Session,
    *,
    keyword: Optional[str] = None,
    source_type: Optional[str] = None,
    category_id: Optional[int] = None,
    file_ext: Optional[str] = None,
    domain_code: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """多条件过滤 + 模糊搜索 + 分页。"""
    q = db.query(PmwbMaterial)
    cat_name_map: dict[int, str] = {}

    if category_id is not None:
        # 含子分类：把该分类及其子孙下的材料都查出来
        ids = _collect_category_ids(db, category_id)
        q = q.filter(PmwbMaterial.category_id.in_(ids))
        cats = db.query(PmwbMaterialCategory).filter(PmwbMaterialCategory.id.in_(ids)).all()
        cat_name_map = {c.id: c.name for c in cats}

    if source_type:
        q = q.filter(PmwbMaterial.source_type == source_type)
    if file_ext:
        q = q.filter(PmwbMaterial.file_ext == file_ext.lower())
    if domain_code:
        q = q.filter(PmwbMaterial.domain_code == domain_code)

    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            (PmwbMaterial.file_name.like(like))
            | (PmwbMaterial.note.like(like))
            | (PmwbMaterial.tags.like(like))
            | (PmwbMaterial.source_no.like(like))
            | (PmwbMaterial.source_title.like(like))
        )

    total = q.count()
    pages = (total + page_size - 1) // page_size if page_size > 0 else 1
    rows = (
        q.order_by(PmwbMaterial.created_at.desc(), PmwbMaterial.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    if not cat_name_map:
        cat_ids = {r.category_id for r in rows if r.category_id}
        if cat_ids:
            for c in db.query(PmwbMaterialCategory).filter(PmwbMaterialCategory.id.in_(cat_ids)).all():
                cat_name_map[c.id] = c.name

    items = [_to_item(r, cat_name_map.get(r.category_id)) for r in rows]

    # 来源统计（全量，供页面分组展示）
    source_stats = (
        db.query(PmwbMaterial.source_type, func.count())
        .group_by(PmwbMaterial.source_type)
        .all()
    )
    stats = [
        {"source_type": s, "label": SOURCE_LABELS.get(s, s), "count": c}
        for s, c in source_stats
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "source_stats": stats,
    }


def _collect_category_ids(db: Session, root_id: int) -> list[int]:
    """收集某分类及其全部子孙的 id。"""
    all_cats = db.query(PmwbMaterialCategory).all()
    children: dict[int, list[int]] = {}
    for c in all_cats:
        children.setdefault(c.parent_id or 0, []).append(c.id)
    result = [root_id]
    stack = [root_id]
    while stack:
        cur = stack.pop()
        for ch in children.get(cur, []):
            result.append(ch)
            stack.append(ch)
    return result


# --------------------------------------------------------------- 分类树
def get_category_tree(db: Session) -> list[dict]:
    cats = db.query(PmwbMaterialCategory).order_by(
        PmwbMaterialCategory.sort_order, PmwbMaterialCategory.id
    ).all()
    counts = dict(
        db.query(PmwbMaterial.category_id, func.count())
        .filter(PmwbMaterial.category_id.isnot(None))
        .group_by(PmwbMaterial.category_id)
        .all()
    )
    out = []
    for c in cats:
        out.append(
            {
                "id": c.id,
                "code": c.code,
                "name": c.name,
                "parent_id": c.parent_id,
                "sort_order": c.sort_order,
                "enabled": c.enabled,
                "created_at": c.created_at,
                "children_count": 0,
                "material_count": counts.get(c.id, 0),
            }
        )
    # 计算 children_count
    by_parent: dict[int, int] = {}
    for c in cats:
        if c.parent_id:
            by_parent[c.parent_id] = by_parent.get(c.parent_id, 0) + 1
    for item in out:
        item["children_count"] = by_parent.get(item["id"], 0)
    return out


def create_category(db: Session, data: "object") -> PmwbMaterialCategory:
    exists = db.query(PmwbMaterialCategory).filter(PmwbMaterialCategory.code == data.code).first()
    if exists:
        raise ValueError(f"分类编码 {data.code} 已存在")
    if data.parent_id:
        parent = db.query(PmwbMaterialCategory).filter(PmwbMaterialCategory.id == data.parent_id).first()
        if not parent:
            raise ValueError(f"父分类 {data.parent_id} 不存在")
    obj = PmwbMaterialCategory(
        code=data.code,
        name=data.name,
        parent_id=data.parent_id,
        sort_order=data.sort_order or 0,
        enabled=data.enabled if data.enabled is not None else True,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_category(db: Session, cat_id: int, data: "object") -> PmwbMaterialCategory:
    cat = db.query(PmwbMaterialCategory).filter(PmwbMaterialCategory.id == cat_id).first()
    if not cat:
        raise ValueError("分类不存在")
    if data.name is not None:
        cat.name = data.name
    if data.sort_order is not None:
        cat.sort_order = data.sort_order
    if data.enabled is not None:
        cat.enabled = data.enabled
    if data.parent_id is not None:
        new_parent = data.parent_id
        if new_parent == cat.id:
            raise ValueError("不能把分类挂到自身下")
        # 禁止挂到自己的子孙下
        if new_parent in _collect_category_ids(db, cat.id):
            raise ValueError("不能把分类挂到自己的子孙下")
        parent = db.query(PmwbMaterialCategory).filter(PmwbMaterialCategory.id == new_parent).first()
        if not parent:
            raise ValueError("父分类不存在")
        cat.parent_id = new_parent
    db.commit()
    db.refresh(cat)
    return cat


def delete_category(db: Session, cat_id: int) -> None:
    cat = db.query(PmwbMaterialCategory).filter(PmwbMaterialCategory.id == cat_id).first()
    if not cat:
        raise ValueError("分类不存在")
    has_children = (
        db.query(PmwbMaterialCategory).filter(PmwbMaterialCategory.parent_id == cat_id).count() > 0
    )
    if has_children:
        raise ValueError("该分类下还有子分类，请先删除或转移子分类")
    # 材料不自动删除，仅解除分类归属
    db.query(PmwbMaterial).filter(PmwbMaterial.category_id == cat_id).update(
        {PmwbMaterial.category_id: None}
    )
    db.delete(cat)
    db.commit()


# --------------------------------------------------------------- 材料操作
def get_material(db: Session, material_id: int) -> PmwbMaterial:
    m = db.query(PmwbMaterial).filter(PmwbMaterial.id == material_id).first()
    if not m:
        raise ValueError("材料不存在")
    return m


def reassign_category(db: Session, material_id: int, category_id: Optional[int]) -> PmwbMaterial:
    m = get_material(db, material_id)
    if category_id:
        cat = db.query(PmwbMaterialCategory).filter(PmwbMaterialCategory.id == category_id).first()
        if not cat:
            raise ValueError("目标分类不存在")
    m.category_id = category_id
    db.commit()
    db.refresh(m)
    return m


def delete_material(db: Session, material_id: int, remove_physical: bool = False) -> dict:
    """删除索引；remove_physical 仅对手工上传(uploads根)生效。"""
    m = get_material(db, material_id)
    info = {"id": m.id, "file_name": m.file_name, "physical_removed": False}
    if remove_physical and m.origin == "manual" and m.storage_root == "uploads":
        full = fs.abs_path(m.storage_root, m.rel_path)
        try:
            if os.path.isfile(full):
                os.remove(full)
                info["physical_removed"] = True
        except OSError:
            pass
    db.delete(m)
    db.commit()
    return info


def upload_material(
    db: Session,
    *,
    file: "object",
    category_id: Optional[int],
    note: Optional[str],
    uploaded_by: Optional[str],
) -> PmwbMaterial:
    """手工上传：落盘到 uploads/material/ 并登记索引。

    复用 utils.file_storage.save_upload（处理大小限制、分块写盘、文件名清洗、
    扩展名黑名单校验）。file 为 FastAPI UploadFile。
    """
    if category_id:
        cat = db.query(PmwbMaterialCategory).filter(PmwbMaterialCategory.id == category_id).first()
        if not cat:
            raise ValueError("目标分类不存在")

    meta = fs.save_upload(file, sub_dir="material", storage_root="uploads")
    m = PmwbMaterial(
        category_id=category_id,
        source_type="manual_upload",
        source_id=str(uuid.uuid4().hex),
        file_name=meta["file_name"],
        stored_name=meta["stored_name"],
        storage_root=meta["storage_root"],
        rel_path=meta["rel_path"],
        rel_path_hash=meta["rel_path_hash"],
        file_size=meta["file_size"],
        file_ext=meta["file_ext"],
        file_type=meta["file_type"],
        origin="manual",
        uploaded_by=uploaded_by,
        note=note,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def abs_path_of(m: PmwbMaterial) -> str:
    return fs.abs_path(m.storage_root, m.rel_path)
