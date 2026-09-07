"""统一文件存储工具。

背景：历史上运营工单 / 调研工单 / 需求交付三处上传逻辑各自复制粘贴，
存在「无大小限制、全量读入内存、同名静默覆盖、无 MIME 校验」四类问题。
业务资料库不再复制第四份，统一收口到本模块。

约定：
- 索引表只存 ``storage_root`` + ``rel_path`` 指针，不搬迁已有物理文件。
- ``storage_root='uploads'`` → 项目根/uploads（可通过 settings.UPLOAD_ROOT 覆盖）
- ``storage_root='vault'``   → settings.OBSIDIAN_VAULT_PATH
- 落盘名加 UUID 短前缀，彻底解决同名覆盖。
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import uuid
from typing import Any, BinaryIO, Optional

from fastapi import HTTPException, UploadFile

from core.config import settings

# 分块写盘大小：避免大文件一次性载入内存
_CHUNK = 8 * 1024 * 1024

# 危险扩展名黑名单（业务资料不会出现，上传即拒）
_BLOCKED_EXT = {
    "exe", "bat", "cmd", "com", "scr", "dll", "sys",
    "ps1", "vbs", "vbe", "js", "jse", "wsf", "msi", "jar", "sh", "app",
}

_ILLEGAL_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]+')

# 扩展名 -> 展示分组（左侧「材料类型」筛选用）
EXT_GROUP: dict[str, str] = {}
for _g, _exts in {
    "表格": ("xlsx", "xls", "csv", "et"),
    "文档": ("docx", "doc", "pdf", "txt", "md", "wps", "rtf", "odt"),
    "演示": ("pptx", "ppt", "dps"),
    "图片": ("png", "jpg", "jpeg", "gif", "bmp", "webp", "svg", "tif", "tiff"),
    "压缩包": ("zip", "rar", "7z", "tar", "gz"),
    "网页": ("htm", "html", "mht"),
}.items():
    for _e in _exts:
        EXT_GROUP[_e] = _g


def uploads_root() -> str:
    """项目内上传根目录。默认推导为项目根/uploads，与现有 uploads/operation 同级。"""
    if settings.UPLOAD_ROOT:
        return settings.UPLOAD_ROOT
    # utils/ -> backend/ -> 项目根
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "uploads",
    )


def vault_root() -> str:
    return settings.OBSIDIAN_VAULT_PATH


def resolve_root(storage_root: str) -> str:
    root = vault_root() if storage_root == "vault" else uploads_root()
    os.makedirs(root, exist_ok=True)
    return root


def human_size(num: Optional[int]) -> str:
    if not num:
        return "0 B"
    n = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def file_ext(name: str) -> str:
    return os.path.splitext(name or "")[1].lstrip(".").lower()


def ext_group(ext: str) -> str:
    return EXT_GROUP.get((ext or "").lower(), "其他")


def sanitize_filename(name: str, max_len: int = 180) -> str:
    """清洗文件名：去非法字符、去路径分隔符、限长。

    保留中文与常见符号（如（）、-、_、@），仅剔除 Windows/Unix 非法字符。
    """
    raw = (name or "").strip().replace("\\", "_").replace("/", "_")
    cleaned = _ILLEGAL_CHARS.sub("_", raw).strip(" .")
    if not cleaned:
        cleaned = "未命名文件"
    if len(cleaned) > max_len:
        stem, dot, ext = cleaned.rpartition(".")
        if dot and len(ext) <= 10:
            cleaned = stem[: max_len - len(ext) - 1] + "." + ext
        else:
            cleaned = cleaned[:max_len]
    return cleaned


def path_hash(rel_path: str) -> str:
    """rel_path 的 sha256，用于唯一约束（MySQL utf8mb4 索引长度限制）。"""
    return hashlib.sha256((rel_path or "").encode("utf-8")).hexdigest()


def abs_path(storage_root: str, rel_path: str) -> str:
    """还原绝对路径，并做路径穿越防护。"""
    root = os.path.abspath(resolve_root(storage_root))
    full = os.path.abspath(os.path.join(root, rel_path or ""))
    if full != root and not full.startswith(root + os.sep):
        raise HTTPException(status_code=400, detail="非法的文件路径")
    return full


def guess_mime(name: str) -> str:
    mime = mimetypes.guess_type(name or "")[0]
    return mime or "application/octet-stream"


def validate_ext(name: str) -> None:
    ext = file_ext(name)
    if ext in _BLOCKED_EXT:
        raise HTTPException(status_code=400, detail=f"不支持上传 .{ext} 类型的文件")


def _stream_to_disk(src: BinaryIO, dest: str, limit_bytes: int) -> int:
    """分块写盘，累计超过 limit_bytes 立即中断并清理半截文件。"""
    total = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = src.read(_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > limit_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"文件超过 {human_size(limit_bytes)} 上限，请压缩后再传",
                    )
                out.write(chunk)
    except HTTPException:
        if os.path.exists(dest):
            try:
                os.remove(dest)
            except OSError:
                pass
        raise
    return total


def save_upload(
    file: UploadFile,
    *,
    sub_dir: str,
    biz_id: Optional[Any] = None,
    storage_root: str = "uploads",
    filename: Optional[str] = None,
) -> dict:
    """保存上传文件并返回索引元信息。

    :param sub_dir: 一级子目录，如 ``material`` / ``operation``
    :param biz_id:  业务对象 id（工单号 / 分类码），作为二级目录；None 则不分层
    :return: dict(file_name, stored_name, rel_path, rel_path_hash, file_size,
                  file_ext, file_type, storage_root)
    """
    original = filename or file.filename or "未命名文件"
    validate_ext(original)

    safe_name = sanitize_filename(original)
    ext = file_ext(safe_name)
    stem = safe_name[: -len(ext) - 1] if ext else safe_name
    stored_name = f"{uuid.uuid4().hex[:8]}_{stem}" + (f".{ext}" if ext else "")

    parts = [sub_dir] + ([str(biz_id)] if biz_id is not None else [])
    rel_dir = "/".join(p.strip("\\/") for p in parts if str(p).strip())
    abs_dir = os.path.join(resolve_root(storage_root), *([p for p in rel_dir.split("/") if p]))
    os.makedirs(abs_dir, exist_ok=True)

    rel_path = f"{rel_dir}/{stored_name}" if rel_dir else stored_name
    dest = os.path.join(abs_dir, stored_name)

    limit = int(settings.MAX_UPLOAD_SIZE_MB) * 1024 * 1024
    size = _stream_to_disk(file.file, dest, limit)

    return {
        "file_name": safe_name,
        "stored_name": stored_name,
        "rel_path": rel_path,
        "rel_path_hash": path_hash(rel_path),
        "file_size": size,
        "file_ext": ext,
        "file_type": guess_mime(safe_name),
        "storage_root": storage_root,
    }


def stat_file(storage_root: str, rel_path: str) -> Optional[dict]:
    """读取已存在文件的元信息；文件不存在返回 None（用于清理孤儿索引）。"""
    try:
        full = abs_path(storage_root, rel_path)
    except HTTPException:
        return None
    if not os.path.isfile(full):
        return None
    name = os.path.basename(full)
    return {
        "file_name": name,
        "file_size": os.path.getsize(full),
        "file_ext": file_ext(name),
        "file_type": guess_mime(name),
    }
