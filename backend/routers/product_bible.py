import re
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from core.config import settings
from core.exceptions import NotFoundException
from core.response import success

router = APIRouter(prefix="/product-bible", tags=["产品圣经"])


class BibleUpdate(BaseModel):
    markdown: str


def _resolve_source(key: str) -> dict:
    """按业务 key 在配置中查找源文件信息，未找到抛 404。"""
    for item in settings.PRODUCT_BIBLE:
        if item["key"] == key:
            return item
    raise NotFoundException(f"未找到业务「{key}」的产品圣经")


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


@router.get("")
def list_bible():
    """返回产品圣经业务目录（key + 名称）。"""
    catalog = [{"key": i["key"], "name": i["name"]} for i in settings.PRODUCT_BIBLE]
    return success(data=catalog)


@router.get("/{key}")
def get_bible(key: str):
    """读取指定业务的产品圣经 markdown 内容及其元信息。"""
    source = _resolve_source(key)
    markdown = _read_markdown(source["path"])
    data = {
        "key": source["key"],
        "name": source["name"],
        "title": _parse_title(markdown),
        "updated_at": _parse_updated_at(markdown),
        "markdown": markdown,
    }
    return success(data=data)


@router.put("/{key}")
def update_bible(key: str, payload: BibleUpdate):
    """把编辑后的 markdown 写回 Obsidian 源文件（单一事实源）。"""
    source = _resolve_source(key)
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
