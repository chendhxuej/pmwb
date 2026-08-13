import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.exceptions import NotFoundException
from core.response import success
from db.base import get_db
from db.models import PmwbBusinessDomain, PmwbKnowledgeItem
from services.knowledge_link_service import ensure_domain_main_note
from utils.obsidian import (
    extract_section,
    read_auto_block,
    read_frontmatter,
    read_markdown,
    upsert_auto_block,
    write_markdown,
)

router = APIRouter(prefix="/product-bible", tags=["产品圣经"])

PRODUCT_SECTION_HEADING = "产商品与资费体系"
PRODUCT_BLOCK_KEY = "product"


class BibleUpdate(BaseModel):
    markdown: str


def _get_domain(db: Session, domain_code: str) -> PmwbBusinessDomain:
    domain = (
        db.query(PmwbBusinessDomain)
        .filter(PmwbBusinessDomain.domain_code == domain_code)
        .first()
    )
    if not domain:
        raise NotFoundException(f"未找到业务领域：{domain_code}")
    return domain


def _get_main_note(db: Session, domain_code: str):
    """返回领域主笔记记录；不存在则 ensure 新建。"""
    item = (
        db.query(PmwbKnowledgeItem)
        .filter(
            PmwbKnowledgeItem.domain_code == domain_code,
            PmwbKnowledgeItem.note_type == "main",
        )
        .first()
    )
    if not item:
        item = ensure_domain_main_note(db, domain_code)
    return item


def _parse_title(markdown: str) -> str:
    for line in markdown.splitlines():
        m = re.match(r"^#\s+(.+)$", line.strip())
        if m:
            return m.group(1).strip()
    return ""


def _parse_updated_at(markdown: str) -> str:
    m = re.search(r"更新日期\**\s*[:：]\s*([\d]{4}-[\d]{2}-[\d]{2})", markdown)
    if m:
        return m.group(1)
    return ""


@router.get("")
def list_bible(db: Session = Depends(get_db)):
    """返回产品圣经业务目录：按业务领域(domain_code)聚合，不再依赖硬编码配置。"""
    domains = (
        db.query(PmwbBusinessDomain)
        .filter(PmwbBusinessDomain.enabled == 1)
        .order_by(PmwbBusinessDomain.sort_order, PmwbBusinessDomain.domain_code)
        .all()
    )
    catalog = [
        {"key": d.domain_code, "name": d.domain_name, "format": "markdown"}
        for d in domains
    ]
    return success(data=catalog)


@router.get("/{domain_code}")
def get_bible(domain_code: str, db: Session = Depends(get_db)):
    """读取业务领域主笔记的 §2 产商品与资费体系章节作为产品圣经内容。"""
    _get_domain(db, domain_code)
    item = _get_main_note(db, domain_code)
    if not item or not item.obsidian_path:
        raise NotFoundException(f"业务「{domain_code}」尚无主笔记，请先同步")

    content = read_markdown(item.obsidian_path)
    # 优先取 §2 产商品章节；章节内优先取系统自动汇总 AUTO 块，空则退回整章
    section = extract_section(content, PRODUCT_SECTION_HEADING)
    block = read_auto_block(content, PRODUCT_BLOCK_KEY)
    if not section and not block:
        # 旧模板主笔记可能缺 §2 章节：惰性回填一次（upsert_auto_block 安全幂等，仅补 AUTO 块）
        try:
            from services.knowledge_link_service import sync_main_note_from_links

            sync_main_note_from_links(db, domain_code)
            content = read_markdown(item.obsidian_path)
            section = extract_section(content, PRODUCT_SECTION_HEADING)
            block = read_auto_block(content, PRODUCT_BLOCK_KEY)
        except Exception:
            pass
    if block:
        markdown = f"## {PRODUCT_SECTION_HEADING}\n\n{block}"
    elif section:
        markdown = section
    else:
        markdown = content

    fm = {}
    try:
        fm = read_frontmatter(item.obsidian_path) or {}
    except Exception:
        pass

    updated_at = fm.get("auto_sections_generated_at") or _parse_updated_at(markdown)
    return success(
        data={
            "key": domain_code,
            "name": item.title or domain_code,
            "title": _parse_title(markdown) or item.title,
            "updated_at": updated_at,
            "format": "markdown",
            "markdown": markdown,
        }
    )


@router.put("/{domain_code}")
def update_bible(domain_code: str, payload: BibleUpdate, db: Session = Depends(get_db)):
    """把编辑后的产商品内容写回主笔记 §2 产商品 AUTO 区块（系统同步会重新生成）。"""
    _get_domain(db, domain_code)
    item = _get_main_note(db, domain_code)
    if not item or not item.obsidian_path:
        raise NotFoundException(f"业务「{domain_code}」尚无主笔记，请先同步")

    content = read_markdown(item.obsidian_path)
    new_content = upsert_auto_block(
        content,
        PRODUCT_BLOCK_KEY,
        payload.markdown,
        anchor_heading=PRODUCT_SECTION_HEADING,
    )
    write_markdown(item.obsidian_path, new_content)
    return success(message="已保存", data={"key": domain_code})
