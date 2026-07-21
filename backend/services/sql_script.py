"""SQL脚本库 Service：列表筛选 + 主表 CRUD。

输出字段样例以 JSON 字符串落库；创建时自动生成 SQL-YYYYMMDD-XXX 编号。
"""
from __future__ import annotations

import json
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import PmwbSqlScript
from services.base import BaseService


class SqlScriptService(BaseService[PmwbSqlScript]):
    """SQL脚本库 Service。"""

    def __init__(self):
        super().__init__(PmwbSqlScript)

    # ------------------------------------------------------------------
    # 列表（含关键字 + 分类筛选）
    # ------------------------------------------------------------------
    def list_with_filters(
        self,
        db: Session,
        keyword: str = None,
        category: str = None,
        page: int = 1,
        page_size: int = 20,
    ):
        query = db.query(self.model)

        if category:
            query = query.filter(self.model.category == category)
        if keyword:
            like_pattern = f"%{keyword}%"
            query = query.filter(
                self.model.title.like(like_pattern)
                | self.model.script_no.like(like_pattern)
                | self.model.description.like(like_pattern)
            )

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

    # ------------------------------------------------------------------
    # 编号生成
    # ------------------------------------------------------------------
    def _gen_script_no(self, db: Session) -> str:
        """生成 SQL-YYYYMMDD-XXX 编号，确保唯一。"""
        day = datetime.now().strftime("%Y%m%d")
        for _ in range(10):
            suffix = f"{random.randint(0, 999):03d}"
            candidate = f"SQL-{day}-{suffix}"
            exists = (
                db.query(self.model.id)
                .filter(self.model.script_no == candidate)
                .first()
            )
            if not exists:
                return candidate
        return f"SQL-{day}-{datetime.now().strftime('%H%M%S')}"

    @staticmethod
    def _normalize_fields(fields: Any) -> str:
        """输出字段样例：列表 -> JSON 字符串。"""
        if isinstance(fields, list):
            # 仅保留有字段名的项
            cleaned = [
                {"name": f.get("name"), "type": f.get("type"), "desc": f.get("desc")}
                for f in fields
                if isinstance(f, dict) and f.get("name")
            ]
            return json.dumps(cleaned, ensure_ascii=False)
        if fields is None:
            return json.dumps([], ensure_ascii=False)
        if isinstance(fields, str):
            return fields
        return json.dumps([], ensure_ascii=False)

    # ------------------------------------------------------------------
    # 创建（带编号 + 字段标准化）
    # ------------------------------------------------------------------
    def create(self, db: Session, obj_in: Dict[str, Any]) -> PmwbSqlScript:
        obj_in = dict(obj_in)
        if "output_fields" in obj_in:
            obj_in["output_fields"] = self._normalize_fields(obj_in.get("output_fields"))
        obj_in["script_no"] = self._gen_script_no(db)
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    # ------------------------------------------------------------------
    # 更新（字段标准化）
    # ------------------------------------------------------------------
    def update(self, db: Session, id: int, obj_in: Dict[str, Any]) -> PmwbSqlScript | None:
        db_obj = self.get(db, id)
        if not db_obj:
            return None
        obj_in = dict(obj_in)
        if "output_fields" in obj_in:
            obj_in["output_fields"] = self._normalize_fields(obj_in.get("output_fields"))
        for key, value in obj_in.items():
            if hasattr(db_obj, key):
                setattr(db_obj, key, value)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    # ------------------------------------------------------------------
    # 统计（按分类计数 + 总数）
    # ------------------------------------------------------------------
    def stats(self, db: Session) -> Dict[str, Any]:
        by_category = {
            row[0] or "未分类": row[1]
            for row in db.query(self.model.category, func.count())
            .group_by(self.model.category)
            .all()
        }
        total = db.query(func.count()).select_from(self.model).scalar() or 0
        return {"total": int(total), "by_category": by_category}


sql_script_service = SqlScriptService()
