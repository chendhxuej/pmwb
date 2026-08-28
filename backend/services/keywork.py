"""重点工作 KeyWork Service：主表 CRUD + 子表全量替换 + 看板统计。

三类（总部试点/年度任务/专题工作）共用一张主表，由 category 字段区分。
"""
from __future__ import annotations

import json
import random
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

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
    PmwbKeyWorkWeeklyFeedback,
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
        """加载重点工作详情。

        8 张子表用 selectinload（而非 joinedload）：多 collection 用 joinedload
        会产生 LEFT JOIN 笛卡尔积（各子表行数相乘），数据量小也慢（实测 1.5s）；
        selectinload 是 1 条主查询 + 每子表 1 条 IN 查询，消除膨胀。
        """
        return (
            db.query(self.model)
            .options(
                selectinload(self.model.goals),
                selectinload(self.model.milestones),
                selectinload(self.model.members),
                selectinload(self.model.monthly_plans),
                selectinload(self.model.weekly_plans),
                selectinload(self.model.progresses),
                selectinload(self.model.member_tasks),
                selectinload(self.model.deliverables),
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

    # ------------------------------------------------------------------
    # 查找：通过子表 ID 查找所属重点工作（tc-3 深链定位）
    # ------------------------------------------------------------------
    @staticmethod
    def find_by_member_task(db: Session, task_id: int) -> int | None:
        row = db.query(PmwbKeyWorkMemberTask.key_work_id).filter(
            PmwbKeyWorkMemberTask.id == task_id
        ).first()
        return row[0] if row else None

    @staticmethod
    def find_by_milestone(db: Session, milestone_id: int) -> int | None:
        row = db.query(PmwbKeyWorkMilestone.key_work_id).filter(
            PmwbKeyWorkMilestone.id == milestone_id
        ).first()
        return row[0] if row else None

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
                PmwbKeyWorkMemberTask.status.notin_(["completed", "cancelled", "delayed"]),
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
                PmwbKeyWorkMilestone.status == "not_started",
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
            .filter(PmwbKeyWorkMemberTask.status == "completed")
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


    # ------------------------------------------------------------------
    # 周反馈（在途工单增量更新，mc-3）
    # ------------------------------------------------------------------
    @staticmethod
    def _week_assignees(db: Session, kw_id: int) -> List[str]:
        """聚合某工单的责任人清单：月/周计划、成员待办 assignee 去重（非空）。"""
        names: set = set()
        for model in (PmwbKeyWorkMonthlyPlan, PmwbKeyWorkWeeklyPlan, PmwbKeyWorkMemberTask):
            rows = (
                db.query(model.assignee)
                .filter(model.key_work_id == kw_id)
                .distinct()
                .all()
            )
            for (n,) in rows:
                if n and str(n).strip():
                    names.add(str(n).strip())
        return sorted(names)

    def list_weekly_feedbacks(self, db: Session, kw_id: int, week: str) -> Dict[str, Any]:
        """某周反馈台账：已反馈记录 + 未反馈责任人清单。"""
        items = (
            db.query(PmwbKeyWorkWeeklyFeedback)
            .filter(
                PmwbKeyWorkWeeklyFeedback.key_work_id == kw_id,
                PmwbKeyWorkWeeklyFeedback.week == week,
            )
            .order_by(
                PmwbKeyWorkWeeklyFeedback.feedback_date.desc(),
                PmwbKeyWorkWeeklyFeedback.id.desc(),
            )
            .all()
        )
        assignees = self._week_assignees(db, kw_id)
        done = {f.assignee for f in items}
        pending = [a for a in assignees if a not in done]
        return {"week": week, "assignees": assignees, "items": items, "pending": pending}

    def weekly_feedback_form(self, db: Session, kw_id: int, week: str) -> Dict[str, Any]:
        """本周反馈工作单：责任人 → 在途子项清单 + 已反馈内容（编辑回显）。"""
        assignees = self._week_assignees(db, kw_id)
        fb_rows = (
            db.query(PmwbKeyWorkWeeklyFeedback)
            .filter(
                PmwbKeyWorkWeeklyFeedback.key_work_id == kw_id,
                PmwbKeyWorkWeeklyFeedback.week == week,
            )
            .all()
        )
        feedback_map = {f.assignee: f for f in fb_rows}

        def _parse_updates(fb) -> List[dict]:
            if not fb or not fb.item_updates:
                return []
            try:
                parsed = json.loads(fb.item_updates)
                return parsed if isinstance(parsed, list) else []
            except Exception:
                return []

        groups = []
        for name in assignees:
            items = []
            for p in (
                db.query(PmwbKeyWorkMonthlyPlan)
                .filter(
                    PmwbKeyWorkMonthlyPlan.key_work_id == kw_id,
                    PmwbKeyWorkMonthlyPlan.assignee == name,
                )
                .order_by(PmwbKeyWorkMonthlyPlan.month)
                .all()
            ):
                items.append({
                    "type": "monthly", "id": p.id,
                    "label": p.title or (p.content or "")[:30] or f"月计划{p.month}",
                    "plan_label": p.month, "due_date": p.due_date, "status": p.status,
                })
            for p in (
                db.query(PmwbKeyWorkWeeklyPlan)
                .filter(
                    PmwbKeyWorkWeeklyPlan.key_work_id == kw_id,
                    PmwbKeyWorkWeeklyPlan.assignee == name,
                )
                .order_by(PmwbKeyWorkWeeklyPlan.week)
                .all()
            ):
                items.append({
                    "type": "weekly", "id": p.id,
                    "label": p.title or (p.content or "")[:30] or f"周计划{p.week}",
                    "plan_label": p.week, "due_date": p.due_date, "status": p.status,
                })
            for t in (
                db.query(PmwbKeyWorkMemberTask)
                .filter(
                    PmwbKeyWorkMemberTask.key_work_id == kw_id,
                    PmwbKeyWorkMemberTask.assignee == name,
                )
                .order_by(PmwbKeyWorkMemberTask.id)
                .all()
            ):
                items.append({
                    "type": "task", "id": t.id,
                    "label": t.title or f"待办#{t.id}",
                    "plan_label": "", "due_date": t.due_date, "status": t.status,
                })
            fb = feedback_map.get(name)
            groups.append({
                "assignee": name,
                "items": items,
                "feedback": {
                    "id": fb.id,
                    "done_summary": fb.done_summary or "",
                    "next_summary": fb.next_summary or "",
                    "risk_note": fb.risk_note or "",
                    "progress": fb.progress,
                    "item_updates": _parse_updates(fb),
                    "feedback_date": fb.feedback_date,
                    "source": fb.source,
                    "updated_at": fb.updated_at,
                } if fb else None,
            })
        return {"week": week, "groups": groups}

    def submit_weekly_feedback(self, db: Session, kw_id: int, payload: dict) -> PmwbKeyWorkWeeklyFeedback:
        """提交一条周反馈（幂等 upsert）：

        1. 同周同责任人已存在 → 更新（重复提交视为编辑）
        2. 自动追加一条 progress 进展日志（reporter=责任人，周反馈汇总）
        3. 按 item_updates 批量更新月/周计划、成员待办状态
        """
        week = payload["week"]
        assignee = payload["assignee"]
        item_updates = payload.get("item_updates") or []

        row = (
            db.query(PmwbKeyWorkWeeklyFeedback)
            .filter(
                PmwbKeyWorkWeeklyFeedback.key_work_id == kw_id,
                PmwbKeyWorkWeeklyFeedback.week == week,
                PmwbKeyWorkWeeklyFeedback.assignee == assignee,
            )
            .first()
        )
        if row:
            for k, v in payload.items():
                if k == "item_updates":
                    setattr(row, "item_updates", json.dumps(v, ensure_ascii=False) if v else None)
                elif hasattr(row, k):
                    setattr(row, k, v)
        else:
            data = dict(payload)
            data["item_updates"] = json.dumps(data.pop("item_updates", None) or [], ensure_ascii=False)
            row = PmwbKeyWorkWeeklyFeedback(key_work_id=kw_id, **data)
            db.add(row)
        db.flush()

        # 2. 追加进展日志（周反馈汇总）
        parts = []
        if payload.get("done_summary"):
            parts.append("本周完成：" + payload["done_summary"])
        if payload.get("next_summary"):
            parts.append("下周计划：" + payload["next_summary"])
        if payload.get("risk_note"):
            parts.append("风险/求助：" + payload["risk_note"])
        content = "；".join(parts) or "（无内容）"
        progress = PmwbKeyWorkProgress(
            key_work_id=kw_id,
            record_date=payload.get("feedback_date") or date.today(),
            reporter=assignee,
            content=f"【周反馈 {week}】{content}",
        )
        db.add(progress)

        # 3. 批量更新子项状态
        for up in item_updates:
            utype, uid, ustatus = up.get("type"), up.get("id"), up.get("status")
            if not ustatus:
                continue
            target = None
            if utype == "monthly":
                target = (
                    db.query(PmwbKeyWorkMonthlyPlan)
                    .filter(
                        PmwbKeyWorkMonthlyPlan.id == uid,
                        PmwbKeyWorkMonthlyPlan.key_work_id == kw_id,
                    )
                    .first()
                )
            elif utype == "weekly":
                target = (
                    db.query(PmwbKeyWorkWeeklyPlan)
                    .filter(
                        PmwbKeyWorkWeeklyPlan.id == uid,
                        PmwbKeyWorkWeeklyPlan.key_work_id == kw_id,
                    )
                    .first()
                )
            elif utype == "task":
                target = (
                    db.query(PmwbKeyWorkMemberTask)
                    .filter(
                        PmwbKeyWorkMemberTask.id == uid,
                        PmwbKeyWorkMemberTask.key_work_id == kw_id,
                    )
                    .first()
                )
            if target is not None:
                target.status = ustatus

        db.commit()
        db.refresh(row)
        return row

    def feedback_overview(self, db: Session, week: str) -> Dict[str, Any]:
        """全部在途工单周反馈总览（列表页/看板消费）。"""
        in_progress = (
            db.query(PmwbKeyWork)
            .filter(PmwbKeyWork.status.in_(["planning", "in_progress", "paused"]))
            .order_by(PmwbKeyWork.updated_at.desc())
            .all()
        )
        rows = []
        for kw in in_progress:
            fb_rows = (
                db.query(PmwbKeyWorkWeeklyFeedback)
                .filter(
                    PmwbKeyWorkWeeklyFeedback.key_work_id == kw.id,
                    PmwbKeyWorkWeeklyFeedback.week == week,
                )
                .all()
            )
            done = {f.assignee for f in fb_rows}
            assignees = self._week_assignees(db, kw.id)
            pending = [a for a in assignees if a not in done]
            rows.append({
                "key_work_id": kw.id,
                "work_no": kw.work_no,
                "title": kw.title,
                "status": kw.status,
                "assignees": assignees,
                "feedback_count": len(fb_rows),
                "pending": pending,
                "all_done": len(assignees) > 0 and not pending,
            })
        return {"week": week, "rows": rows}


keywork_service = KeyWorkService()
