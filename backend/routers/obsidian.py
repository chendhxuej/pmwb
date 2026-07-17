"""Obsidian 联动通用路由。

提供按相对路径读取/写回笔记内容的能力（应用内预览/编辑弹窗使用），
并做 vault 越界安全校验，杜绝路径穿越写/读 vault 之外的文件。
"""
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.config import settings
from core.exceptions import NotFoundException, ValidationException
from core.response import success
from db.base import get_db
from utils.obsidian import list_notes, read_markdown, write_markdown_safe

router = APIRouter(prefix="/obsidian", tags=["Obsidian 联动"])


class NoteWrite(BaseModel):
    path: str
    content: str


@router.get("/notes")
def list_obsidian_notes(
    folders: Optional[List[str]] = Query(None, description="限制的 vault 内目录，不传则用配置中的 OPERATION_NOTE_FOLDERS"),
    db: Session = Depends(get_db),
):
    """列出 Obsidian 指定目录下所有 .md 笔记（供工单关联/知识沉淀页浏览）。"""
    target = folders or settings.OPERATION_NOTE_FOLDERS
    notes = list_notes(target)
    return success(data=notes)


@router.get("/content")
def get_obsidian_content(
    path: str = Query(..., description="Obsidian vault 内相对路径，如 01-运营知识/Bug解决方案/xxx.md"),
    db: Session = Depends(get_db),
):
    """读取 Obsidian 笔记内容，供前端应用内预览。"""
    vault = Path(settings.OBSIDIAN_VAULT_PATH).resolve()
    full = (vault / path).resolve()
    # 安全校验：解析后的绝对路径必须仍位于 vault 之内
    if full != vault and vault not in full.parents:
        raise ValidationException("路径越界：必须位于 Obsidian vault 内")

    exists = full.exists()
    content = read_markdown(path) if exists else None
    return success(
        data={
            "exists": exists,
            "content": content,
            "absolute_path": str(full),
            "relative_path": path,
        }
    )


@router.put("/content")
def write_obsidian_content(payload: NoteWrite, db: Session = Depends(get_db)):
    """把编辑后的笔记内容写回 Obsidian 源文件（vault 越界拒绝）。"""
    vault = Path(settings.OBSIDIAN_VAULT_PATH).resolve()
    full = (vault / payload.path).resolve()
    if full != vault and vault not in full.parents:
        raise ValidationException("路径越界：必须位于 Obsidian vault 内")
    if not full.exists() or not full.is_file():
        raise NotFoundException(f"笔记文件不存在：{payload.path}")
    try:
        write_markdown_safe(payload.path, payload.content)
    except ValueError as e:
        raise ValidationException(str(e))
    return success(message="已保存", data={"path": payload.path})
