"""重点工作 KeyWork Service：主表 CRUD + 子表全量替换 + 看板统计。

三类（总部试点/年度任务/专题工作）共用一张主表，由 category 字段区分。
"""
from __future__ import annotations

import json
import random
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from core.exceptions import NotFoundException
from db.models import (
    PmwbKeyWork,
    PmwbKeyWorkDeliverable,
    PmwbKeyWorkGoal,
    PmwbKeyWorkMember,
    PmwbKeyWorkMemberTask,
    PmwbKeyWorkMilestone,
    PmwbKeyWorkMonthlyPlan,
    PmwbKeyWorkProgress,
    PmwbKeyWorkWeeklyPlan,
)
from services.base import BaseService

_CHILDREN = {
    "goals": PmwbKeyWorkGoal,
    "milestones": PmwbKeyWorkMilestone,
    "members": PmwbKeyWorkMember,
    "monthly_plans": PmwbKeyWorkMonthlyPlan,
    "weekly_plans": PmwbKeyWorkWeeklyPlan,
    "progresses": PmwbKeyWorkProgress,
    "member_tasks": PmwbKeyWorkMemberTask,
}


class KeyWorkService(BaseService[PmwbKeyWork]):
    """重点工作 Service。"""

    def __init__(self):
        super().__init__(PmwbKeyWork)

    # ------------------------------------------------------------------
    # 详情（一次性加载全部 children）
    # ------------------------------------------------------------------
    def get(self, db: Session, id: int) -> PmwbKeyWork | None:
        return (
            db.query(self.model)
            .options(
                joinedload(self.model.goals),
                joinedload(self.model.milestones),
                joinedload(self.model.members),
                joinedload(self.model.monthly_plans),
                joinedload(self.model.weekly_plans),
                joinedload(self.model.progresses),
                joinedload(self.model.member_tasks),
                joinedload(self.model.deliverables),
            )
            .filter(self.model.id == id)
            .first()
        )

    # ------------------------------------------------------------------
    # 列表（仅主表字段，不含 children，减重）
    # ------------------------------------------------------------------
    def list_with_filters(
        self,
        db: Session,
        keyword: str = None,
        category: str = None,
        status: str = None,
        owner: str = None,
        page: int = 1,
        page_size: int = 20,
    ):
        query = db.query(self.model)

        if category:
            query = query.filter(self.model.category == category)
        if status:
            query = query.filter(self.model.status == status)
        if owner:
            query = query.filter(self.model.owner == owner)
        if keyword:
            like_pattern = f"%{keyword}%"
            query = query.filter(
                self.model.title.like(like_pattern)
                | self.model.work_no.like(like_pattern)
                | self.model.owner.like(like_pattern)
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
    # 新建（含子表）
    # ------------------------------------------------------------------
    def _gen_work_no(self, db: Session) -> str:
        """生成 KW-YYYYMMDD-XXX 编号，确保唯一。"""
        day = datetime.now().strftime("%Y%m%d")
        for _ in range(10):
            suffix = f"{random.randint(0, 999):03d}"
            candidate = f"KW-{day}-{suffix}"
            exists = (
                db.query(self.model.id)
                .filter(self.model.work_no == candidate)
                .first()
            )
            if not exists:
                return candidate
        # 极端碰撞：用毫秒兜底
        return f"KW-{day}-{datetime.now().strftime('%H%M%S')}"

    @staticmethod
    def _normalize_acceptance(acc: Any) -> str:
        if isinstance(acc, list):
            return json.dumps(acc, ensure_ascii=False)
        if acc is None:
            return json.dumps([], ensure_ascii=False)
        return acc

    def create_with_relations(self, db: Session, obj_in: dict) -> PmwbKeyWork:
        children = {key: obj_in.pop(key, []) for key in _CHILDREN.keys()}

        if "acceptance_criteria" in obj_in:
            obj_in["acceptance_criteria"] = self._normalize_acceptance(
                obj_in.get("acceptance_criteria")
            )

        obj_in["work_no"] = self._gen_work_no(db)
        kw = self.model(**obj_in)
        db.add(kw)
        db.flush()

        for key, model in _CHILDREN.items():
            for child in children.get(key) or []:
                child = dict(child)
                child.pop("id", None)
                db.add(model(key_work_id=kw.id, **child))

        db.commit()
        db.refresh(kw)
        return kw

    # ------------------------------------------------------------------
    # 子表全量替换
    # ------------------------------------------------------------------
    def _replace_children(
        self, db: Session, kw_id: int, children: List[dict], model, fk: str = "key_work_id"
    ):
        db.query(model).filter(getattr(model, fk) == kw_id).delete()
        for child in children or []:
            child = dict(child)
            child.pop("id", None)
            db.add(model(**{fk: kw_id, **child}))

    # ------------------------------------------------------------------
    # 更新（标量 setattr + 提供的子表全量替换）
    # ------------------------------------------------------------------
    def update(self, db: Session, id: int, obj_in: dict) -> PmwbKeyWork | None:
        db_obj = self.get(db, id)
        if not db_obj:
            return None

        # 验收标准：列表转 JSON 字符串
        if "acceptance_criteria" in obj_in:
            obj_in["acceptance_criteria"] = self._normalize_acceptance(
                obj_in.get("acceptance_criteria")
            )

        for key, value in obj_in.items():
            if key in _CHILDREN:
                continue
            if hasattr(db_obj, key):
                setattr(db_obj, key, value)

        for key, model in _CHILDREN.items():
            if obj_in.get(key) is not None:
                self._replace_children(db, id, obj_in[key], model)

        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, id: int) -> bool:
        db_obj = self.get(db, id)
        if not db_obj:
            return False
        db.delete(db_obj)
        db.commit()
        return True

    # ------------------------------------------------------------------
    # 统计（供首页看板消费，本期不接入首页）
    # ------------------------------------------------------------------
    def stats(self, db: Session) -> Dict[str, Any]:
        today = date.today()
        in_30 = date.fromordinal(today.toordinal() + 30)

        by_category = {
            row[0]: row[1]
            for row in db.query(self.model.category, func.count())
            .group_by(self.model.category)
            .all()
        }
        by_status = {
            row[0]: row[1]
            for row in db.query(self.model.status, func.count())
            .group_by(self.model.status)
            .all()
        }

        overdue_member_tasks = (
            db.query(func.count())
            .select_from(PmwbKeyWorkMemberTask)
            .filter(
                PmwbKeyWorkMemberTask.due_date < today,
                PmwbKeyWorkMemberTask.status != "done",
            )
            .scalar()
            or 0
        )
        upcoming_milestones = (
            db.query(func.count())
            .select_from(PmwbKeyWorkMilestone)
            .filter(
                PmwbKeyWorkMilestone.due_date >= today,
                PmwbKeyWorkMilestone.due_date <= in_30,
                PmwbKeyWorkMilestone.status == "pending",
            )
            .scalar()
            or 0
        )
        total_member_tasks = (
            db.query(func.count()).select_from(PmwbKeyWorkMemberTask).scalar() or 0
        )
        done_member_tasks = (
            db.query(func.count())
            .select_from(PmwbKeyWorkMemberTask)
            .filter(PmwbKeyWorkMemberTask.status == "done")
            .scalar()
            or 0
        )

        return {
            "by_category": by_category,
            "by_status": by_status,
            "overdue_member_tasks": int(overdue_member_tasks),
            "upcoming_milestones": int(upcoming_milestones),
            "total_member_tasks": int(total_member_tasks),
            "done_member_tasks": int(done_member_tasks),
        }


keywork_service = KeyWorkService()
