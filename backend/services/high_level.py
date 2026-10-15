"""高级别工单服务：自动汇总 + 汇聚跟踪 + 批量邮件督办（任务中心子模块，2026-10-15）。

三条设计铁律（与项目既有约定一致，勿违反）：
  1. **只存跟踪态，不复制工单本体**：pmwb_high_level_track 只记「是否高级别 / 判定来源 /
     人工覆盖 / 跟踪态 / 督办次数 / 首次与最近命中」，工单标题/负责人/截止/状态一律
     实时回读各来源表（复用 services/task_center.py 的 collector），杜绝双真相源。
  2. **状态文案唯一源** = constants/status_registry.py；本模块的跟踪态域 key 为
     `high_level_track`，中文标签/色调/可流转目标全部由注册表派生。
  3. **级别口径唯一源** = constants/levels.py；判定规则只在本文件 HighLevelRuleSet 实现一次。

同步语义：`sync` 为**显式幂等写操作**（前端进入页面触发一次），读接口只读。
采集失败的来源**不参与「源消失」判定**，避免一次抖动把整批工单误标为已移除。
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from constants import levels, status_registry
from core.exceptions import NotFoundException, ValidationException
from db.models import (
    EmailRecord,
    PmwbDevTicket,
    PmwbHighLevelTrack,
    PmwbKeyWork,
    PmwbKeyWorkMemberTask,
    PmwbKeyWorkMilestone,
    PmwbOperationIssue,
    PmwbRequirementExt,
    PmwbResearchIssue,
    now_cn,
)
from schemas.high_level import (
    HighLevelItem,
    HighLevelSendRequest,
    HighLevelTaskQuery,
    HighLevelTrackBatchRequest,
    HighLevelTrackUpdateRequest,
)
from schemas.task_center import SOURCE_LABELS, TaskItem, TaskRef
from services.mail_dispatch import _render_mail, dispatch_email
from services.task_center import task_center_service
from utils.owners import owners_display, owner_set, split_owners
from utils.validators import split_and_validate_emails

logger = logging.getLogger("pmwb.high_level")

# 跟踪态域 key（constants/status_registry.py::_HIGH_LEVEL_TRACK）
TRACK_DOMAIN = "high_level_track"

# 统一态终态：源工单到此即自动闭环，不再作为在池项
TERMINAL_UNIFIED = ("done", "blocked")

# 不进池的来源：需求催办派生自评估环节，无级别、无截止，属「待评估催办」而非高级别工单
EXCLUDED_SOURCES = ("requirement_urge",)

# 「在跟池」跟踪态（列表默认口径）；resolved / dropped 属历史态，需显式 include_closed 才展示
OPEN_TRACK_STATUSES = ("open", "tracking", "escalated")
CLOSED_TRACK_STATUSES = ("resolved", "dropped")

# 人工覆盖合法值
OVERRIDES = ("lock", "escalate", "dismiss")


@dataclass(frozen=True)
class Judgement:
    """单条工单的高级别判定结果。"""

    is_high: bool
    level_code: Optional[str]   # 生效级别码（继承时取母项级别）
    reason: str                 # 判定来源：R1:P0 / R2:overdue:P2:12d / R3:inherit:.. / R4:lock / ""


@dataclass(frozen=True)
class HighLevelRuleSet:
    """高级别判定规则集（唯一实现，禁在前端/别处复制）。

    规则优先级：R4 人工覆盖 > R1 级别直判 > R2 超期升格 > R3 母项继承。
    """

    high_codes: Tuple[str, ...] = levels.HIGH_LEVEL_CODES          # R1：P0/P1
    overdue_upgrade_codes: Tuple[str, ...] = ("P2",)               # R2：仅 P2 升格
    overdue_days_threshold: int = 0                               # R2：超期 >= 阈值（0=超期即升格）
    enable_inherit: bool = True                                    # R3：母项继承

    def judge(
        self,
        item: TaskItem,
        *,
        parent_priority: Optional[str] = None,
        parent_ref: str = "",
        manual_override: Optional[str] = None,
        overdue_days: Optional[int] = None,
    ) -> Judgement:
        code = levels.normalize_priority(item.priority)

        # ── R4 人工覆盖（最高优先，覆盖 R1-R3）────────────────
        if manual_override == "dismiss":
            return Judgement(False, code, "R4:dismiss")
        if manual_override == "lock":
            return Judgement(True, code, "R4:lock")
        if manual_override == "escalate":
            return Judgement(True, code, "R4:escalate")

        # ── R1 级别直判（含需求自由文本「集团需求/紧急需求」）──
        if levels.is_high_level(item.priority):
            tag = code or levels.priority_label(item.priority)
            return Judgement(True, code, f"R1:{tag}")

        # ── R2 超期升格 ──────────────────────────────────────
        if (
            code is not None
            and code in self.overdue_upgrade_codes
            and item.is_overdue
            and (overdue_days is None or overdue_days >= self.overdue_days_threshold)
        ):
            # dev_ticket 的 is_overdue 直接来自库字段，可能缺 due_date → 标 no-due 以示退化
            days = "no-due" if overdue_days is None else f"{overdue_days}d"
            return Judgement(True, code, f"R2:overdue:{code}:{days}")

        # ── R3 母项继承 ──────────────────────────────────────
        if self.enable_inherit and parent_priority and levels.is_high_level(parent_priority):
            pcode = levels.normalize_priority(parent_priority) or levels.priority_label(parent_priority)
            return Judgement(True, pcode, f"R3:inherit:{parent_ref}({pcode})")

        return Judgement(False, code, "")


DEFAULT_RULE_SET = HighLevelRuleSet()


class HighLevelService:
    """高级别工单聚合/跟踪/督办服务。"""

    def __init__(self, rules: HighLevelRuleSet = DEFAULT_RULE_SET):
        self.rules = rules

    # ------------------------------------------------------------------
    # 母项索引（R3 用）：一次性批量预载，避免 N+1
    # ------------------------------------------------------------------
    def _load_parent_index(self, db: Session) -> Dict[Tuple[str, str], Tuple[str, Optional[str]]]:
        """(source, source_id) → (母项标识, 母项级别原值)。"""
        idx: Dict[Tuple[str, str], Tuple[str, Optional[str]]] = {}

        req_prio: Dict[str, Optional[str]] = {
            rid: prio
            for rid, prio in db.query(PmwbRequirementExt.req_id, PmwbRequirementExt.priority).all()
            if rid
        }
        if req_prio:
            for tid, req_id in db.query(PmwbDevTicket.id, PmwbDevTicket.req_id).all():
                if req_id in req_prio:
                    idx[("dev_ticket", str(tid))] = (f"需求{req_id}", req_prio[req_id])
            for iid, req_id in db.query(PmwbOperationIssue.id, PmwbOperationIssue.related_req_id).all():
                if req_id in req_prio:
                    idx[("operation_issue", str(iid))] = (f"需求{req_id}", req_prio[req_id])
            for iid, req_id in db.query(PmwbResearchIssue.id, PmwbResearchIssue.related_req_id).all():
                if req_id in req_prio:
                    idx[("research_issue", str(iid))] = (f"需求{req_id}", req_prio[req_id])

        kw_prio: Dict[int, Optional[str]] = {
            kid: prio for kid, prio in db.query(PmwbKeyWork.id, PmwbKeyWork.priority).all()
        }
        if kw_prio:
            for tid, kid in db.query(
                PmwbKeyWorkMemberTask.id, PmwbKeyWorkMemberTask.key_work_id
            ).all():
                if kid in kw_prio:
                    idx[("key_work", f"task-{tid}")] = (f"重点工作#{kid}", kw_prio[kid])
            for mid, kid in db.query(
                PmwbKeyWorkMilestone.id, PmwbKeyWorkMilestone.key_work_id
            ).all():
                if kid in kw_prio:
                    idx[("key_work", f"milestone-{mid}")] = (f"重点工作#{kid}", kw_prio[kid])

        return idx

    # ------------------------------------------------------------------
    # 同步：全量重算跟踪表（幂等）
    # ------------------------------------------------------------------
    def sync(self, db: Session) -> Dict[str, Any]:
        """采集全部来源 → 判定 → upsert 跟踪表 → 源消失检测。幂等，可重复执行。"""
        started = now_cn()
        today = started.date()

        items, failed = task_center_service.collect_with_report(db)
        failed_set = set(failed)
        parent_idx = self._load_parent_index(db)

        existing: Dict[Tuple[str, str], PmwbHighLevelTrack] = {
            (r.source, r.source_id): r for r in db.query(PmwbHighLevelTrack).all()
        }

        stats: Dict[str, Any] = {
            "scanned": len(items), "high": 0, "added": 0, "updated": 0,
            "removed": 0, "resolved": 0, "restored": 0, "dropped": 0,
            "failed_sources": failed,
        }
        seen: set = set()

        for item in items:
            if item.source in EXCLUDED_SOURCES:
                continue
            key = (item.source, item.source_id)
            seen.add(key)
            row = existing.get(key)
            override = row.manual_override if row else None

            # ── 源工单已达终态：不新建；已有在跟行自动闭环 ──
            if item.status in TERMINAL_UNIFIED:
                if row and row.track_status in OPEN_TRACK_STATUSES and override != "dismiss":
                    row.track_status = "resolved"
                    row.resolved_at = started
                    row.updated_at = started
                    stats["resolved"] += 1
                continue

            parent_ref, parent_prio = parent_idx.get(key, ("", None))
            overdue_days = (
                (today - item.due_date).days if (item.due_date and item.is_overdue) else None
            )
            j = self.rules.judge(
                item,
                parent_priority=parent_prio,
                parent_ref=parent_ref,
                manual_override=override,
                overdue_days=overdue_days,
            )

            if j.is_high:
                stats["high"] += 1
                if row is None:
                    # 新纳入：R2 超期升格首次命中直接标「已升级」，提示需关注
                    db.add(PmwbHighLevelTrack(
                        source=item.source,
                        source_id=item.source_id,
                        is_high=1,
                        judge_reason=j.reason,
                        level_code=j.level_code,
                        manual_override=None,
                        track_status="escalated" if j.reason.startswith("R2:") else "open",
                        urge_count=0,
                        first_seen_at=started,
                        last_seen_at=started,
                        first_overdue_at=today if item.is_overdue else None,
                        created_at=started,
                        updated_at=started,
                    ))
                    stats["added"] += 1
                    continue

                prev_high = bool(row.is_high)
                # 复活：曾被闭环/移出，规则重新命中（人工 dismiss 不复活）
                if override != "dismiss" and row.track_status in CLOSED_TRACK_STATUSES:
                    row.track_status = "tracking"
                    row.resolved_at = None
                    row.removed_at = None
                    stats["restored"] += 1
                # 自动升格打标：由「非高级别 → 高级别(R2)」且尚未督办过
                elif (
                    not prev_high
                    and j.reason.startswith("R2:")
                    and not row.urge_count
                    and row.track_status in OPEN_TRACK_STATUSES
                ):
                    row.track_status = "escalated"

                row.is_high = 1
                row.judge_reason = j.reason
                row.level_code = j.level_code
                row.last_seen_at = started
                row.updated_at = started
                if row.first_overdue_at is None and item.is_overdue:
                    row.first_overdue_at = today
                stats["updated"] += 1
            else:
                # 降级：保留行（不删），is_high 置 0 → 自动退出在跟池
                if row is not None and row.is_high:
                    row.is_high = 0
                    row.judge_reason = j.reason or row.judge_reason
                    row.last_seen_at = started
                    row.updated_at = started
                    stats["dropped"] += 1

        # ── 源消失检测：仅对「本轮采集成功」的来源生效（关键护栏）──
        for key, row in existing.items():
            if key in seen:
                continue
            source = key[0]
            if source in EXCLUDED_SOURCES or source in failed_set:
                continue
            if row.track_status not in OPEN_TRACK_STATUSES:
                continue
            row.track_status = "dropped"
            row.is_high = 0
            row.removed_at = started
            row.updated_at = started
            stats["removed"] += 1

        db.commit()
        logger.info(
            "高级别工单同步完成：采集 %s / 命中 %s / 新增 %s / 刷新 %s / 移除 %s / 闭环 %s / 失败源 %s",
            stats["scanned"], stats["high"], stats["added"], stats["updated"],
            stats["removed"], stats["resolved"], stats["failed_sources"],
        )
        return stats

    # ------------------------------------------------------------------
    # 查询：读跟踪表 + 实时回读源
    # ------------------------------------------------------------------
    def _compose_item(self, row: PmwbHighLevelTrack, src: Optional[TaskItem]) -> HighLevelItem:
        """跟踪态行 + 源工单快照 → 统一条目。源已删除时降级展示。"""
        st = status_registry.get_status(TRACK_DOMAIN, row.track_status)
        base = dict(
            task_id=f"{row.source}:{row.source_id}",
            source=row.source,
            source_id=row.source_id,
            level_code=row.level_code,
            judge_reason=row.judge_reason or "",
            is_high=bool(row.is_high),
            track_status=row.track_status,
            track_label=st.label if st else row.track_status,
            track_tone=st.tone if st else "info",
            manual_override=row.manual_override,
            urge_count=row.urge_count or 0,
            last_urged_at=row.last_urged_at,
            first_seen_at=row.first_seen_at,
            last_seen_at=row.last_seen_at,
            first_overdue_at=row.first_overdue_at,
        )
        if src is None:
            return HighLevelItem(
                source_label=row.source,
                title="（源工单已删除）",
                source_gone=True,
                **base,
            )
        return HighLevelItem(
            source_label=src.source_label,
            title=src.title,
            status=src.status,
            status_label=src.status_label,
            raw_status=src.raw_status,
            owner=src.owner or "",
            owner_display=owners_display(src.owner),
            priority=src.priority,
            priority_label=levels.priority_label(src.priority),
            due_date=src.due_date,
            created_at=src.created_at,
            is_overdue=bool(src.is_overdue),
            is_due_soon=bool(src.is_due_soon),
            source_url=src.source_url,
            detail=dict(src.detail or {}),
            **base,
        )

    def _load_pool(self, db: Session) -> List[HighLevelItem]:
        """加载全部跟踪行并合成（不筛选、不分页），供列表与统计共用。"""
        rows = db.query(PmwbHighLevelTrack).all()
        if not rows:
            return []
        items, _ = task_center_service.collect_with_report(db)
        index = {t.task_id: t for t in items}
        return [self._compose_item(r, index.get(f"{r.source}:{r.source_id}")) for r in rows]

    @staticmethod
    def _sort_key(it: HighLevelItem) -> Tuple:
        """排序：级别高者优先 → 超期优先 → 截止日期早者优先 → 督办次数少者优先。"""
        return (
            levels.level_rank(it.priority if it.level_code is None else it.level_code),
            0 if it.is_overdue else 1,
            it.due_date or date.max,
            it.urge_count,
        )

    def list_tasks(self, db: Session, query: HighLevelTaskQuery) -> Dict[str, Any]:
        """高级别工单列表（跟踪态/来源/级别/责任人/关键字/超期筛选 + 分页）。"""
        pool = self._load_pool(db)

        # 跟踪态口径：默认仅「在跟池」；显式 track_status 或 include_closed 时放开
        if query.track_status:
            pool = [it for it in pool if it.track_status == query.track_status]
        elif not query.include_closed:
            pool = [it for it in pool if it.track_status in OPEN_TRACK_STATUSES]

        if query.source:
            pool = [it for it in pool if it.source == query.source]
        if query.status:
            pool = [it for it in pool if it.status == query.status]
        if query.level:
            lv = query.level.strip().upper()
            pool = [it for it in pool if (it.level_code or "").upper() == lv]
        if query.owner:
            wanted = {o.strip() for o in str(query.owner).split(",") if o.strip()}
            if wanted:
                pool = [it for it in pool if owner_set(it.owner) & wanted]
        if query.only_overdue:
            pool = [it for it in pool if it.is_overdue]
        if query.keyword:
            kw = query.keyword.strip().lower()
            pool = [
                it for it in pool
                if kw in (it.title or "").lower()
                or kw in (it.owner or "").lower()
                or kw in str(it.detail or {}).lower()
            ]

        pool.sort(key=self._sort_key)
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
                "overdue": sum(1 for it in pool if it.is_overdue),
                "escalated": sum(1 for it in pool if it.track_status == "escalated"),
                "unassigned": sum(1 for it in pool if not split_owners(it.owner)),
            },
        }

    def get_stats(self, db: Session) -> Dict[str, Any]:
        """在跟池统计：来源 / 级别 / 跟踪态 / 超期 / 已升级 / 未分配责任人 / 责任人分布。

        责任人分布（by_handler）是「按责任人批量督办」的单一数据源，前端 chips 直接消费，
        禁止前端再拉全量列表自己算（沿用运营监控 by-handler 口径）。
        """
        pool = [it for it in self._load_pool(db) if it.track_status in OPEN_TRACK_STATUSES]

        by_source: Dict[str, int] = {}
        by_level: Dict[str, int] = {}
        by_track: Dict[str, int] = {}
        by_handler: Dict[str, int] = {}
        unassigned = 0
        for it in pool:
            by_source[it.source] = by_source.get(it.source, 0) + 1
            by_level[it.level_code or "—"] = by_level.get(it.level_code or "—", 0) + 1
            by_track[it.track_status] = by_track.get(it.track_status, 0) + 1
            names = split_owners(it.owner)
            if not names:
                unassigned += 1
                continue
            for n in names:
                by_handler[n] = by_handler.get(n, 0) + 1

        handlers = [
            {"name": n, "count": c}
            for n, c in sorted(by_handler.items(), key=lambda kv: (-kv[1], kv[0]))
        ]

        return {
            "total": len(pool),
            "overdue": sum(1 for it in pool if it.is_overdue),
            "escalated": sum(1 for it in pool if it.track_status == "escalated"),
            "unassigned": unassigned,
            "by_source": by_source,
            "by_source_label": {k: SOURCE_LABELS.get(k, k) for k in by_source},
            "by_level": by_level,
            "by_level_label": {k: levels.priority_label(k) for k in by_level},
            "by_track_status": by_track,
            "by_handler": handlers,
        }

    # ------------------------------------------------------------------
    # 跟踪态人工更新
    # ------------------------------------------------------------------
    def _get_row(self, db: Session, source: str, source_id: str) -> PmwbHighLevelTrack:
        row = (
            db.query(PmwbHighLevelTrack)
            .filter(
                PmwbHighLevelTrack.source == source,
                PmwbHighLevelTrack.source_id == source_id,
            )
            .first()
        )
        if row is None:
            raise NotFoundException(f"跟踪记录不存在：{source}:{source_id}")
        return row

    def update_track(
        self, db: Session, source: str, source_id: str, payload: HighLevelTrackUpdateRequest
    ) -> Dict[str, Any]:
        """人工更新跟踪态 / 人工覆盖（lock / escalate / dismiss）。"""
        row = self._get_row(db, source, source_id)
        now = now_cn()

        if payload.track_status:
            target = payload.track_status.strip()
            if target not in status_registry.labels_for(TRACK_DOMAIN):
                raise ValidationException(
                    f"未知跟踪态：{target}（合法值见 /meta/status-domains 的 {TRACK_DOMAIN}）"
                )
            cur = row.track_status
            if target != cur:
                allowed = status_registry.allowed_next(TRACK_DOMAIN, cur)
                if allowed and target not in allowed:
                    cur_def = status_registry.get_status(TRACK_DOMAIN, cur)
                    raise ValidationException(
                        f"「{cur_def.label if cur_def else cur}」不能直接流转到「{target}」"
                    )
            row.track_status = target
            if target == "resolved":
                row.resolved_at = now
            elif target == "dropped":
                row.removed_at = now

        if payload.manual_override is not None:
            ov = payload.manual_override.strip()
            if ov and ov not in OVERRIDES:
                raise ValidationException(f"未知人工覆盖：{ov}（合法值 lock/escalate/dismiss）")
            row.manual_override = ov or None
            if ov == "dismiss":
                # 强制移出：即使 P0 也不再进池，且自动规则不得复活
                row.is_high = 0
                row.track_status = "dropped"
                row.removed_at = now
            elif ov in ("lock", "escalate"):
                row.is_high = 1
                if row.track_status in CLOSED_TRACK_STATUSES:
                    row.track_status = "open"
                    row.removed_at = None
                    row.resolved_at = None

        row.operator = payload.operator or "pmwb"
        row.updated_at = now
        db.commit()
        db.refresh(row)
        return {
            "source": row.source,
            "source_id": row.source_id,
            "track_status": row.track_status,
            "track_label": (
                status_registry.get_status(TRACK_DOMAIN, row.track_status).label
                if status_registry.get_status(TRACK_DOMAIN, row.track_status) else row.track_status
            ),
            "manual_override": row.manual_override,
            "is_high": bool(row.is_high),
        }

    def batch_update_track(self, db: Session, payload: HighLevelTrackBatchRequest) -> Dict[str, Any]:
        """批量更新跟踪态；逐项容错，失败项回报原因（不中断整批）。"""
        updated = 0
        errors: List[Dict[str, Any]] = []
        for it in payload.items:
            try:
                self.update_track(
                    db,
                    it.source,
                    it.source_id,
                    HighLevelTrackUpdateRequest(
                        track_status=it.track_status,
                        manual_override=it.manual_override,
                        operator=it.operator or "pmwb",
                    ),
                )
                updated += 1
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                errors.append({
                    "source": it.source,
                    "source_id": it.source_id,
                    "reason": getattr(exc, "message", None) or str(exc),
                })
        return {"requested": len(payload.items), "updated": updated, "errors": errors}

    # ------------------------------------------------------------------
    # 邮件督办 / 同步
    # ------------------------------------------------------------------
    def draft(self, db: Session, tasks: List[Dict[str, Any]], send_type: str,
              body: Optional[str], recipient_name: Optional[str]) -> Dict[str, str]:
        """生成邮件 Markdown 草稿（主题 + 正文），供前端左侧编辑区默认值。"""
        from services.mail_dispatch import format_task_center_subject
        from utils.mail_content import build_mail_body_md

        scene = "high_level_urge" if send_type == "urge" else "high_level_notify"
        md = build_mail_body_md(
            scene=scene,
            fields={"tasks": tasks},
            body_md=body,
            recipient_name=recipient_name or "",
        )
        subject = format_task_center_subject(scene, tasks, recipient_name or "")
        return {"body_md": md, "subject": subject}

    def send(self, db: Session, obj_in: HighLevelSendRequest) -> Dict[str, Any]:
        """发送高级别工单督办/同步邮件并落 email_records（ref_type=high_level）。

        dry_run=True 仅返回装配正文（预览），不校验收件人、不发送、不落库；
        真实发信由前端显式带 confirm_send=true 触发（后端另有 MAIL_DRY_RUN 兜底）。
        """
        if not obj_in.tasks:
            raise ValidationException("请至少选择一条工单")

        scene = "high_level_urge" if obj_in.send_type == "urge" else "high_level_notify"
        tdata = obj_in.template_data or {}
        tdata_tasks = tdata.get("tasks") if isinstance(tdata.get("tasks"), list) else None
        if not tdata_tasks:
            tdata_tasks = task_center_service._build_structured_tasks(db, obj_in.tasks)

        recipient_name = tdata.get("recipient_name") or task_center_service._aggregate_owners(tdata_tasks)

        variables: Dict[str, Any] = {
            "tasks": tdata_tasks,
            "sendType": tdata.get("sendType") or obj_in.send_type,
            "recipient_name": recipient_name,
            "body": obj_in.body or tdata.get("body") or "",
        }

        if obj_in.dry_run:
            rendered = _render_mail(
                scene=scene,
                variables=variables,
                fields={"tasks": tdata_tasks} if tdata_tasks else None,
                subject=obj_in.subject,
                recipient_name=recipient_name,
            )
            return {
                "success": True,
                "preview": True,
                "body": rendered["rendered_body"],
                "subject": rendered["subject"],
            }

        resolved_to, unresolved_to = task_center_service._resolve_recipients_for_send(obj_in.to or "")
        resolved_cc, unresolved_cc = task_center_service._resolve_recipients_for_send(obj_in.cc or "")

        bad: List[str] = []
        for addr in resolved_to:
            _, invalid = split_and_validate_emails(addr)
            bad.extend(invalid)
        for addr in resolved_cc:
            _, invalid = split_and_validate_emails(addr)
            bad.extend(invalid)
        if bad:
            raise ValidationException(
                "收件人邮箱格式不正确：" + "、".join(bad)
                + "。请填写真实邮箱（可在统一邮件中心通讯录按姓名查询）。"
            )

        first_title = ""
        for ref in obj_in.tasks:
            item = task_center_service.get_detail(db, f"{ref.source}:{ref.source_id}")
            if item and not first_title:
                first_title = item.title
                break

        email_type = "pmwb_high_level_urge" if obj_in.send_type == "urge" else "pmwb_high_level_notify"
        ref_key = ";".join(f"{t.source}:{t.source_id}" for t in obj_in.tasks)[:64]

        result = dispatch_email(
            db=db,
            to=resolved_to,
            cc=resolved_cc or None,
            subject=obj_in.subject,
            scene=scene,
            variables=variables,
            fields={"tasks": tdata_tasks} if tdata_tasks else None,
            raw_content=obj_in.body,
            recipient_name=recipient_name,
            email_type=email_type,
            req_id=ref_key,
            req_name=(first_title or "高级别工单邮件")[:255],
            ref_type=obj_in.ref_type or "high_level",
            ref_id=obj_in.ref_id or ref_key,
            raise_on_error=False,
            confirm_send=obj_in.confirm_send,
        )
        main_record_id = result.get("record_id")
        record_ids = [main_record_id] if main_record_id else []

        # 逐条落库：一封邮件涵盖多条工单时，为每条各记一条记录，
        # 使单条工单详情页的督办历史（EmailSuperviseLog）可查到本次督办。
        # 仅真实发信成功时复制，避免污染 dry_run 验证记录。
        if obj_in.confirm_send and main_record_id and result.get("success"):
            main = db.query(EmailRecord).filter(EmailRecord.id == main_record_id).first()
            if main:
                recs: List[EmailRecord] = []
                for ref in obj_in.tasks:
                    rec = EmailRecord(
                        req_id=main.req_id,
                        req_name=main.req_name,
                        email_type=main.email_type,
                        recipient=main.recipient,
                        recipient_name=main.recipient_name,
                        subject=main.subject,
                        content=main.content,
                        send_status=main.send_status,
                        error_msg=main.error_msg,
                        source=main.source,
                        sender=main.sender,
                        ref_type=obj_in.ref_type or "high_level",
                        ref_id=f"{ref.source}:{ref.source_id}",
                    )
                    db.add(rec)
                    recs.append(rec)
                db.flush()   # 拿自增 id 后再提交
                for rec in recs:
                    record_ids.append(rec.id)
                db.commit()

            # 督办计数回写（仅成功时；失败/部分失败不回写）
            self._bump_urge(db, obj_in.tasks, obj_in.operator or "pmwb")

        return {
            "success": result.get("success", False),
            "record_ids": [i for i in record_ids if i],
            "message": result.get("message", ""),
            "unresolved": (unresolved_to or []) + (unresolved_cc or []),
        }

    def _bump_urge(self, db: Session, refs: List[TaskRef], operator: str) -> None:
        """对本次邮件涉及的唯一 (source, source_id) 集合累加督办次数。"""
        now = now_cn()
        keys = {(r.source, r.source_id) for r in refs}
        if not keys:
            return
        rows = db.query(PmwbHighLevelTrack).filter(
            PmwbHighLevelTrack.source.in_({k[0] for k in keys})
        ).all()
        hit = 0
        for row in rows:
            if (row.source, row.source_id) not in keys:
                continue
            row.urge_count = (row.urge_count or 0) + 1
            row.last_urged_at = now
            row.operator = operator
            row.updated_at = now
            hit += 1
        if hit:
            db.commit()


high_level_service = HighLevelService()
