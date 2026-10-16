from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.exceptions import NotFoundException, ValidationException
from db.models import PmwbActiveOptimization, PmwbActiveOptimizationReq, SentEmail, now_cn
from utils.owners import split_owners


# 中国时区（UTC+8），与 models 及 dashboard 保持一致
_CST = timezone(timedelta(hours=8))

_STATUS_LABELS = {
    "pending": "待评估",
    "adopted": "已采纳",
    "rejected": "不采纳",
}

# 单次写入的关联文号上限（超出直接 400，防误传全量需求把工单灌爆）
MAX_REQ_LINKS = 50
# req_id 最大长度（与 pmwb_active_optimization_req.req_id String(255) 对齐）
MAX_REQ_ID_LEN = 255


def _lookup_req_name(db: Session, req_id: str) -> Optional[str]:
    """按文号取需求名称（冗余快照用，取不到返回 None 不影响关联本身）。"""
    row = db.query(SentEmail.req_name).filter(SentEmail.req_id == req_id).first()
    return (row[0] if row else None) or None


class ActiveOptimizationService:
    """主动优化建议工单 Service。"""

    def _get(self, db: Session, opt_id: int) -> Optional[PmwbActiveOptimization]:
        return db.query(PmwbActiveOptimization).filter(PmwbActiveOptimization.id == opt_id).first()

    # ------------------------------------------------------------------
    # 关联需求文号（一对多）
    # ------------------------------------------------------------------
    @staticmethod
    def req_universe(db: Session) -> Set[str]:
        """需求宇宙：sent_emails 去重 req_id。

        **唯一口径**（与 services/requirement.py:24-38 同源），禁止另造第二份。
        """
        return {row[0] for row in db.query(SentEmail.req_id).distinct().all() if row[0]}

    @staticmethod
    def _links_by_opt(db: Session, opt_ids: List[int]) -> Dict[int, list]:
        """批量捞关联行，按 opt_id 分组（避免 N+1）。"""
        if not opt_ids:
            return {}
        rows = (
            db.query(PmwbActiveOptimizationReq)
            .filter(PmwbActiveOptimizationReq.opt_id.in_(opt_ids))
            .order_by(PmwbActiveOptimizationReq.id.asc())
            .all()
        )
        out: Dict[int, list] = {}
        for r in rows:
            out.setdefault(r.opt_id, []).append(r)
        return out

    def _to_out(
        self,
        obj: PmwbActiveOptimization,
        links: Optional[list] = None,
        universe: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """序列化单条工单，补上 req_ids / req_links（含需求名快照与有效性）。

        universe 为 None 时 req_exists 一律 True（调用方不关心有效性，省一次查询）。
        """
        d = {
            "id": obj.id,
            "title": obj.title,
            "current_situation": obj.current_situation,
            "suggestion": obj.suggestion,
            "admin_name": obj.admin_name,
            "status": obj.status,
            "priority": obj.priority,
            "req_id": obj.req_id,
            "note": obj.note,
            "created_by": obj.created_by,
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
        }
        lks = links or []
        d["req_ids"] = [x.req_id for x in lks]
        d["req_links"] = [
            {
                "id": x.id,
                "opt_id": x.opt_id,
                "req_id": x.req_id,
                "req_name": x.req_name,
                "req_exists": True if universe is None else (x.req_id in universe),
                "created_at": x.created_at,
            }
            for x in lks
        ]
        return d

    def list_req_links(self, db: Session, opt_id: int) -> Dict[str, Any]:
        """关联文号列表（带 req_exists 有效性标记）。"""
        if not self._get(db, opt_id):
            raise NotFoundException(f"主动优化工单不存在：{opt_id}")
        rows = (
            db.query(PmwbActiveOptimizationReq)
            .filter(PmwbActiveOptimizationReq.opt_id == opt_id)
            .order_by(PmwbActiveOptimizationReq.id.asc())
            .all()
        )
        universe = self.req_universe(db)
        return {
            "total": len(rows),
            "items": [
                {
                    "id": r.id,
                    "opt_id": r.opt_id,
                    "req_id": r.req_id,
                    "req_name": r.req_name,
                    "req_exists": r.req_id in universe,
                    "created_at": r.created_at,
                }
                for r in rows
            ],
        }

    def _replace_req_links(
        self,
        db: Session,
        obj: PmwbActiveOptimization,
        req_ids: Any,
        strict: bool = False,
        incremental: bool = False,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """写入关联需求文号。

        - incremental=False（PUT/全量覆盖）：差集计算，新增 + 删除多余；
        - incremental=True（POST/增量）：只新增，不删除；
        - strict=True：任一文号无效则整体拒绝（ValidationException）。

        校验链：strip → 去重 → 数量上限 → 长度上限 → 需求宇宙存在性 → 唯一约束兜底。
        返回 {req_ids, created, removed, skipped_duplicate, rejected_invalid}。
        """
        raw = req_ids if isinstance(req_ids, (list, tuple, set)) else ([req_ids] if req_ids else [])
        # split_owners 是唯一拆分实现（去空白 + 去重 + 剔空项）
        wanted: List[str] = split_owners(raw)

        if len(wanted) > MAX_REQ_LINKS:
            raise ValidationException(f"单个工单最多关联 {MAX_REQ_LINKS} 个需求文号，当前 {len(wanted)} 个")
        for rid in wanted:
            if len(rid) > MAX_REQ_ID_LEN:
                raise ValidationException(f"需求文号超长（>{MAX_REQ_ID_LEN}）：{rid[:32]}…")

        if incremental and not wanted:
            raise ValidationException("请至少选择一个需求文号")

        existing_rows = (
            db.query(PmwbActiveOptimizationReq)
            .filter(PmwbActiveOptimizationReq.opt_id == obj.id)
            .all()
        )
        existing_map = {r.req_id: r for r in existing_rows}

        universe = self.req_universe(db)
        rejected_invalid = [rid for rid in wanted if rid not in universe]
        if rejected_invalid and strict:
            raise ValidationException(
                "以下需求文号不在需求宇宙中：" + "、".join(rejected_invalid[:5])
                + ("…" if len(rejected_invalid) > 5 else "")
            )
        accepted = [rid for rid in wanted if rid in universe]

        created: List[str] = []
        skipped_duplicate: List[str] = []
        for rid in accepted:
            if rid in existing_map:
                skipped_duplicate.append(rid)
                continue
            db.add(
                PmwbActiveOptimizationReq(
                    opt_id=obj.id,
                    req_id=rid,
                    req_name=_lookup_req_name(db, rid),
                    created_by=created_by,
                )
            )
            created.append(rid)

        removed: List[str] = []
        if not incremental:
            keep = set(accepted) | set(skipped_duplicate)
            for rid, row in existing_map.items():
                if rid not in keep:
                    db.delete(row)
                    removed.append(rid)

        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise ValidationException("关联需求文号写入冲突（疑似重复关联），请重试")

        # 回填历史列 req_id：取剩余首条，**绝不清空**（service.update 无法清空字段的历史坑）
        remain = [
            r.req_id
            for r in db.query(PmwbActiveOptimizationReq)
            .filter(PmwbActiveOptimizationReq.opt_id == obj.id)
            .order_by(PmwbActiveOptimizationReq.id.asc())
            .all()
        ]
        if remain:
            obj.req_id = remain[0]
        db.commit()
        db.refresh(obj)

        return {
            "req_ids": remain,
            "created": created,
            "removed": removed,
            "skipped_duplicate": skipped_duplicate,
            "rejected_invalid": rejected_invalid,
        }

    def remove_req_link(self, db: Session, opt_id: int, link_id: int) -> Dict[str, Any]:
        """删除单条关联（不存在返回 deleted=False，沿用项目既有删除契约）。"""
        row = (
            db.query(PmwbActiveOptimizationReq)
            .filter(
                PmwbActiveOptimizationReq.id == link_id,
                PmwbActiveOptimizationReq.opt_id == opt_id,
            )
            .first()
        )
        if not row:
            return {"deleted": False}
        db.delete(row)
        db.commit()
        return {"deleted": True}

    def remove_req_links_by_req_id(self, db: Session, opt_id: int, req_id: str) -> Dict[str, Any]:
        """按文号批量删除关联（清理失效文号用）。"""
        cnt = (
            db.query(PmwbActiveOptimizationReq)
            .filter(
                PmwbActiveOptimizationReq.opt_id == opt_id,
                PmwbActiveOptimizationReq.req_id == req_id,
            )
            .delete(synchronize_session=False)
        )
        db.commit()
        return {"deleted": int(cnt or 0)}

    @staticmethod
    def migrate_legacy_req_ids(db: Session) -> int:
        """存量迁移：把 pmwb_active_optimization.req_id 灌入关联表。

        幂等（NOT EXISTS 探测 + uk_opt_req 双保险），可安全重复执行。
        应用启动时调用一次（create_all 只会建表、不会跑 alembic 的数据迁移）。
        返回本次新增行数。
        """
        rows = (
            db.query(PmwbActiveOptimization.id, PmwbActiveOptimization.req_id)
            .filter(PmwbActiveOptimization.req_id.isnot(None))
            .all()
        )
        inserted = 0
        for opt_id, req_id in rows:
            rid = (req_id or "").strip()
            if not rid:
                continue
            exists = (
                db.query(PmwbActiveOptimizationReq.id)
                .filter(
                    PmwbActiveOptimizationReq.opt_id == opt_id,
                    PmwbActiveOptimizationReq.req_id == rid,
                )
                .first()
            )
            if exists:
                continue
            db.add(
                PmwbActiveOptimizationReq(
                    opt_id=opt_id,
                    req_id=rid,
                    req_name=_lookup_req_name(db, rid),
                )
            )
            inserted += 1
        if inserted:
            db.commit()
        return inserted

    def list_with_filters(
        self,
        db: Session,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        admin_name: Optional[str] = None,
        req_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ):
        query = db.query(PmwbActiveOptimization)
        if keyword:
            kw = f"%{keyword}%"
            base = (
                (PmwbActiveOptimization.title.ilike(kw))
                | (PmwbActiveOptimization.current_situation.ilike(kw))
                | (PmwbActiveOptimization.suggestion.ilike(kw))
                | (PmwbActiveOptimization.admin_name.ilike(kw))
                | (PmwbActiveOptimization.req_id.ilike(kw))
            )
            # 关联表也要命中：迁移后主表 req_id 可能是空的，只查主表会漏
            hit_ids = [
                r[0]
                for r in db.query(PmwbActiveOptimizationReq.opt_id)
                .filter(PmwbActiveOptimizationReq.req_id.ilike(kw))
                .distinct()
                .all()
            ]
            query = query.filter(base) if not hit_ids else query.filter(
                base | PmwbActiveOptimization.id.in_(hit_ids)
            )
        if status:
            query = query.filter(PmwbActiveOptimization.status == status)
        if priority:
            query = query.filter(PmwbActiveOptimization.priority == priority)
        if admin_name:
            query = query.filter(PmwbActiveOptimization.admin_name.ilike(f"%{admin_name}%"))
        if req_id:
            # 历史列 + 关联表 双通道命中
            hit_ids = [
                r[0]
                for r in db.query(PmwbActiveOptimizationReq.opt_id)
                .filter(PmwbActiveOptimizationReq.req_id == req_id)
                .distinct()
                .all()
            ]
            cond = PmwbActiveOptimization.req_id == req_id
            query = query.filter(cond) if not hit_ids else query.filter(
                cond | PmwbActiveOptimization.id.in_(hit_ids)
            )

        total = query.count()
        items = (
            query.order_by(PmwbActiveOptimization.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        pages = (total + page_size - 1) // page_size if page_size > 0 else 1
        links_map = self._links_by_opt(db, [o.id for o in items])
        # 仅当存在关联行时才取需求宇宙（避免每个列表请求都白查一次）
        universe = self.req_universe(db) if links_map else None
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
            "items": [self._to_out(o, links_map.get(o.id, []), universe) for o in items],
        }

    def get(self, db: Session, opt_id: int) -> Optional[Dict[str, Any]]:
        """详情（带 req_ids / req_links）。"""
        obj = self._get(db, opt_id)
        if not obj:
            return None
        return self._to_out(
            obj, self._links_by_opt(db, [obj.id]).get(obj.id, []), self.req_universe(db)
        )

    def create(
        self, db: Session, obj_in: Dict[str, Any], created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        data = {k: v for k, v in obj_in.items() if v is not None}
        # req_ids 是关联表字段，不能进主表构造参数
        req_ids = data.pop("req_ids", None)
        data.setdefault("status", "pending")
        data["created_by"] = created_by
        obj = PmwbActiveOptimization(**data)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        if req_ids is not None:
            self._replace_req_links(db, obj, req_ids, created_by=created_by)
        return self._to_out(
            obj, self._links_by_opt(db, [obj.id]).get(obj.id, []), self.req_universe(db)
        )

    def update(self, db: Session, opt_id: int, obj_in: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        obj = self._get(db, opt_id)
        if not obj:
            return None
        payload = dict(obj_in)
        # ★ 必须 pop：通用 setattr 循环只处理 `value is not None`，req_ids 走独立分支
        req_ids = payload.pop("req_ids", None)
        for key, value in payload.items():
            if value is not None and hasattr(obj, key):
                setattr(obj, key, value)
        if req_ids is not None:
            self._replace_req_links(db, obj, req_ids)
        else:
            db.commit()
            db.refresh(obj)
        return self._to_out(
            obj, self._links_by_opt(db, [obj.id]).get(obj.id, []), self.req_universe(db)
        )

    def delete(self, db: Session, opt_id: int) -> bool:
        obj = self._get(db, opt_id)
        if not obj:
            return False
        # 级联清理关联行（项目风格：级联在 service 层做，不用 DB ON DELETE CASCADE）
        db.query(PmwbActiveOptimizationReq).filter(
            PmwbActiveOptimizationReq.opt_id == opt_id
        ).delete(synchronize_session=False)
        db.delete(obj)
        db.commit()
        return True

    def get_summary_stats(self, db: Session) -> Dict[str, int]:
        """首页看板/页面统计用：总数、各状态数、各优先级数、本周新增。"""
        today = datetime.now(_CST).date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=7)
        week_start_dt = datetime.combine(week_start, datetime.min.time())
        week_end_dt = datetime.combine(week_end, datetime.min.time())

        total = db.query(func.count(PmwbActiveOptimization.id)).scalar() or 0
        pending = db.query(func.count(PmwbActiveOptimization.id)).filter(
            PmwbActiveOptimization.status == "pending"
        ).scalar() or 0
        adopted = db.query(func.count(PmwbActiveOptimization.id)).filter(
            PmwbActiveOptimization.status == "adopted"
        ).scalar() or 0
        rejected = db.query(func.count(PmwbActiveOptimization.id)).filter(
            PmwbActiveOptimization.status == "rejected"
        ).scalar() or 0
        p0 = db.query(func.count(PmwbActiveOptimization.id)).filter(
            PmwbActiveOptimization.priority == "P0"
        ).scalar() or 0
        p1 = db.query(func.count(PmwbActiveOptimization.id)).filter(
            PmwbActiveOptimization.priority == "P1"
        ).scalar() or 0
        p2 = db.query(func.count(PmwbActiveOptimization.id)).filter(
            PmwbActiveOptimization.priority == "P2"
        ).scalar() or 0
        p3 = db.query(func.count(PmwbActiveOptimization.id)).filter(
            PmwbActiveOptimization.priority == "P3"
        ).scalar() or 0
        this_week = db.query(func.count(PmwbActiveOptimization.id)).filter(
            PmwbActiveOptimization.created_at >= week_start_dt,
            PmwbActiveOptimization.created_at < week_end_dt,
        ).scalar() or 0

        return {
            "total": total,
            "pending": pending,
            "adopted": adopted,
            "rejected": rejected,
            "p0": p0,
            "p1": p1,
            "p2": p2,
            "p3": p3,
            "this_week": this_week,
        }

    def build_email_variables(
        self, db: Session, obj: Any, scene: str = "sync"
    ) -> Dict[str, Any]:
        """为 mail_dispatch 组装邮件模板变量。

        req_id 语义（2026-10-16 改一对多后）：
          - req_id      : 字符串，取关联表首条；无关联时回落历史列（旧模板零改动）
          - req_ids     : 文号数组（新模板可用）
          - req_id_text : 顿号连接文本（新模板 {{req_id_text}}）
        """
        opt_id = obj.get("id") if isinstance(obj, dict) else getattr(obj, "id", None)
        req_ids: List[str] = []
        if isinstance(obj, dict):
            req_ids = list(obj.get("req_ids") or [])
        if not req_ids and opt_id is not None:
            req_ids = [
                r.req_id
                for r in db.query(PmwbActiveOptimizationReq)
                .filter(PmwbActiveOptimizationReq.opt_id == opt_id)
                .order_by(PmwbActiveOptimizationReq.id.asc())
                .all()
            ]
        legacy = obj.get("req_id") if isinstance(obj, dict) else getattr(obj, "req_id", None)
        if not req_ids and legacy:
            req_ids = [legacy]
        pick = (lambda k, d="": obj.get(k) or d) if isinstance(obj, dict) else (
            lambda k, d="": getattr(obj, k, None) or d
        )
        status = pick("status", "pending")
        return {
            "title": pick("title"),
            "status": status,
            "status_label": _STATUS_LABELS.get(status, status),
            "priority": pick("priority", "P2"),
            "admin_name": pick("admin_name"),
            "req_id": req_ids[0] if req_ids else (legacy or ""),
            "req_ids": req_ids,
            "req_id_text": "、".join(req_ids),
            "current_situation": pick("current_situation", "（无）"),
            "suggestion": pick("suggestion", "（无）"),
            "note": pick("note", "（无）"),
            "scene_label": "催办" if scene == "urge" else "同步",
            "body": "",  # 前端编辑区正文，需要时由调用方填充
        }


active_optimization_service = ActiveOptimizationService()
