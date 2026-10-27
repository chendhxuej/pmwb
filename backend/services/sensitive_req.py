"""敏感需求跟踪服务：自动入池 + 倒排里程碑 + 团队调度督办（需求与交付子模块，2026-10-25）。

业务诉求（老大 2026-10-25）：
  P0/P1 等敏感需求原则上都有明确的上线时间要求，需围绕该时间对
  需求评估 → 方案制定 → 开发 → 测试 → 上线交付 5 个阶段做**倒排**；
  每个阶段有明确责任人，按约定时间完成，未完成及时督办协调；
  管控粒度 = **需求 × 团队 × 阶段**（每个团队独立 5 阶段排期与督办）。

设计铁律（勿违反）：
  1. **只存跟踪态，不复制需求本体**：需求名称/优先级/状态/上线要求时间
     一律实时回读 sent_emails + pmwb_requirement_ext；
  2. **上线要求时间（倒排终点）权威源 = pmwb_requirement_ext.version_required_date**
     （老大拍板），本服务不另存 deadline 字段，杜绝第二真相源；
  3. **敏感判定唯一源 = constants/levels.py::is_high_level**（P0/P1/集团需求/紧急需求），
     本文件只调用不复写；**补充（2026-10-27）**：人工「超期风险」标记
     （ext.overdue_risk，需求列表打标）与级别命中同等入池待遇，
     judge_reason 单值优先级 R4:lock > R1:级别 > R5:dev_overdue，不拼接；
  4. **团队唯一源 = services/vendor_dev.py::active_team_systems()**
     （团队评估 workload>0 的系统），禁另造团队清单；
  5. **环节事实时间只读引用** stage_log 与 ext.delivered_date，里程碑 actual_end
     仅为人工确认值，读接口以 actual_hint 提示可回填的事实时间；
  6. 跟踪态/里程碑态文案唯一源 = constants/status_registry.py
     （域 key：sensitive_req_track / sensitive_milestone）。

同步语义：`sync` 为显式幂等写操作（进入页面触发一次），读接口只读。
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from constants import levels, status_registry
from core.exceptions import NotFoundException, ValidationException
from db.models import (
    EmailRecord,
    PmwbRequirementExt,
    PmwbRequirementStageLog,
    PmwbSensitiveReqMilestone,
    PmwbSensitiveReqTrack,
    PmwbRequirementEvaluation,
    PmwbReqVendorDev,
    SentEmail,
    now_cn,
)
from schemas.sensitive_req import (
    SensitiveReqItem,
    SensitiveReqMilestoneSaveRequest,
    SensitiveReqMilestoneUpdateRequest,
    SensitiveReqQuery,
    SensitiveReqSendRequest,
    SensitiveReqTrackUpdateRequest,
)
from services.mail_dispatch import _render_mail, dispatch_email
from services.vendor_dev import active_team_systems, active_team_systems_batch
from utils.owners import split_owners
from utils.validators import split_and_validate_emails

logger = logging.getLogger("pmwb.sensitive_req")

# 跟踪态域 key（constants/status_registry.py::_SENSITIVE_REQ_TRACK）
TRACK_DOMAIN = "sensitive_req_track"
MILESTONE_DOMAIN = "sensitive_milestone"

# 「在跟池」跟踪态；resolved / dropped 属历史态，需显式 include_closed 才展示
OPEN_TRACK_STATUSES = ("active", "delayed", "escalated")
CLOSED_TRACK_STATUSES = ("resolved", "dropped")

# 人工覆盖合法值（敏感域无 escalate：督办升级由督办动作/人工改态承载）
OVERRIDES = ("lock", "dismiss")

# 敏感域 5 阶段（独立于 requirement_stage 的 6 环节；test 是敏感域新增管控点）
STAGE_ORDER: Tuple[str, ...] = ("evaluate", "plan", "dev", "test", "deploy")
STAGE_LABELS: Dict[str, str] = {
    "evaluate": "需求评估",
    "plan": "方案制定",
    "dev": "开发",
    "test": "测试",
    "deploy": "上线交付",
}

# 倒排模板（老大拍板：模板缓冲 + 手工调整）：
# 各阶段计划完成日 = 上线要求日 - OFFSET 天；planned_start = 上一阶段 planned_end + 1 天。
# deploy 固定 0（上线日当天交付），评估最早。仅作建议值，前端可逐项改后保存。
TEMPLATE_OFFSETS: Dict[str, int] = {
    "deploy": 0,
    "test": 4,
    "dev": 10,
    "plan": 18,
    "evaluate": 25,
}

# 里程碑未完成即算超期；planned_end 临近 N 天内算临期
DUE_SOON_DAYS = 3

# 无厂家评估时的兜底团队名（ext.system_name 也为空时使用）
FALLBACK_TEAM = "（未分配团队）"


def _norm_req_id(req_id: Optional[str]) -> str:
    return (req_id or "").strip()


class SensitiveReqService:
    """敏感需求聚合/倒排/督办服务。"""

    # ------------------------------------------------------------------
    # 需求宇宙：实时回读 ext（+ sent_emails 名称兜底）
    # ------------------------------------------------------------------
    def _load_ext_index(self, db: Session) -> Dict[str, PmwbRequirementExt]:
        return {
            ext.req_id: ext
            for ext in db.query(PmwbRequirementExt).all()
            if _norm_req_id(ext.req_id)
        }

    def _load_name_index(self, db: Session) -> Dict[str, str]:
        """req_id → 展示名：ext.req_name 优先，sent_emails.req_name 兜底。"""
        names: Dict[str, str] = {}
        for rid, rname in (
            db.query(SentEmail.req_id, SentEmail.req_name)
            .filter(SentEmail.req_id.isnot(None))
            .all()
        ):
            rid = _norm_req_id(rid)
            if rid and rname and rid not in names:
                names[rid] = rname
        for rid, rname in (
            db.query(PmwbRequirementExt.req_id, PmwbRequirementExt.req_name).all()
        ):
            rid = _norm_req_id(rid)
            if rid and rname:
                names[rid] = rname
        return names

    def _get_track_row(self, db: Session, req_id: str) -> PmwbSensitiveReqTrack:
        row = (
            db.query(PmwbSensitiveReqTrack)
            .filter(PmwbSensitiveReqTrack.req_id == _norm_req_id(req_id))
            .first()
        )
        if row is None:
            raise NotFoundException(f"敏感需求跟踪记录不存在：{req_id}")
        return row

    # ------------------------------------------------------------------
    # 里程碑读写
    # ------------------------------------------------------------------
    def _milestones_of(self, db: Session, req_id: str) -> List[PmwbSensitiveReqMilestone]:
        return (
            db.query(PmwbSensitiveReqMilestone)
            .filter(PmwbSensitiveReqMilestone.req_id == _norm_req_id(req_id))
            .order_by(
                PmwbSensitiveReqMilestone.team_system_name,
                PmwbSensitiveReqMilestone.id,
            )
            .all()
        )

    def _stage_log_hints(self, db: Session, req_id: str) -> Dict[str, Optional[date]]:
        """敏感阶段 → 可回填的事实完成日（只读引用，不改库）。

        映射：evaluate→requirement_stage.evaluate.left_at；dev→dev.left_at；
        deploy→ext.delivered_date（实际上线日）。其余阶段无自动事实源。
        """
        hints: Dict[str, Optional[date]] = {}
        ext = (
            db.query(PmwbRequirementExt)
            .filter(PmwbRequirementExt.req_id == _norm_req_id(req_id))
            .first()
        )
        hints["deploy"] = ext.delivered_date if ext else None
        logs = {
            log.stage: log
            for log in db.query(PmwbRequirementStageLog)
            .filter(PmwbRequirementStageLog.req_id == _norm_req_id(req_id))
            .all()
        }
        for sr_stage, log_stage in (("evaluate", "evaluate"), ("dev", "dev")):
            log = logs.get(log_stage)
            hints[sr_stage] = log.left_at.date() if (log and log.left_at) else None
        hints.setdefault("plan", None)
        hints.setdefault("test", None)
        return hints

    def _compose_milestone(
        self,
        ms: PmwbSensitiveReqMilestone,
        hint: Optional[date],
        today: date,
    ) -> Dict[str, Any]:
        st = status_registry.get_status(MILESTONE_DOMAIN, ms.status)
        overdue = bool(
            ms.planned_end and ms.planned_end < today and ms.status != "done"
        )
        due_soon = bool(
            ms.planned_end and not overdue
            and timedelta(days=0) <= (ms.planned_end - today) <= timedelta(days=DUE_SOON_DAYS)
            and ms.status != "done"
        )
        return {
            "id": ms.id,
            "req_id": ms.req_id,
            "team_system_name": ms.team_system_name,
            "stage": ms.stage,
            "stage_label": STAGE_LABELS.get(ms.stage, ms.stage),
            "stage_order": STAGE_ORDER.index(ms.stage) if ms.stage in STAGE_ORDER else 99,
            "owner": ms.owner or "",
            "owner_list": split_owners(ms.owner or ""),
            "planned_start": ms.planned_start,
            "planned_end": ms.planned_end,
            "actual_end": ms.actual_end,
            "actual_hint": hint,
            "status": ms.status,
            "status_label": st.label if st else ms.status,
            "tone": st.tone if st else "info",
            "risk_note": ms.risk_note or "",
            "source": ms.source or "manual",
            "is_overdue": overdue,
            "overdue_days": (today - ms.planned_end).days if overdue else 0,
            "is_due_soon": due_soon,
            "urge_count": ms.urge_count or 0,
            "last_urged_at": ms.last_urged_at,
        }

    # ------------------------------------------------------------------
    # 条目合成（列表/详情共用）
    # ------------------------------------------------------------------
    def _compose_item(
        self,
        row: PmwbSensitiveReqTrack,
        ext: Optional[PmwbRequirementExt],
        name: str,
        milestones: List[PmwbSensitiveReqMilestone],
        today: date,
        hints: Optional[Dict[str, Optional[date]]] = None,
    ) -> SensitiveReqItem:
        st = status_registry.get_status(TRACK_DOMAIN, row.track_status)
        deadline = ext.version_required_date if ext else None

        composed: List[Dict[str, Any]] = []
        hint_map = hints or {}
        for ms in milestones:
            composed.append(self._compose_milestone(ms, hint_map.get(ms.stage), today))

        overdue_ms = [m for m in composed if m["is_overdue"]]
        due_soon_ms = [m for m in composed if m["is_due_soon"]]

        # 最近的关键里程碑：超期 > 临期 > 未来最早的未完成
        pending = [m for m in composed if m["status"] != "done"]
        pending.sort(key=lambda m: (m["planned_end"] or date.max, m["stage_order"]))
        focus = None
        if overdue_ms:
            focus = sorted(overdue_ms, key=lambda m: m["planned_end"])[0]
        elif due_soon_ms:
            focus = sorted(due_soon_ms, key=lambda m: m["planned_end"])[0]
        elif pending:
            focus = pending[0]

        days_to_deadline = (deadline - today).days if deadline else None

        return SensitiveReqItem(
            req_id=row.req_id,
            req_name=name or "（未知需求）",
            priority=ext.priority if ext else None,
            priority_label=levels.priority_label(ext.priority) if ext else "",
            req_status=ext.status if ext else "",
            req_status_label=(
                status_registry.get_status("requirement", ext.status).label
                if ext and status_registry.get_status("requirement", ext.status)
                else (ext.status if ext else "")
            ),
            version_required_date=deadline,
            delivered_date=ext.delivered_date if ext else None,
            days_to_deadline=days_to_deadline,
            deadline_missed=bool(
                deadline and deadline < today and (not ext or ext.status != "closed")
            ),
            teams=sorted({m.team_system_name for m in milestones}),
            milestone_total=len(composed),
            milestone_done=sum(1 for m in composed if m["status"] == "done"),
            overdue_count=len(overdue_ms),
            due_soon_count=len(due_soon_ms),
            focus_milestone=focus,
            is_sensitive=bool(row.is_sensitive),
            judge_reason=row.judge_reason or "",
            level_code=row.level_code,
            track_status=row.track_status,
            track_label=st.label if st else row.track_status,
            track_tone=st.tone if st else "info",
            manual_override=row.manual_override,
            urge_count=row.urge_count or 0,
            last_urged_at=row.last_urged_at,
            first_seen_at=row.first_seen_at,
            last_seen_at=row.last_seen_at,
            first_overdue_at=row.first_overdue_at,
            source_url=f"/requirement-delivery?sensitive={row.req_id}",
            source_gone=ext is None,
            milestones=composed,
        )

    # ------------------------------------------------------------------
    # sync：自动入池（幂等）
    # ------------------------------------------------------------------
    def sync(self, db: Session) -> Dict[str, Any]:
        """扫描 ext → 敏感判定 → upsert 跟踪表 → 里程碑逾期回写跟踪态 → 源消失检测。"""
        started = now_cn()
        today = started.date()

        exts = self._load_ext_index(db)
        existing: Dict[str, PmwbSensitiveReqTrack] = {
            r.req_id: r for r in db.query(PmwbSensitiveReqTrack).all()
        }

        # 逐需求逾期/完成度批量预载
        all_ms = (
            db.query(PmwbSensitiveReqMilestone)
            .filter(PmwbSensitiveReqMilestone.status != "done",
                    PmwbSensitiveReqMilestone.planned_end.isnot(None))
            .all()
        )
        overdue_map: Dict[str, date] = {}
        for ms in all_ms:
            if ms.planned_end < today:
                cur = overdue_map.get(ms.req_id)
                if cur is None or ms.planned_end < cur:
                    overdue_map[ms.req_id] = ms.planned_end

        stats: Dict[str, Any] = {
            "scanned": len(exts), "sensitive": 0, "added": 0, "updated": 0,
            "resolved": 0, "delayed": 0, "demoted": 0, "removed": 0,
        }
        seen: set = set()

        for req_id, ext in exts.items():
            seen.add(req_id)
            row = existing.get(req_id)
            override = row.manual_override if row else None
            if override == "dismiss":
                continue  # 人工移出：永不复活

            # 纳入判定（单一真相源）：级别命中（levels.py 唯一实现）
            # 或 人工「超期风险」标记（ext.overdue_risk，需求列表打标）→ 同等入池待遇
            risk_flag = bool(getattr(ext, "overdue_risk", 0))
            is_high = levels.is_high_level(ext.priority) or risk_flag

            # ── 非敏感：已有行降级退池（lock 保池）─────────────
            if not is_high and override != "lock":
                if row and row.is_sensitive:
                    row.is_sensitive = 0
                    row.track_status = "dropped"
                    row.removed_at = started
                    row.updated_at = started
                    stats["demoted"] += 1
                continue

            # judge_reason 单值优先级：lock > 级别命中(R1) > 超期风险(R5)，不拼接
            code = levels.normalize_priority(ext.priority)
            level_hit = levels.is_high_level(ext.priority)
            if override == "lock":
                reason = f"R4:lock"
            elif level_hit:
                reason = f"R1:{code}" if code else f"R1:{levels.priority_label(ext.priority)}"
            else:
                reason = f"R5:dev_overdue"
            # level_code 仅级别命中时保留（R5 单独命中时置空，级别语义以 judge_reason 为准）
            track_level_code = code if level_hit else None

            if row is None:
                row = PmwbSensitiveReqTrack(
                    req_id=req_id,
                    is_sensitive=1,
                    judge_reason=reason,
                    level_code=track_level_code,
                    manual_override=override,
                    track_status="active",
                    urge_count=0,
                    first_seen_at=started,
                    last_seen_at=started,
                    created_at=started,
                    updated_at=started,
                )
                db.add(row)
                stats["added"] += 1
            else:
                row.is_sensitive = 1
                row.judge_reason = reason
                row.level_code = track_level_code
                row.last_seen_at = started
                row.updated_at = started
                stats["updated"] += 1
            stats["sensitive"] += 1

            # ── 上线闭环：需求已 closed → resolved ─────────────
            if ext.status == "closed":
                if row.track_status in OPEN_TRACK_STATUSES:
                    row.track_status = "resolved"
                    row.resolved_at = started
                    stats["resolved"] += 1
                continue

            # ── 里程碑超期 → delayed（escalated 不降级）────────
            first_overdue = overdue_map.get(req_id)
            if first_overdue:
                if row.track_status in ("active",):
                    row.track_status = "delayed"
                    stats["delayed"] += 1
                if row.first_overdue_at is None or first_overdue < row.first_overdue_at:
                    row.first_overdue_at = first_overdue
            elif row.track_status == "delayed":
                row.track_status = "active"  # 逾期解除（里程碑补完成/改期）

        # ── 源需求消失（ext 行删除）→ dropped ─────────────────
        for req_id, row in existing.items():
            if req_id in seen:
                continue
            if row.track_status not in OPEN_TRACK_STATUSES:
                continue
            row.track_status = "dropped"
            row.is_sensitive = 0
            row.removed_at = started
            row.updated_at = started
            stats["removed"] += 1

        db.commit()
        logger.info(
            "敏感需求同步完成：扫描 %s / 敏感 %s / 新增 %s / 刷新 %s / 闭环 %s / 降级 %s / 移除 %s",
            stats["scanned"], stats["sensitive"], stats["added"], stats["updated"],
            stats["resolved"], stats["demoted"], stats["removed"],
        )
        return stats

    # ------------------------------------------------------------------
    # 列表 / 统计
    # ------------------------------------------------------------------
    def _load_pool(self, db: Session) -> List[SensitiveReqItem]:
        rows = db.query(PmwbSensitiveReqTrack).all()
        if not rows:
            return []
        exts = self._load_ext_index(db)
        names = self._load_name_index(db)
        today = now_cn().date()
        ms_rows = (
            db.query(PmwbSensitiveReqMilestone)
            .filter(PmwbSensitiveReqMilestone.req_id.in_([r.req_id for r in rows]))
            .all()
        )
        ms_by_req: Dict[str, List[PmwbSensitiveReqMilestone]] = {}
        for ms in ms_rows:
            ms_by_req.setdefault(ms.req_id, []).append(ms)

        items: List[SensitiveReqItem] = []
        for row in rows:
            ext = exts.get(row.req_id)
            hints = (
                self._stage_log_hints(db, row.req_id)
                if ext is not None else None
            )
            items.append(self._compose_item(
                row, ext, names.get(row.req_id, ""), ms_by_req.get(row.req_id, []), today,
                hints=hints,
            ))
        return items

    def list_reqs(self, db: Session, query: SensitiveReqQuery) -> Dict[str, Any]:
        pool = self._load_pool(db)

        if query.track_status:
            pool = [it for it in pool if it.track_status == query.track_status]
        elif not query.include_closed:
            pool = [it for it in pool if it.track_status in OPEN_TRACK_STATUSES]
        if query.team:
            pool = [it for it in pool if query.team in it.teams]
        if query.only_overdue:
            pool = [it for it in pool if it.overdue_count > 0]
        if query.keyword:
            kw = query.keyword.strip().lower()
            pool = [
                it for it in pool
                if kw in (it.req_name or "").lower()
                or kw in (it.req_id or "").lower()
            ]

        def _sort_key(it: SensitiveReqItem) -> Tuple:
            code = it.level_code or ("P0" if it.priority and levels.is_free_text_high(it.priority) else None)
            return (
                0 if it.deadline_missed else 1,
                levels.level_rank(code or it.priority),
                it.version_required_date or date.max,
                -(it.overdue_count),
            )

        pool.sort(key=_sort_key)
        total = len(pool)
        start = (query.page - 1) * query.page_size
        page_items = pool[start:start + query.page_size]
        return {
            "total": total,
            "page": query.page,
            "page_size": query.page_size,
            "items": page_items,
            "summary": {
                "in_pool": sum(1 for it in pool if it.track_status in OPEN_TRACK_STATUSES),
                "overdue": sum(1 for it in pool if it.overdue_count > 0),
                "escalated": sum(1 for it in pool if it.track_status == "escalated"),
                "deadline_missed": sum(1 for it in pool if it.deadline_missed),
            },
        }

    def get_stats(self, db: Session) -> Dict[str, Any]:
        pool = [it for it in self._load_pool(db) if it.track_status in OPEN_TRACK_STATUSES]
        by_track: Dict[str, int] = {}
        by_level: Dict[str, int] = {}
        by_team: Dict[str, int] = {}
        for it in pool:
            by_track[it.track_status] = by_track.get(it.track_status, 0) + 1
            key = it.level_code or levels.priority_label(it.priority or "")
            by_level[key] = by_level.get(key, 0) + 1
            for t in it.teams:
                by_team[t] = by_team.get(t, 0) + 1
        return {
            "total": len(pool),
            "overdue": sum(1 for it in pool if it.overdue_count > 0),
            "due_soon": sum(1 for it in pool if it.due_soon_count > 0 and it.overdue_count == 0),
            "escalated": sum(1 for it in pool if it.track_status == "escalated"),
            "deadline_missed": sum(1 for it in pool if it.deadline_missed),
            "by_track_status": by_track,
            "by_level": by_level,
            "by_team": dict(sorted(by_team.items(), key=lambda kv: -kv[1])),
        }

    def get_detail(self, db: Session, req_id: str) -> Dict[str, Any]:
        """单个敏感需求详情：跟踪态 + 需求本体 + 全量里程碑（含泳道分组）。"""
        req_id = _norm_req_id(req_id)
        row = self._get_track_row(db, req_id)
        ext = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == req_id).first()
        if ext is None:
            raise NotFoundException(f"需求不存在：{req_id}")
        names = self._load_name_index(db)
        today = now_cn().date()
        item = self._compose_item(
            row, ext, names.get(req_id, ""), self._milestones_of(db, req_id), today,
            hints=self._stage_log_hints(db, req_id),
        )
        # 泳道分组：团队 → 阶段升序（milestones 为 pydantic 模型，用属性访问）
        lanes: Dict[str, List[Dict[str, Any]]] = {}
        for ms in sorted(item.milestones, key=lambda m: (m.team_system_name, m.stage_order)):
            lanes.setdefault(ms.team_system_name, []).append(ms.model_dump(mode="json"))
        return {
            **item.model_dump(mode="json"),
            "lanes": lanes,
            "teams_detail": active_team_systems(db, req_id),
        }

    # ------------------------------------------------------------------
    # 倒排建议 + 里程碑保存（PUT=全量覆盖，与主动优化 req-links 同口径）
    # ------------------------------------------------------------------
    def plan_suggestion(self, db: Session, req_id: str) -> Dict[str, Any]:
        """按模板缓冲生成倒排建议（不落库），供前端确认后保存。"""
        req_id = _norm_req_id(req_id)
        ext = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == req_id).first()
        if ext is None:
            raise NotFoundException(f"需求不存在：{req_id}")
        if not ext.version_required_date:
            raise ValidationException(
                "该需求未填写「版本要求上线时间」，请先在需求详情补填后再倒排"
            )
        deadline: date = ext.version_required_date

        teams = [t["system_name"] for t in active_team_systems(db, req_id)]
        if not teams:
            teams = [ext.system_name.strip()] if (ext.system_name or "").strip() else [FALLBACK_TEAM]

        # 阶段责任人预填：评估→SA，开发→厂家负责人，其余留空人工填
        team_meta = {t["system_name"]: t for t in active_team_systems(db, req_id)}

        items: List[Dict[str, Any]] = []
        for team in teams:
            prev_end: Optional[date] = None
            for stage in STAGE_ORDER:
                planned_end = deadline - timedelta(days=TEMPLATE_OFFSETS[stage])
                planned_start = (
                    prev_end + timedelta(days=1) if prev_end
                    else planned_end - timedelta(days=6)
                )
                owner = ""
                if stage == "evaluate":
                    owner = ext.sa_name or ""
                elif stage == "dev":
                    owner = (team_meta.get(team) or {}).get("sa_name", "")
                items.append({
                    "team_system_name": team,
                    "stage": stage,
                    "stage_label": STAGE_LABELS[stage],
                    "owner": owner,
                    "planned_start": planned_start,
                    "planned_end": planned_end,
                    "status": "pending",
                    "risk_note": "",
                    "source": "auto",
                })
                prev_end = planned_end
        return {
            "req_id": req_id,
            "deadline": deadline,
            "template_offsets": dict(TEMPLATE_OFFSETS),
            "teams": teams,
            "items": items,
        }

    def save_milestones(
        self, db: Session, req_id: str, payload: SensitiveReqMilestoneSaveRequest
    ) -> Dict[str, Any]:
        """全量覆盖保存里程碑（PUT 语义）。校验阶段枚举与状态域，upsert + 删除缺失行。"""
        req_id = _norm_req_id(req_id)
        ext = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == req_id).first()
        if ext is None:
            raise NotFoundException(f"需求不存在：{req_id}")
        if not ext.version_required_date:
            raise ValidationException("上线要求时间（version_required_date）为空，无法保存倒排")

        seen_keys: set = set()
        for it in payload.items:
            if it.stage not in STAGE_ORDER:
                raise ValidationException(
                    f"非法阶段：{it.stage}（合法值 {'/'.join(STAGE_ORDER)}）"
                )
            team = (it.team_system_name or "").strip()
            if not team:
                raise ValidationException("团队名不能为空")
            key = (team, it.stage)
            if key in seen_keys:
                raise ValidationException(f"里程碑重复：{team}/{it.stage}")
            seen_keys.add(key)
            if it.status and it.status not in status_registry.labels_for(MILESTONE_DOMAIN):
                raise ValidationException(f"未知里程碑状态：{it.status}")
            if it.planned_end and ext.version_required_date and it.planned_end > ext.version_required_date:
                raise ValidationException(
                    f"{team}/{STAGE_LABELS[it.stage]} 计划完成日晚于上线要求日，倒排不允许"
                )

        existing = {m: m for m in self._milestones_of(db, req_id)}
        now = now_cn()
        saved = 0
        for it in payload.items:
            key = ((it.team_system_name or "").strip(), it.stage)
            row = existing.get(key)
            if row is None:
                row = PmwbSensitiveReqMilestone(req_id=req_id, created_at=now)
                db.add(row)
            row.team_system_name, row.stage = key
            row.owner = (it.owner or "").strip() or None
            row.planned_start = it.planned_start
            row.planned_end = it.planned_end
            row.status = it.status or "pending"
            row.risk_note = (it.risk_note or "").strip() or None
            row.source = it.source or "manual"
            row.updated_at = now
            saved += 1

        # 全量覆盖：删除本次未提交的旧行
        for key, row in existing.items():
            if key not in seen_keys:
                db.delete(row)

        db.commit()
        # 保存后重算跟踪态（超期解除等）
        self.sync(db)
        return {"req_id": req_id, "saved": saved}

    def update_milestone(
        self, db: Session, milestone_id: int, payload: SensitiveReqMilestoneUpdateRequest
    ) -> Dict[str, Any]:
        """人工修正单个里程碑（责任人/计划/实际完成/状态/风险）。"""
        ms = db.query(PmwbSensitiveReqMilestone).filter(
            PmwbSensitiveReqMilestone.id == milestone_id
        ).first()
        if ms is None:
            raise NotFoundException(f"里程碑不存在：{milestone_id}")
        now = now_cn()

        if payload.owner is not None:
            ms.owner = payload.owner.strip() or None
        if payload.planned_start is not None:
            ms.planned_start = payload.planned_start or None
        if payload.planned_end is not None:
            ms.planned_end = payload.planned_end or None
        if payload.actual_end is not None:
            ms.actual_end = payload.actual_end or None
        if payload.status is not None:
            target = payload.status.strip()
            if target not in status_registry.labels_for(MILESTONE_DOMAIN):
                raise ValidationException(f"未知里程碑状态：{target}")
            ms.status = target
        if payload.risk_note is not None:
            ms.risk_note = payload.risk_note.strip() or None
        ms.updated_at = now
        db.commit()
        db.refresh(ms)

        # 全部里程碑完成 → 跟踪行自动闭环；有超期未完成 → delayed
        track = db.query(PmwbSensitiveReqTrack).filter(
            PmwbSensitiveReqTrack.req_id == ms.req_id
        ).first()
        auto_status = None
        if track and track.track_status in OPEN_TRACK_STATUSES and track.manual_override != "dismiss":
            siblings = self._milestones_of(db, ms.req_id)
            if siblings and all(m.status == "done" for m in siblings):
                track.track_status = "resolved"
                track.resolved_at = now
                auto_status = "resolved"
            else:
                today = now.date()
                has_overdue = any(
                    m.planned_end and m.planned_end < today and m.status != "done"
                    for m in siblings
                )
                new_status = "delayed" if has_overdue else "active"
                if new_status != track.track_status and track.track_status != "escalated":
                    track.track_status = new_status
                    auto_status = new_status
            track.updated_at = now
            db.commit()

        return {"milestone": self._compose_milestone(ms, None, now.date()), "auto_track_status": auto_status}

    # ------------------------------------------------------------------
    # 跟踪态人工更新
    # ------------------------------------------------------------------
    def update_track(
        self, db: Session, req_id: str, payload: SensitiveReqTrackUpdateRequest
    ) -> Dict[str, Any]:
        row = self._get_track_row(db, req_id)
        now = now_cn()
        if payload.track_status:
            target = payload.track_status.strip()
            if target not in status_registry.labels_for(TRACK_DOMAIN):
                raise ValidationException(
                    f"未知跟踪态：{target}（合法值见 /meta/status-domains 的 {TRACK_DOMAIN}）"
                )
            if target != row.track_status:
                allowed = status_registry.allowed_next(TRACK_DOMAIN, row.track_status)
                if allowed and target not in allowed:
                    cur_def = status_registry.get_status(TRACK_DOMAIN, row.track_status)
                    raise ValidationException(
                        f"「{cur_def.label if cur_def else row.track_status}」不能直接流转到「{target}」"
                    )
            row.track_status = target
            if target == "resolved":
                row.resolved_at = now
            elif target == "dropped":
                row.removed_at = now
                row.is_sensitive = 0
            elif target in OPEN_TRACK_STATUSES:
                row.is_sensitive = 1
        if payload.manual_override is not None:
            ov = payload.manual_override.strip()
            if ov and ov not in OVERRIDES:
                raise ValidationException(f"未知人工覆盖：{ov}（合法值 lock/dismiss）")
            row.manual_override = ov or None
            if ov == "dismiss":
                row.is_sensitive = 0
                row.track_status = "dropped"
                row.removed_at = now
            elif ov == "lock":
                row.is_sensitive = 1
                if row.track_status in CLOSED_TRACK_STATUSES:
                    row.track_status = "active"
                    row.removed_at = None
                    row.resolved_at = None
        row.operator = payload.operator or "pmwb"
        row.updated_at = now
        db.commit()
        db.refresh(row)
        st = status_registry.get_status(TRACK_DOMAIN, row.track_status)
        return {
            "req_id": row.req_id,
            "track_status": row.track_status,
            "track_label": st.label if st else row.track_status,
            "manual_override": row.manual_override,
            "is_sensitive": bool(row.is_sensitive),
        }

    # ------------------------------------------------------------------
    # 邮件督办 / 同步（与 high_level 同构；红线：dry_run 预览，真发须 confirm_send）
    # ------------------------------------------------------------------
    def _structured_tasks(self, db: Session, refs: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """TaskRef（source=sensitive_req, source_id=req_id）→ 邮件清单结构。"""
        out: List[Dict[str, Any]] = []
        for idx, ref in enumerate(refs, 1):
            req_id = _norm_req_id(ref.get("source_id"))
            try:
                # get_detail 返回 dict（已 model_dump(mode="json")），一律用字典访问
                d = self.get_detail(db, req_id)
            except NotFoundException:
                continue
            focus = d.get("focus_milestone")
            owner = (
                (focus.get("owner") if focus else "") or "、".join(
                    o for m in d.get("milestones", []) for o in m.get("owner_list", [])
                )
            ) or "未分配"
            focus_desc = f"{focus['team_system_name']} {focus['stage_label']}" if focus else ""
            out.append({
                "index": idx,
                "title": d.get("req_name") or "",
                "source_label": "敏感需求",
                "source": "sensitive_req",
                "source_id": d.get("req_id"),
                "owner": owner,
                "due_date": (
                    (focus or {}).get("planned_end")
                    or (d.get("version_required_date") or "")
                ),
                "created_at": (d.get("first_seen_at") or "")[:10],
                "status_label": (
                    f"{d.get('track_label', '')}｜{focus['stage_label']}".strip("｜")
                    if focus else (d.get("track_label") or d.get("track_status") or "")
                ),
                "priority": d.get("priority_label") or "",
                "description": (
                    f"上线要求 {d.get('version_required_date') or '未填'}；"
                    f"里程碑 {d.get('milestone_done', 0)}/{d.get('milestone_total', 0)} 完成"
                    + (f"；超期 {d['overdue_count']} 项" if d.get("overdue_count") else "")
                    + (f"；当前卡点：{focus_desc}" if focus_desc else "")
                ),
                "is_overdue": bool(d.get("overdue_count")) or bool(d.get("deadline_missed")),
                "is_due_soon": bool(d.get("due_soon_count")),
                "source_url": d.get("source_url") or "",
            })
        return out

    # 开发已完成的厂家态（urge 督办不再发给这些团队；partial_live 部分上线仍须督办）
    _DEV_DONE_STATUSES = ("completed", "live")

    def _structured_req_blocks(
        self, db: Session, refs: List[Dict[str, str]],
        only_active_teams: bool = False,
    ) -> List[Dict[str, Any]]:
        """督办邮件模板 v2 的需求块装配（2026-10-27）。

        结构 = 需求块（基础信息 7 项）× 团队块（dev_status/处理人/5 阶段里程碑）。
        约束：6 次批量查询 + 内存分组，禁 N+1；单条取数失败跳过该块
        （与 _structured_tasks 现行为一致）；团队骨架 = active_team_systems 唯一源。

        only_active_teams=True（urge 督办口径）：剔除已完成开发的团队
        （vendor_dev.dev_status ∈ completed/live；无 vendor_dev 行则该团队
        里程碑全 done 视为完成）。
        """
        ids: List[str] = []
        for ref in refs:
            rid = _norm_req_id(ref.get("source_id"))
            if rid and rid not in ids:
                ids.append(rid)
        if not ids:
            return []
        today = now_cn().date()

        # ── 批量预载 ──────────────────────────────────────────────
        sent_rows: List[SentEmail] = (
            db.query(SentEmail).filter(SentEmail.req_id.in_(ids)).all()
        )
        sent_map: Dict[str, SentEmail] = {}
        ticket_map: Dict[str, str] = {}
        for s in sorted(sent_rows, key=lambda x: x.id, reverse=True):
            rid = _norm_req_id(s.req_id)
            # 开发单号权威口径（与 requirement.py 回填一致）：id 倒序首个非空
            tno = (s.dev_ticket_no or "").strip()
            if tno and rid not in ticket_map:
                ticket_map[rid] = tno
        for s in sent_rows:
            rid = _norm_req_id(s.req_id)
            cur = sent_map.get(rid)
            # 登记时间口径：同 req_id 多行取最早 created_at（与 _load_name_index 口径对齐）
            if cur is None or (s.created_at and (not cur.created_at or s.created_at < cur.created_at)):
                sent_map[rid] = s
        ext_map = {
            e.req_id: e
            for e in db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id.in_(ids)).all()
        }
        track_map = {
            r.req_id: r
            for r in db.query(PmwbSensitiveReqTrack).filter(PmwbSensitiveReqTrack.req_id.in_(ids)).all()
        }
        slog_by_req: Dict[str, Dict[str, PmwbRequirementStageLog]] = {}
        for lg in db.query(PmwbRequirementStageLog).filter(
            PmwbRequirementStageLog.req_id.in_(ids)
        ).all():
            slog_by_req.setdefault(_norm_req_id(lg.req_id), {})[lg.stage] = lg
        miles_by: Dict[Tuple[str, str], List[PmwbSensitiveReqMilestone]] = {}
        for ms in db.query(PmwbSensitiveReqMilestone).filter(
            PmwbSensitiveReqMilestone.req_id.in_(ids)
        ).order_by(
            PmwbSensitiveReqMilestone.team_system_name, PmwbSensitiveReqMilestone.id
        ).all():
            miles_by.setdefault((ms.req_id, ms.team_system_name), []).append(ms)
        vdev_by: Dict[Tuple[str, str], PmwbReqVendorDev] = {
            (v.req_id, v.system_name): v
            for v in db.query(PmwbReqVendorDev).filter(PmwbReqVendorDev.req_id.in_(ids)).all()
        }
        teams_by = active_team_systems_batch(db, ids)
        names = self._load_name_index(db)

        blocks: List[Dict[str, Any]] = []
        for idx, rid in enumerate(ids, 1):
            ext = ext_map.get(rid)
            track = track_map.get(rid)
            if ext is None or track is None:
                continue  # 无 ext/track 的编号跳过（同 _structured_tasks 降级口径）

            # 事实时间 hints（复用 _stage_log_hints 映射口径，仅批量预载版）
            logs = slog_by_req.get(rid, {})
            hints: Dict[str, Optional[date]] = {
                "evaluate": logs["evaluate"].left_at.date() if (logs.get("evaluate") and logs["evaluate"].left_at) else None,
                "plan": None,
                "test": None,
                "deploy": ext.delivered_date,
            }
            dev_log = logs.get("dev")
            hints["dev"] = dev_log.left_at.date() if (dev_log and dev_log.left_at) else None

            # 团队块（骨架=活跃团队唯一源，历史行不展示）
            team_blocks: List[Dict[str, Any]] = []
            req_recipients: List[str] = []  # 该需求全部环节涉及人（urge 收件人候选）
            for t in teams_by.get(rid, []):
                tname = t["system_name"]
                vd = vdev_by.get((rid, tname))
                dev_status = (vd.dev_status if vd else "") or ""
                vd_status = status_registry.get_status("vendor_dev", dev_status) if dev_status else None
                ms_rows = [
                    self._compose_milestone(ms, hints.get(ms.stage), today)
                    for ms in miles_by.get((rid, tname), [])
                ]
                if only_active_teams:
                    dev_done = (
                        dev_status in self._DEV_DONE_STATUSES
                        or (not vd and ms_rows and all(m["status"] == "done" for m in ms_rows))
                    )
                    if dev_done:
                        continue  # urge 督办只发还未完成开发的团队
                dev_ms_owner = next(
                    (m["owner"] for m in ms_rows if m["stage"] == "dev" and m["owner"]), ""
                )
                owner = (
                    (vd.sa_name if vd and vd.sa_name else "")
                    or (t.get("sa_name") or "")
                    or dev_ms_owner
                    or "未分配"
                )
                for m in ms_rows:
                    for o in str(m["owner"] or "").replace("、", ",").split(","):
                        o = o.strip()
                        if o and o != "未填" and o not in req_recipients:
                            req_recipients.append(o)
                team_blocks.append({
                    "team": tname,
                    "team_name": (vd.team_name if vd else "") or tname,
                    "dev_status": dev_status,
                    "dev_status_label": vd_status.label if vd_status else (dev_status or "—"),
                    "owner": owner,
                    "milestones": [
                        {
                            "stage": m["stage"],
                            "stage_label": m["stage_label"],
                            "owner": m["owner"] or "未填",
                            "planned_start": m["planned_start"].isoformat() if m["planned_start"] else "",
                            "planned_end": m["planned_end"].isoformat() if m["planned_end"] else "",
                            "actual_end": m["actual_end"].isoformat() if m["actual_end"] else "",
                            "actual_display": (
                                m["actual_end"].isoformat()
                                if m["actual_end"]
                                else (m["actual_hint"].isoformat() if m["actual_hint"] else "")
                            ),
                            "status": m["status"],
                            "status_label": m["status_label"],
                            "is_overdue": m["is_overdue"],
                            "overdue_days": m["overdue_days"],
                            "is_due_soon": m["is_due_soon"],
                            "risk_note": m["risk_note"],
                        }
                        for m in ms_rows
                    ],
                    "has_milestones": bool(ms_rows),
                })

            req_overdue = any(t["is_overdue"] for tb in team_blocks for t in tb["milestones"])
            req_due_soon = (
                any(t["is_due_soon"] for tb in team_blocks for t in tb["milestones"])
                and not req_overdue
            )
            ms_total = sum(len(tb["milestones"]) for tb in team_blocks)
            ms_done = sum(
                1 for tb in team_blocks for m in tb["milestones"] if m["status"] == "done"
            )
            deadline_missed = bool(
                ext.version_required_date
                and ext.version_required_date < today
                and ext.status != "closed"
                and track.track_status != "resolved"
            )
            tr_status = status_registry.get_status(TRACK_DOMAIN, track.track_status)
            sent = sent_map.get(rid)
            dev_ticket_no = ticket_map.get(rid) or (sent.dev_ticket_no if sent else "") or ""

            blocks.append({
                "index": idx,
                "req_id": rid,
                "title": ext.req_name or (names.get(rid) or "（无标题）"),
                "dev_ticket_no": dev_ticket_no or "未填写",
                "registered_at": (sent.created_at.strftime("%Y-%m-%d") if (sent and sent.created_at) else "—"),
                "dev_started_at": (
                    dev_log.entered_at.strftime("%Y-%m-%d")
                    if (dev_log and dev_log.entered_at) else "未采集"
                ),
                "due_date": ext.version_required_date.isoformat() if ext.version_required_date else "未填",
                "level": levels.priority_label(ext.priority) if ext.priority else (track.level_code or "—"),
                "status_label": tr_status.label if tr_status else track.track_status,
                "is_overdue": req_overdue or deadline_missed,
                "is_due_soon": req_due_soon,
                "milestone_done": ms_done,
                "milestone_total": ms_total,
                "teams": team_blocks,
                "has_teams": bool(team_blocks),
                "recipients": req_recipients,
            })
        return blocks

    def draft(
        self, db: Session, refs: List[Dict[str, str]], send_type: str,
        body: Optional[str], recipient_name: Optional[str],
    ) -> Dict[str, str]:
        from services.mail_dispatch import format_task_center_subject
        from utils.mail_content import build_mail_body_md

        scene = "sensitive_req_urge" if send_type == "urge" else "sensitive_req_notify"
        is_urge = send_type == "urge"
        tasks = self._structured_tasks(db, refs)
        # urge 督办只发还未完成开发的团队；notify 同步保留全量团队
        req_blocks = self._structured_req_blocks(
            db, refs, only_active_teams=is_urge
        )
        # 收件人候选 = 各需求全部环节涉及人去重（urge 口径下已随团队过滤）
        recipients: List[str] = []
        for b in req_blocks:
            for n in b.get("recipients") or []:
                if n and n not in recipients:
                    recipients.append(n)
        if not recipient_name:
            if len(recipients) > 8:
                recipient_name = "、".join(recipients[:8]) + f"等{len(recipients)}人"
            else:
                recipient_name = "、".join(recipients)
        md = build_mail_body_md(
            scene=scene, fields={"tasks": tasks, "req_blocks": req_blocks}, body_md=body,
            recipient_name=recipient_name or "",
        )
        subject = format_task_center_subject(scene, tasks, recipient_name or "")
        return {
            "body_md": md, "subject": subject, "tasks": tasks,
            "req_blocks": req_blocks, "recipients": recipients,
            "recipient_name": recipient_name or "",
        }

    def send(self, db: Session, obj_in: SensitiveReqSendRequest) -> Dict[str, Any]:
        """发送敏感需求督办/同步邮件（ref_type=sensitive_req）。

        dry_run=True 仅返回装配正文（预览）；真实发信由前端显式 confirm_send=true 触发。
        """
        refs = [{"source": "sensitive_req", "source_id": r.source_id} for r in obj_in.tasks]
        refs = [r for r in refs if r["source_id"]]
        if not refs:
            raise ValidationException("请至少选择一条敏感需求")

        scene = "sensitive_req_urge" if obj_in.send_type == "urge" else "sensitive_req_notify"
        tdata = obj_in.template_data or {}
        tasks = tdata.get("tasks") if isinstance(tdata.get("tasks"), list) else None
        if not tasks:
            tasks = self._structured_tasks(db, refs)
        req_blocks = (
            tdata.get("req_blocks")
            if isinstance(tdata.get("req_blocks"), list)
            else None
        )
        if not req_blocks:
            # tdata 未带（用户未走 draft 直发）时服务端重算，保证预览=实发同源；
            # urge 口径同样只发还未完成开发的团队
            req_blocks = self._structured_req_blocks(
                db, refs, only_active_teams=(obj_in.send_type == "urge")
            )
        # 收件人候选（与 draft 同源）：各需求全部环节涉及人去重
        auto_recipients: List[str] = []
        for b in req_blocks:
            for n in b.get("recipients") or []:
                if n and n not in auto_recipients:
                    auto_recipients.append(n)
        recipient_name = tdata.get("recipient_name") or ""
        if not recipient_name:
            if len(auto_recipients) > 8:
                recipient_name = "、".join(auto_recipients[:8]) + f"等{len(auto_recipients)}人"
            else:
                recipient_name = "、".join(auto_recipients)

        variables: Dict[str, Any] = {
            "tasks": tasks,
            "req_blocks": req_blocks,
            "sendType": tdata.get("sendType") or obj_in.send_type,
            "recipient_name": recipient_name,
            "body": obj_in.body or tdata.get("body") or "",
        }

        mail_fields = {"tasks": tasks, "req_blocks": req_blocks}

        if obj_in.dry_run:
            rendered = _render_mail(
                scene=scene, variables=variables,
                fields=mail_fields,
                subject=obj_in.subject, recipient_name=recipient_name,
            )
            return {"success": True, "preview": True,
                    "body": rendered["rendered_body"], "subject": rendered["subject"]}

        from services.task_center import task_center_service
        # 收件人兜底：前端未传 to 时，自动用全部环节涉及人（姓名串，由
        # _resolve_recipients_for_send 解析成邮箱；解析不出的保持原样并记 unresolved）
        raw_to = obj_in.to or ""
        if not raw_to.strip():
            # 解析器按 , ; ，；空白切分，用逗号拼接
            raw_to = ",".join(auto_recipients)
        resolved_to, unresolved_to = task_center_service._resolve_recipients_for_send(raw_to)
        resolved_cc, unresolved_cc = task_center_service._resolve_recipients_for_send(obj_in.cc or "")
        bad: List[str] = []
        for addr in resolved_to + resolved_cc:
            _, invalid = split_and_validate_emails(addr)
            bad.extend(invalid)
        if bad:
            raise ValidationException(
                "收件人邮箱格式不正确：" + "、".join(bad)
                + "。请填写真实邮箱（可在统一邮件中心通讯录按姓名查询）。"
            )

        ref_key = ";".join(r["source_id"] for r in refs)[:64]
        email_type = ("pmwb_sensitive_req_urge" if obj_in.send_type == "urge"
                      else "pmwb_sensitive_req_notify")

        result = dispatch_email(
            db=db, to=resolved_to, cc=resolved_cc or None,
            subject=obj_in.subject, scene=scene, variables=variables,
            fields=mail_fields,
            raw_content=obj_in.body, recipient_name=recipient_name,
            email_type=email_type, req_id=ref_key,
            req_name=(tasks[0]["title"] if tasks else "敏感需求督办")[:255],
            ref_type=obj_in.ref_type or "sensitive_req",
            ref_id=obj_in.ref_id or ref_key,
            raise_on_error=False, confirm_send=obj_in.confirm_send,
        )
        main_record_id = result.get("record_id")
        record_ids = [main_record_id] if main_record_id else []

        # 逐条落库（同 high_level：单条需求详情页督办历史可查）
        if obj_in.confirm_send and main_record_id and result.get("success"):
            main = db.query(EmailRecord).filter(EmailRecord.id == main_record_id).first()
            if main:
                for r in refs:
                    db.add(EmailRecord(
                        req_id=main.req_id, req_name=main.req_name,
                        email_type=main.email_type, recipient=main.recipient,
                        recipient_name=main.recipient_name, subject=main.subject,
                        content=main.content, send_status=main.send_status,
                        error_msg=main.error_msg, source=main.source, sender=main.sender,
                        ref_type=obj_in.ref_type or "sensitive_req",
                        ref_id=r["source_id"],
                    ))
                db.commit()
            self._bump_urge(db, [r["source_id"] for r in refs], obj_in.operator or "pmwb")

        return {
            "success": result.get("success", False),
            "record_ids": [i for i in record_ids if i],
            "message": result.get("message", ""),
            "unresolved": (unresolved_to or []) + (unresolved_cc or []),
        }

    def _bump_urge(self, db: Session, req_ids: List[str], operator: str) -> None:
        """督办成功回写：跟踪行 urge_count+1；涉及的里程碑行 urge_count+1。"""
        now = now_cn()
        ids = [i for i in {_norm_req_id(r) for r in req_ids} if i]
        if not ids:
            return
        for row in db.query(PmwbSensitiveReqTrack).filter(
            PmwbSensitiveReqTrack.req_id.in_(ids)
        ).all():
            row.urge_count = (row.urge_count or 0) + 1
            row.last_urged_at = now
            row.operator = operator
            row.updated_at = now
            if row.track_status in ("active", "delayed"):
                row.track_status = "escalated"
        for ms in db.query(PmwbSensitiveReqMilestone).filter(
            PmwbSensitiveReqMilestone.req_id.in_(ids)
        ).all():
            ms.urge_count = (ms.urge_count or 0) + 1
            ms.last_urged_at = now
            ms.updated_at = now
        db.commit()


sensitive_req_service = SensitiveReqService()
