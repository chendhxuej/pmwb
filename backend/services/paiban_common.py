"""排版管理共用口径工具（pb-2 ~ pb-8 唯一实现，禁止在子服务里复制公式）。

职责：JSON 存取、主行/版本定位、派生截止与临期/超期/停滞计算、参与记录、
流转留痕、主行序列化。四环节偏移与准入时点只从 constants/paiban.py 派生。

⚠ 本文件不写源需求 / 源工单、不发邮件、不判定风险（风险由 paiban_risk 负责）。
"""

import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from constants import paiban as C
from core.exceptions import NotFoundException, ValidationException
from db.models import (
    PmwbPbFeedback,
    PmwbPbParticipation,
    PmwbPbRisk,
    PmwbPbStageLog,
    PmwbPbSuperviseItem,
    PmwbPbTrack,
    PmwbPbTrackTeam,
    PmwbPbVersionPlan,
    now_cn,
)
from services import paiban_version as VS

STAGE_KEYS = [k for k, _ in C.STAGES]
STAGE_INDEX = {k: i for i, k in enumerate(STAGE_KEYS)}


def jdump(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, default=str)


def jload(v: Any, default: Any = None) -> Any:
    if not v:
        return default if default is not None else []
    if isinstance(v, (list, dict)):
        return v
    try:
        return json.loads(v)
    except (ValueError, TypeError):
        return default if default is not None else []


def iso(v: Any) -> str:
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return str(v)[:10] if v else ""


def dt_iso(v: Any) -> str:
    return v.isoformat(sep=" ", timespec="seconds") if isinstance(v, datetime) else ""


def today() -> date:
    return now_cn().date()


def track_or_404(db: Session, track_id: int) -> PmwbPbTrack:
    t = db.query(PmwbPbTrack).filter(PmwbPbTrack.id == track_id).first()
    if t is None:
        raise NotFoundException(f"跟踪主行 {track_id} 不存在")
    return t


def teams_of(db: Session, track_id: int, include_inactive: bool = True) -> List[PmwbPbTrackTeam]:
    q = db.query(PmwbPbTrackTeam).filter(PmwbPbTrackTeam.track_id == track_id)
    return q.order_by(PmwbPbTrackTeam.team_name).all()


def plan_of(db: Session, track: PmwbPbTrack) -> Optional[PmwbPbVersionPlan]:
    if not track.current_plan_id:
        return None
    return db.query(PmwbPbVersionPlan).filter(
        PmwbPbVersionPlan.id == track.current_plan_id
    ).first()


def plan_payload(db: Session, track: PmwbPbTrack) -> Dict[str, Any]:
    """派生截止/准入时点一律查询期算，不落副本（默认计划改期自动重算）。"""
    plan = plan_of(db, track)
    return VS.serialize_plan(plan) if plan else {}


def stage_deadline(plan_payload_dict: Dict[str, Any], stage: str) -> str:
    for s in (plan_payload_dict or {}).get("deadlines", {}).get("stages", []):
        if s.get("key") == stage:
            return s.get("deadline", "")
    return ""


def stage_metrics(db: Session, track: PmwbPbTrack) -> Dict[str, Any]:
    """临期 ≤3 天 / 超期 / 停滞 ≥7 天，唯一实现；同时供督办规则与概览使用。"""
    p = plan_payload(db, track)
    deadline = stage_deadline(p, track.stage)
    d = date.fromisoformat(deadline) if deadline else None
    t = today()
    days_left = (d - t).days if d else None
    entered = track.stage_entered_at.date() if isinstance(track.stage_entered_at, datetime) else t
    stalled_days = (t - entered).days
    return {
        "deadline": deadline,
        "days_left": days_left,
        "overdue": bool(d and days_left is not None and days_left < 0),
        "near_due": bool(d and days_left is not None and 0 <= days_left <= C.NEAR_DUE_DAYS),
        "stalled": stalled_days >= C.STALL_DAYS,
        "stalled_days": stalled_days,
        "admit_gate_at": p.get("admit_gate_at", ""),
        "release_date": p.get("release_date", ""),
        "plan_no": p.get("version_no", ""),
        "plan_source": track.plan_source,
    }


def ensure_participation(db: Session, track: PmwbPbTrack, plan: Optional[PmwbPbVersionPlan],
                         admit_status: Optional[str] = None) -> Optional[PmwbPbParticipation]:
    """主行 × 版本参与记录：按计划上线率的唯一分母来源，幂等不重复计数。"""
    if plan is None:
        return None
    row = db.query(PmwbPbParticipation).filter(
        PmwbPbParticipation.track_id == track.id,
        PmwbPbParticipation.plan_id == plan.id,
    ).first()
    if row is None:
        row = PmwbPbParticipation(
            track_id=track.id, plan_id=plan.id, version_no=plan.version_no,
            joined_at=now_cn(), outcome="in_progress",
        )
        db.add(row)
        db.flush()  # autoflush=False 的测试/批量场景必须立即落主键，防同锚重复行
    row.version_no = plan.version_no
    if admit_status is not None:
        row.admit_status = admit_status
    row.is_exception = int(track.exception_flag or 0)
    row.freeze_late = int(track.freeze_late or 0)
    return row


def close_participation(db: Session, track: PmwbPbTrack, plan_id: Optional[int],
                        result: str, outcome: str = "not_achieved") -> None:
    if not plan_id:
        return
    row = db.query(PmwbPbParticipation).filter(
        PmwbPbParticipation.track_id == track.id,
        PmwbPbParticipation.plan_id == plan_id,
    ).first()
    if row is None:
        return
    row.left_at = now_cn()
    row.result = result
    row.result_date = track.result_date
    row.outcome = outcome
    row.admit_status = track.admit_status


def add_stage_log(db: Session, track: PmwbPbTrack, to_stage: str, *,
                  from_stage: str = "", team_id: Optional[int] = None,
                  is_rollback: bool = False, reason: str = "", source: str = "page",
                  operator: str = "", feedback_id: Optional[int] = None,
                  risk_id: Optional[int] = None, batch_no: str = "",
                  before_value: Any = None, after_value: Any = None,
                  new_deadline: str = "") -> PmwbPbStageLog:
    rollback_count = 0
    if is_rollback:
        rollback_count = 1 + db.query(PmwbPbStageLog).filter(
            PmwbPbStageLog.track_id == track.id,
            PmwbPbStageLog.is_rollback == 1,
        ).count()
    row = PmwbPbStageLog(
        track_id=track.id, team_id=team_id, from_stage=from_stage, to_stage=to_stage,
        is_rollback=int(is_rollback), rollback_count=rollback_count, reason=reason,
        source=source, operator=operator, feedback_id=feedback_id, risk_id=risk_id,
        batch_no=batch_no, before_value=jdump(before_value) if before_value is not None else None,
        after_value=jdump(after_value) if after_value is not None else None,
        new_deadline=new_deadline, changed_at=now_cn(),
    )
    db.add(row)
    return row


def recompute_counters(db: Session, track: PmwbPbTrack) -> None:
    """重点 / 异常标记唯一实现；顺延≥2 或失败≥1 重点，顺延≥3 异常。"""
    track.focus_flag = int((track.defer_count or 0) >= C.DEFERRAL_FOCUS_MIN
                           or (track.fail_count or 0) >= 1)
    track.abnormal_flag = int((track.defer_count or 0) >= C.DEFERRAL_ABNORMAL_MIN)
    track.pending_feedback = db.query(PmwbPbFeedback).filter(
        PmwbPbFeedback.track_id == track.id,
        PmwbPbFeedback.adopt_status.in_(("pending", "conflict", "parse_failed")),
        PmwbPbFeedback.rolled_back == 0,
    ).count()


def track_where(db: Session, plan_id: Optional[int] = None, *, active_only: bool = True,
                ticket_type: str = "", stage: str = "", admit_status: str = ""):
    """概览 / 列表 / 下钻 / 导出共用同一口径：展示字段=排序字段=下钻字段=同一版本。"""
    q = db.query(PmwbPbTrack)
    if active_only:
        q = q.filter(PmwbPbTrack.active == 1)
    if plan_id:
        # 当前归属版本 + 曾参与该版本（顺延离开的仍计入原版未达成）
        ids = [r.track_id for r in db.query(PmwbPbParticipation).filter(
            PmwbPbParticipation.plan_id == plan_id
        ).all()]
        q = q.filter(PmwbPbTrack.id.in_(ids) if ids else PmwbPbTrack.current_plan_id == plan_id)
    if ticket_type:
        q = q.filter(PmwbPbTrack.ticket_type == ticket_type)
    if stage:
        q = q.filter(PmwbPbTrack.stage == stage)
    if admit_status:
        q = q.filter(PmwbPbTrack.admit_status == admit_status)
    return q


def serialize_track(db: Session, t: PmwbPbTrack) -> Dict[str, Any]:
    """跟踪行展示：口径全部后端一次返回，前端不推导簇数/分母。"""
    p = plan_payload(db, t)
    m = stage_metrics(db, t)
    teams = teams_of(db, t.id)
    blocking = db.query(PmwbPbRisk).filter(
        PmwbPbRisk.track_id == t.id, PmwbPbRisk.affect_release == 1,
        PmwbPbRisk.status == "open",
    ).count()
    return {
        "id": t.id, "ticket_type": t.ticket_type,
        "ticket_type_label": dict(C.TICKET_TYPES).get(t.ticket_type, t.ticket_type),
        "ticket_no": t.ticket_no, "title": t.title, "system_name": t.system_name,
        "priority": t.priority, "owner": t.owner,
        "expected_date": iso(t.expected_date),
        "current_plan_id": t.current_plan_id, "plan_source": t.plan_source,
        "plan_source_label": {"exclusive": "专属", "default": "统一默认", "missing": "待补版本计划"}.get(t.plan_source, t.plan_source),
        "plan": p, "stage": t.stage,
        "stage_label": C.STAGE_LABELS.get(t.stage, t.stage),
        "stage_entered_at": dt_iso(t.stage_entered_at),
        "wait_release_at": dt_iso(t.wait_release_at),
        "admit_status": t.admit_status,
        "admit_status_label": dict(C.ADMIT_STATUSES).get(t.admit_status, t.admit_status),
        "exception_flag": int(t.exception_flag or 0),
        "exception_reason": t.exception_reason, "exception_operator": t.exception_operator,
        "exception_at": dt_iso(t.exception_at), "exception_fact": jload(t.exception_fact, {}),
        "result": t.result, "result_label": dict(C.RESULTS).get(t.result, t.result),
        "result_date": iso(t.result_date), "result_reason": t.result_reason,
        "defer_count": t.defer_count or 0, "fail_count": t.fail_count or 0,
        "plan_chain": jload(t.plan_chain, []), "last_defer_reason": t.last_defer_reason,
        "focus_flag": int(t.focus_flag or 0), "abnormal_flag": int(t.abnormal_flag or 0),
        "freeze_late": int(t.freeze_late or 0), "source_conflict": int(t.source_conflict or 0),
        "include_source": t.include_source, "included_at": dt_iso(t.included_at),
        "included_by": t.included_by, "active": int(t.active or 0),
        "supervise_count": t.supervise_count or 0,
        "last_supervise_at": dt_iso(t.last_supervise_at),
        "pending_receipt_batch": t.pending_receipt_batch,
        "feedback_count": t.feedback_count or 0,
        "last_feedback_at": dt_iso(t.last_feedback_at),
        "pending_feedback": t.pending_feedback or 0,
        "blocking_risk_count": blocking,
        "metrics": m,
        "team_count": len(teams),
        "teams": [{
            "id": x.id, "team_name": x.team_name, "owner": x.owner,
            "stage": x.stage, "stage_label": C.STAGE_LABELS.get(x.stage, x.stage),
            "done": int(x.done or 0), "parse_status": x.parse_status,
            "recipient_status": x.recipient_status,
            "last_feedback_at": dt_iso(x.last_feedback_at),
        } for x in teams],
    }


def validate_transition(from_stage: str, to_stage: str) -> bool:
    """正向逐级不可跳级；回退允许跨级但必填原因（原因校验在调用方）。"""
    if to_stage not in STAGE_INDEX or from_stage not in STAGE_INDEX:
        raise ValidationException("环节值不在四环节闭集内")
    return STAGE_INDEX[to_stage] >= STAGE_INDEX[from_stage]
