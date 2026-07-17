import re
import zipfile
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel

from core.config import settings
from core.exceptions import NotFoundException
from core.response import success
from core.docx_convert import docx_to_html, emf_to_bmp

router = APIRouter(prefix="/product-bible", tags=["产品圣经"])

# EMF 转换结果缓存（key: docx路径:文件名:mtime -> bmp bytes），避免每次请求重算 GDI
_EMF_CACHE: dict = {}


class BibleUpdate(BaseModel):
    markdown: str


def _resolve_source(key: str) -> dict:
    """按业务 key 在配置中查找源文件信息，未找到抛 404。"""
    for item in settings.PRODUCT_BIBLE:
        if item["key"] == key:
            return item
    raise NotFoundException(f"未找到业务「{key}」的产品圣经")


def _source_format(source: dict) -> str:
    """判断源文件格式：配置显式 format 优先，否则按扩展名。"""
    fmt = source.get("format")
    if fmt:
        return fmt.lower()
    return "docx" if Path(source["path"]).suffix.lower() == ".docx" else "md"


def _read_markdown(rel_path: str) -> str:
    """基于 Obsidian vault 根目录解析并读取 markdown 文件。"""
    full = Path(settings.OBSIDIAN_VAULT_PATH) / rel_path
    if not full.exists() or not full.is_file():
        raise NotFoundException(f"知识文件不存在：{rel_path}")
    return full.read_text(encoding="utf-8")


def _parse_title(markdown: str) -> str:
    """取第一个一级标题作为标题。"""
    for line in markdown.splitlines():
        m = re.match(r"^#\s+(.+)$", line.strip())
        if m:
            return m.group(1).strip()
    return ""


def _parse_updated_at(markdown: str) -> str:
    """从文档头部的「更新日期」行解析日期，失败回退文件修改时间。"""
    m = re.search(r"更新日期\**\s*[:：]\s*([\d]{4}-[\d]{2}-[\d]{2})", markdown)
    if m:
        return m.group(1)
    return ""


def _read_bible(source: dict):
    """读取源文件，返回 (content, title, updated_at, fmt)。docx 转 HTML 后复用渲染链路。"""
    fmt = _source_format(source)
    full = Path(settings.OBSIDIAN_VAULT_PATH) / source["path"]
    if not full.exists() or not full.is_file():
        raise NotFoundException(f"知识文件不存在：{source['path']}")
    if fmt == "docx":
        res = docx_to_html(str(full))
        content = res["html"].replace("__KEY__", source["key"])
        return content, res["title"], res["updated_at"], fmt
    markdown = full.read_text(encoding="utf-8")
    return markdown, _parse_title(markdown), _parse_updated_at(markdown), fmt


_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}


@router.get("")
def list_bible():
    """返回产品圣经业务目录（key + 名称 + 格式）。"""
    catalog = [
        {"key": i["key"], "name": i["name"], "format": _source_format(i)}
        for i in settings.PRODUCT_BIBLE
    ]
    return success(data=catalog)


@router.get("/{key}")
def get_bible(key: str):
    """读取指定业务的产品圣经内容及其元信息（md 原文或 docx 转出的 HTML）。"""
    source = _resolve_source(key)
    content, title, updated_at, fmt = _read_bible(source)
    data = {
        "key": source["key"],
        "name": source["name"],
        "title": title,
        "updated_at": updated_at,
        "format": fmt,
        "markdown": content,
    }
    return success(data=data)


@router.get("/{key}/media/{filename}")
def get_media(key: str, filename: str):
    """抽取 docx 内的媒体文件返回；EMF 矢量图经 GDI 光栅化为 BMP。"""
    source = _resolve_source(key)
    if _source_format(source) != "docx":
        raise NotFoundException("该业务非 docx 源，无媒体资源")
    # 防目录穿越
    if "/" in filename or "\\" in filename or ".." in filename:
        raise NotFoundException("非法文件名")
    full = Path(settings.OBSIDIAN_VAULT_PATH) / source["path"]
    if not full.exists() or not full.is_file():
        raise NotFoundException(f"知识文件不存在：{source['path']}")
    media_path = f"word/media/{filename}"
    try:
        z = zipfile.ZipFile(full)
    except zipfile.BadZipFile:
        raise NotFoundException("文档无法读取")
    if media_path not in z.namelist():
        raise NotFoundException(f"媒体不存在：{filename}")
    ext = Path(filename).suffix.lower()
    if ext == ".emf":
        raw = z.read(media_path)
        mtime = full.stat().st_mtime
        cache_key = f"{full}:{filename}:{mtime}"
        bmp = _EMF_CACHE.get(cache_key)
        if bmp is None:
            bmp = emf_to_bmp(raw)
            if bmp is None:
                # 转换失败：返回占位说明（1x1 透明？这里用简单文本提示）
                return Response(
                    content=b"EMF render failed",
                    media_type="text/plain",
                    status_code=200,
                )
            _EMF_CACHE[cache_key] = bmp
        return Response(content=bmp, media_type="image/bmp")
    raw = z.read(media_path)
    return Response(content=raw, media_type=_MEDIA_TYPES.get(ext, "application/octet-stream"))


@router.put("/{key}")
def update_bible(key: str, payload: BibleUpdate):
    """把编辑后的内容写回 Obsidian 源文件。docx 为只读源，拒绝写入。"""
    source = _resolve_source(key)
    if _source_format(source) == "docx":
        raise NotFoundException("docx 为只读源，请在 Obsidian / Word 中修改原文件")
    full = Path(settings.OBSIDIAN_VAULT_PATH) / source["path"]
    if not full.exists() or not full.is_file():
        raise NotFoundException(f"知识文件不存在：{source['path']}")
    # 安全校验：解析后的绝对路径必须仍位于 vault 之内，杜绝路径越界写文件
    full_resolved = full.resolve()
    vault_resolved = Path(settings.OBSIDIAN_VAULT_PATH).resolve()
    if full_resolved != vault_resolved and vault_resolved not in full_resolved.parents:
        raise NotFoundException("非法路径，拒绝写入")
    full.write_text(payload.markdown, encoding="utf-8")
    return success(message="已保存", data={"key": key})
