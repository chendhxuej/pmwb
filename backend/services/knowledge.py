from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import PmwbKnowledgeItem
from schemas.knowledge import KnowledgeItemCreate
from services.base import BaseService
from services.knowledge_link_service import ensure_domain_main_note, rebuild_main_note_subnotes
from utils.obsidian import read_markdown, write_markdown


class KnowledgeItemService(BaseService[PmwbKnowledgeItem]):
    """知识库 Service。"""

    def __init__(self):
        super().__init__(PmwbKnowledgeItem)

    def list_with_filters(
        self,
        db: Session,
        keyword: str = None,
        category: str = None,
        sub_category: str = None,
        tag: str = None,
        source_type: str = None,
        domain_code: str = None,
        page: int = 1,
        page_size: int = 20,
    ):
        query = db.query(self.model)

        if category:
            query = query.filter(self.model.category == category)
        if sub_category:
            query = query.filter(self.model.sub_category == sub_category)
        if source_type:
            query = query.filter(self.model.source_type == source_type)
        if domain_code:
            query = query.filter(self.model.domain_code == domain_code)
        if keyword:
            like_pattern = f"%{keyword}%"
            query = query.filter(
                self.model.title.like(like_pattern)
                | self.model.summary.like(like_pattern)
                | self.model.item_id.like(like_pattern)
            )
        if tag:
            like_tag = f"%{tag}%"
            query = query.filter(self.model.tags.like(like_tag))

        total = query.count()
        offset = (page - 1) * page_size
        items = (
            query.order_by(self.model.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        pages = (total + page_size - 1) // page_size if page_size > 0 else 1
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
            "items": items,
        }

    def create_with_content(self, db: Session, obj_in: KnowledgeItemCreate) -> PmwbKnowledgeItem:
        data = obj_in.model_dump()
        content = data.pop("content", "")

        # 写入 Obsidian
        if content:
            write_markdown(data["obsidian_path"], content)

        item = self.create(db, data)
        # 系统自动保活：新建笔记归属某领域时，确保其主笔记存在并重建子笔记摘要
        if item.domain_code:
            try:
                ensure_domain_main_note(db, item.domain_code)
                rebuild_main_note_subnotes(db, item.domain_code)
            except Exception:
                # 保活失败不应阻断主流程（如领域不存在等）
                pass
        return item

    def update(self, db: Session, id: int, obj_in: Dict[str, Any]) -> PmwbKnowledgeItem | None:
        item = super().update(db, id, obj_in)
        if item and obj_in.get("domain_code"):
            # 领域变更/归属时自动保活主笔记并重建子笔记摘要
            try:
                ensure_domain_main_note(db, obj_in["domain_code"])
                rebuild_main_note_subnotes(db, obj_in["domain_code"])
            except Exception:
                pass
        return item

    def get_content(self, db: Session, id: int) -> Dict[str, Any]:
        item = self.get(db, id)
        if not item:
            return None
        content = read_markdown(item.obsidian_path) or ""
        return {
            "item_id": item.item_id,
            "title": item.title,
            "obsidian_path": item.obsidian_path,
            "content": content,
        }

    def update_content(self, db: Session, id: int, content: str) -> bool:
        item = self.get(db, id)
        if not item:
            return False
        write_markdown(item.obsidian_path, content)
        item.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(item)
        return True

    def get_categories(self, db: Session) -> List[str]:
        rows = db.query(self.model.category).distinct().all()
        return [row[0] for row in rows if row[0]]

    def get_sub_categories(self, db: Session, category: str = None) -> List[str]:
        query = db.query(self.model.sub_category).distinct()
        if category:
            query = query.filter(self.model.category == category)
        rows = query.all()
        return [row[0] for row in rows if row[0]]

    def get_tags(self, db: Session) -> List[str]:
        rows = db.query(self.model.tags).all()
        tags = set()
        for row in rows:
            if row[0]:
                for tag in row[0].split(","):
                    tag = tag.strip()
                    if tag:
                        tags.add(tag)
        return sorted(list(tags))


knowledge_item_service = KnowledgeItemService()
