from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import PmwbRequirementEvaluation, PmwbRequirementExt, SentEmail
from schemas.common import PaginationParams, PaginationResponse


class RequirementService:
    """需求管理 Service，聚合 sent_emails 和 pmwb_requirement_ext。"""

    def _get_or_create_ext(self, db: Session, req_id: str) -> PmwbRequirementExt:
        ext = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == req_id).first()
        if not ext:
            ext = PmwbRequirementExt(req_id=req_id)
            db.add(ext)
            db.commit()
            db.refresh(ext)
        return ext

    def _merge_ext(self, item: SentEmail, ext: Optional[PmwbRequirementExt] = None, eval_count: int = 0) -> Dict[str, Any]:
        data = {
            "req_id": item.req_id,
            "req_name": item.req_name,
            "proposer": item.proposer,
            "propose_time": item.propose_time,
            "background": item.background,
            "description": item.description,
            "clarification": item.clarification,
            "system_name": item.system_name,
            "sa_name": item.sa_name,
            "send_datetime": item.send_datetime,
            "workload": float(item.workload) if item.workload is not None else None,
            "is_involved": item.is_involved,
            "dev_ticket_no": item.dev_ticket_no,
            "involve_dev": item.involve_dev,
            "eval_count": eval_count,  # 团队评估记录数
            "ext": None,
        }
        if ext:
            data["ext"] = {
                "id": ext.id,
                "req_id": ext.req_id,
                "status": ext.status,
                "tags": ext.tags,
                "personal_note": ext.personal_note,
                "priority": ext.priority,
                "owner_note": ext.owner_note,
                "created_at": ext.created_at,
                "updated_at": ext.updated_at,
            }
        return data

    def list_with_filters(
        self,
        db: Session,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        system_name: Optional[str] = None,
        is_involved: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginationResponse[Dict[str, Any]]:
        # 基础查询：从 sent_emails 中按需求数号去重（同一需求只取最新一条）
        base_query = db.query(
            SentEmail.req_id,
            func.max(SentEmail.id).label('max_id')
        ).group_by(SentEmail.req_id)

        # 子查询获取每个需求的最新记录 ID
        from sqlalchemy import text
        subq = base_query.subquery()

        if keyword:
            subq_filtered = db.query(subq.c.req_id).join(
                SentEmail, SentEmail.req_id == subq.c.req_id
            ).filter(
                (SentEmail.req_id.ilike(f"%{keyword}%"))
                | (SentEmail.req_name.ilike(f"%{keyword}%"))
                | (SentEmail.proposer.ilike(f"%{keyword}%"))
            )
            matched_ids = [row[0] for row in subq_filtered.all()]
            subq = base_query.filter(subq.c.req_id.in_(matched_ids))

        # 获取去重后的总需求条数
        total_query = db.query(func.count()).select_from(subq)
        total = total_query.scalar() or 0

        # 分页取最新记录 ID
        paginated = (
            db.query(subq.c.req_id, subq.c.max_id)
            .order_by(subq.c.max_id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        max_ids = [row.max_id for row in paginated]

        # 用这些 ID 查出完整的 SentEmail 记录
        items_query = db.query(SentEmail).filter(SentEmail.id.in_(max_ids))
        if system_name:
            items_query = items_query.filter(SentEmail.system_name == system_name)
        if is_involved is not None:
            items_query = items_query.filter(SentEmail.is_involved == is_involved)
        # 按 max_id 降序保持顺序
        id_order = {mid: idx for idx, mid in enumerate(max_ids)}
        items = sorted(items_query.all(), key=lambda x: id_order.get(x.id, 0))

        ext_map = {}
        if status or priority:
            ext_query = db.query(PmwbRequirementExt)
            if status:
                ext_query = ext_query.filter(PmwbRequirementExt.status == status)
            if priority:
                ext_query = ext_query.filter(PmwbRequirementExt.priority == priority)
            ext_rows = ext_query.all()
            ext_map = {row.req_id: row for row in ext_rows}
            req_ids = {item.req_id for item in items}
            ext_map.update({row.req_id: row for row in ext_rows if row.req_id in req_ids})
        else:
            req_ids = {item.req_id for item in items}
            ext_rows = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id.in_(req_ids)).all()
            ext_map = {row.req_id: row for row in ext_rows}

        # 统计每个需求的团队评估数量（以可编辑评估表为准，无记录时回退到邮件数）
        req_ids = {item.req_id for item in items}
        sent_counts = (
            db.query(SentEmail.req_id, func.count(SentEmail.id))
            .filter(SentEmail.req_id.in_(req_ids))
            .group_by(SentEmail.req_id)
            .all()
        )
        sent_count_map = {row[0]: row[1] for row in sent_counts}
        eval_row_counts = (
            db.query(PmwbRequirementEvaluation.req_id, func.count(PmwbRequirementEvaluation.id))
            .filter(PmwbRequirementEvaluation.req_id.in_(req_ids))
            .group_by(PmwbRequirementEvaluation.req_id)
            .all()
        )
        eval_row_map = {row[0]: row[1] for row in eval_row_counts}
        eval_count_map = {}
        for rid in req_ids:
            eval_count_map[rid] = eval_row_map.get(rid, 0) or sent_count_map.get(rid, 0)

        merged = [self._merge_ext(item, ext_map.get(item.req_id), eval_count_map.get(item.req_id, 0)) for item in items]
        return PaginationResponse.create(
            total=total,
            page=page,
            page_size=page_size,
            items=merged,
        )

    def get(self, db: Session, req_id: str) -> Optional[Dict[str, Any]]:
        item = db.query(SentEmail).filter(SentEmail.req_id == req_id).first()
        if not item:
            return None
        ext = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == req_id).first()
        eval_count = db.query(SentEmail).filter(SentEmail.req_id == req_id).count()
        return self._merge_ext(item, ext, eval_count)

    def update_ext(self, db: Session, req_id: str, obj_in: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        item = db.query(SentEmail).filter(SentEmail.req_id == req_id).first()
        if not item:
            return None
        ext = self._get_or_create_ext(db, req_id)
        for key, value in obj_in.items():
            if value is not None and hasattr(ext, key):
                setattr(ext, key, value)
        db.commit()
        db.refresh(ext)
        return self._merge_ext(item, ext)

    def get_stats(self, db: Session) -> Dict[str, int]:
        # 按需求文号去重统计（同一需求多次发邮件只算 1 条）
        total = db.query(SentEmail.req_id).distinct().count()
        involved = (
            db.query(SentEmail.req_id)
            .filter(SentEmail.is_involved == 1)
            .distinct()
            .count()
        )
        counts = (
            db.query(PmwbRequirementExt.status, func.count(PmwbRequirementExt.id))
            .group_by(PmwbRequirementExt.status)
            .all()
        )
        status_map = {row[0]: row[1] for row in counts}
        return {
            "total": total,
            "proposed": status_map.get("proposed", 0),
            "accepted": status_map.get("accepted", 0),
            "dev": status_map.get("dev", 0),
            "closed": status_map.get("closed", 0),
            "paused": status_map.get("paused", 0),
            "involved": involved,
        }

    def get_evaluations(self, db: Session, req_id: str) -> List[Dict[str, Any]]:
        """获取需求下所有团队评估记录（可自由增删改的清单）。

        首次访问且尚未播种时，从只读来源 sent_emails 自动播种出可编辑记录，
        并打上 eval_seeded 标记；之后以 pmwb_requirement_evaluation 为唯一权威
        来源（支持增/删/改）。删除后的记录不会因重新读取而复活。

        读取时若评估记录本身的 sa_name/system_name 为空，则回退到其溯源来源
        sent_emails（通过 sent_email_id 关联）补全展示，避免子表出现空白列。
        """
        existing = (
            db.query(PmwbRequirementEvaluation)
            .filter(PmwbRequirementEvaluation.req_id == req_id)
            .order_by(PmwbRequirementEvaluation.id.asc())
            .all()
        )
        if not existing:
            ext = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == req_id).first()
            if not (ext and ext.eval_seeded):
                # 尚未播种：从邮件导入为可编辑记录（仅此一次）
                source_items = (
                    db.query(SentEmail)
                    .filter(SentEmail.req_id == req_id)
                    .order_by(SentEmail.id.asc())
                    .all()
                )
                for item in source_items:
                    ev = PmwbRequirementEvaluation(
                        sent_email_id=item.id,
                        req_id=item.req_id,
                        req_name=item.req_name,
                        proposer=item.proposer,
                        send_datetime=item.send_datetime,
                        sa_name=item.sa_name,
                        system_name=item.system_name,
                        workload=float(item.workload) if item.workload is not None else None,
                        review_workload=None,
                        opinion="",
                        dev_ticket_no=item.dev_ticket_no,
                    )
                    db.add(ev)
                if ext is None:
                    ext = PmwbRequirementExt(req_id=req_id)
                    db.add(ext)
                ext.eval_seeded = 1
                db.commit()
                existing = (
                    db.query(PmwbRequirementEvaluation)
                    .filter(PmwbRequirementEvaluation.req_id == req_id)
                    .order_by(PmwbRequirementEvaluation.id.asc())
                    .all()
                )
        # 溯源补全：评估记录本身 sa_name/system_name 为空时，回退 sent_emails 源值
        sent_ids = [ev.sent_email_id for ev in existing if ev.sent_email_id]
        src_map = {}
        if sent_ids:
            src_rows = db.query(SentEmail).filter(SentEmail.id.in_(sent_ids)).all()
            src_map = {s.id: s for s in src_rows}
        result = []
        for ev in existing:
            d = self._eval_to_dict(ev)
            src = src_map.get(ev.sent_email_id)
            if src:
                if not d.get("sa_name"):
                    d["sa_name"] = src.sa_name
                if not d.get("system_name"):
                    d["system_name"] = src.system_name
            result.append(d)
        return result

    def _eval_to_dict(self, ev: "PmwbRequirementEvaluation") -> Dict[str, Any]:
        return {
            "id": ev.id,
            "req_id": ev.req_id,
            "req_name": ev.req_name,
            "proposer": ev.proposer,
            "sa_name": ev.sa_name,
            "system_name": ev.system_name,
            "workload": float(ev.workload) if ev.workload is not None else None,
            "review_workload": float(ev.review_workload) if ev.review_workload is not None else None,
            "opinion": ev.opinion or "",
            "send_datetime": ev.send_datetime,
            "dev_ticket_no": ev.dev_ticket_no or "",
        }

    def create_evaluation(self, db: Session, req_id: str, obj_in: Dict[str, Any]) -> Dict[str, Any]:
        """新增一条团队评估记录（手动录入，sent_email_id 为 NULL）。"""
        item = db.query(SentEmail).filter(SentEmail.req_id == req_id).first()
        ev = PmwbRequirementEvaluation(
            sent_email_id=None,
            req_id=req_id,
            sa_name=obj_in.get("sa_name"),
            system_name=obj_in.get("system_name"),
            workload=obj_in.get("workload"),
            review_workload=obj_in.get("review_workload"),
            opinion=obj_in.get("opinion") or "",
            dev_ticket_no=obj_in.get("dev_ticket_no"),
        )
        # 借用该需求下某条只读邮件的上下文补全展示字段
        if item:
            ev.req_name = item.req_name
            ev.proposer = item.proposer
            ev.send_datetime = item.send_datetime
        db.add(ev)
        # 打上已播种标记，确保之后即使记录被删空也不会从邮件复活
        ext = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == req_id).first()
        if ext is None:
            ext = PmwbRequirementExt(req_id=req_id)
            db.add(ext)
        ext.eval_seeded = 1
        db.commit()
        db.refresh(ev)
        return self._eval_to_dict(ev)

    def update_evaluation(self, db: Session, eval_id: int, obj_in: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新单条团队评估记录（按评估记录自身 id）。"""
        ev = (
            db.query(PmwbRequirementEvaluation)
            .filter(PmwbRequirementEvaluation.id == eval_id)
            .first()
        )
        if not ev:
            return None
        allowed = {"sa_name", "system_name", "workload", "review_workload", "opinion", "dev_ticket_no"}
        for key, value in obj_in.items():
            if key in allowed and hasattr(ev, key):
                setattr(ev, key, value)
        db.commit()
        db.refresh(ev)
        return self._eval_to_dict(ev)

    def delete_evaluation(self, db: Session, eval_id: int) -> bool:
        """删除单条团队评估记录。"""
        ev = (
            db.query(PmwbRequirementEvaluation)
            .filter(PmwbRequirementEvaluation.id == eval_id)
            .first()
        )
        if not ev:
            return False
        db.delete(ev)
        db.commit()
        return True

    def get_systems(self, db: Session) -> List[str]:
        rows = db.query(SentEmail.system_name).distinct().filter(SentEmail.system_name.isnot(None)).all()
        return [row[0] for row in rows if row[0]]


requirement_service = RequirementService()
