"""重点工作交付物 service：文件落 Obsidian vault（DB 存元数据）。

路径模式：{OBSIDIAN_VAULT_PATH}/09-重点工作/{category}/{kw_id}_{safe(title)}/
与需求交付 / 会议纪要 同源，便于 Obsidian 直接索引。
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from db.models import PmwbKeyWork, PmwbKeyWorkDeliverable
from core.config import settings
from core.exceptions import NotFoundException


def _safe_name(name: str) -> str:
    if not name:
        return "untitled"
    s = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", name).strip()
    s = re.sub(r"\s+", "_", s)
    return s[:40]


def _resolve_paths(kw_id: int, category: str, title: str) -> Dict[str, str]:
    vault = settings.OBSIDIAN_VAULT_PATH
    folder_base = os.path.join(vault, settings.KEY_WORK_VAULT_DIR)
    sub = f"{kw_id}_{_safe_name(title or str(kw_id))}"
    folder = os.path.join(folder_base, category or "other", sub)
    return {"folder_base": folder_base, "folder": folder}


def upload_deliverable(
    db,
    kw_id: int,
    filename: str,
    content: bytes,
    uploaded_by: str = None,
    deliverable_type: str = "other",
    note: str = None,
) -> Dict[str, Any]:
    kw = db.query(PmwbKeyWork).filter(PmwbKeyWork.id == kw_id).first()
    if not kw:
        raise NotFoundException(f"重点工作不存在：id={kw_id}")
    paths = _resolve_paths(kw.id, kw.category, kw.title)
    os.makedirs(paths["folder"], exist_ok=True)

    safe_fn = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", filename)
    fp = os.path.join(paths["folder"], safe_fn)
    with open(fp, "wb") as f:
        f.write(content)

    row = PmwbKeyWorkDeliverable(
        key_work_id=kw.id,
        deliverable_type=deliverable_type,
        file_name=safe_fn,
        original_name=filename,
        file_size=len(content),
        file_type=_guess_type(filename),
        obsidian_path=fp,
        source="upload",
        note=note,
        uploaded_by=uploaded_by,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "file_name": row.file_name,
        "original_name": row.original_name,
        "file_size": row.file_size,
        "file_type": row.file_type,
        "obsidian_path": row.obsidian_path,
        "deliverable_type": row.deliverable_type,
        "note": row.note,
        "uploaded_by": row.uploaded_by,
        "created_at": row.created_at,
    }


def list_deliverables(db, kw_id: int) -> List[Dict[str, Any]]:
    rows = (
        db.query(PmwbKeyWorkDeliverable)
        .filter(PmwbKeyWorkDeliverable.key_work_id == kw_id)
        .order_by(PmwbKeyWorkDeliverable.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "file_name": r.file_name,
            "original_name": r.original_name,
            "file_size": r.file_size,
            "file_type": r.file_type,
            "deliverable_type": r.deliverable_type,
            "note": r.note,
            "uploaded_by": r.uploaded_by,
            "created_at": r.created_at,
        }
        for r in rows
    ]


def get_deliverable_path(db, kw_id: int, did: int) -> str:
    row = (
        db.query(PmwbKeyWorkDeliverable)
        .filter(
            PmwbKeyWorkDeliverable.id == did,
            PmwbKeyWorkDeliverable.key_work_id == kw_id,
        )
        .first()
    )
    if not row:
        raise NotFoundException(f"交付物不存在：id={did}")
    return row.obsidian_path


def delete_deliverable(db, kw_id: int, did: int) -> bool:
    row = (
        db.query(PmwbKeyWorkDeliverable)
        .filter(
            PmwbKeyWorkDeliverable.id == did,
            PmwbKeyWorkDeliverable.key_work_id == kw_id,
        )
        .first()
    )
    if not row:
        return False
    fp = row.obsidian_path
    db.delete(row)
    db.commit()
    # 删除物理文件（防路径穿越）
    if fp and os.path.isfile(fp):
        folder = os.path.dirname(fp)
        if os.path.abspath(fp).startswith(os.path.abspath(folder)):
            try:
                os.remove(fp)
            except OSError:
                # 某些受保护环境禁止程序化删除，忽略（DB 记录已删）
                pass
    return True


def _guess_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    mapping = {
        "doc": "word", "docx": "word", "pdf": "pdf", "xls": "excel",
        "xlsx": "excel", "ppt": "ppt", "pptx": "ppt", "png": "image",
        "jpg": "image", "jpeg": "image", "gif": "image", "zip": "archive",
        "rar": "archive", "txt": "text", "md": "text",
    }
    return mapping.get(ext, "other")
