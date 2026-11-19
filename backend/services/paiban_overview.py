"""版本概览与口径（pb-8 / L7）—— 展示字段 = 排序字段 = 下钻字段 = 同一版本。

- 分母一律后端一次返回，前端只展示不推导；
- 版本统计按主行，团队视图按团队子行，两处**不可加总**；
- 按计划上线率分子排除「人工例外 / 冻结后纳入」，单列清单防特例美化指标；
- 顺延来的工单计入原版未达成 + 新版在跟，全局在跟数按主行去重。
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from constants import paiban as C
from core.exceptions import ValidationException
from db.models import (
    PmwbPbFeedback, PmwbPbParticipation, PmwbPbRisk, PmwbPbSuperviseBatch,
    PmwbPbSuperviseItem, PmwbPbTrack, PmwbPbTrackTeam, PmwbPbVersionPlan,
)
from services import paiban_common as K
from services import paiban_risk as RS
from services import paiban_version as VS

SCOPE_NOTE = "版本统计按主行、团队视图按团队子行，两处不可加总"


def _plan(db: Session, plan_id: int) -> PmwbPbVersionPlan:
    p = db.query(PmwbPbVersionPlan).filter_by(id=plan_id).first()
    if p is None:
        raise ValidationException(f"版本计划 {plan_id} 不存在")
    return p


def overview(db: Session, plan_id: int) -> Dict[str, Any]:
    plan = _plan(db, plan_id)
    parts = db.query(PmwbPbParticipation).filter(
        PmwbPbParticipation.plan_id == plan_id).all()
    ids = [x.track_id for x in parts]
    tracks = db.query(PmwbPbTrack).filter(PmwbPbTrack.id.in_(ids)).all() if ids else []
    by_id = {t.id: t for t in tracks}
    main_count = len([t for t in tracks if int(t.active or 0) == 1])

    def cnt(fn) -> int:
        return sum(1 for t in tracks if int(t.active or 0) == 1 and fn(t))

    stage_counts = [{"key": k, "label": v,
                     "count": cnt(lambda t, k=k: t.stage == k)} for k, v in C.STAGES]
    admit_counts = [{"key": k, "label": v,
                     "count": cnt(lambda t, k=k: t.admit_status == k)}
                    for k, v in C.ADMIT_STATUSES]
    result_counts = [{"key": k, "label": v or "未出结果",
                      "count": cnt(lambda t, k=k: (t.result or "") == k)}
                     for k, v in C.RESULTS]

    decided = [p for p in parts if p.left_at or p.result or p.outcome != "in_progress"]
    achieved = [p for p in decided if p.outcome == "achieved"]
    planned_hits = [p for p in achieved
                    if not int(p.is_exception or 0) and not int(p.freeze_late or 0)]
    deferred_in = cnt(lambda t: bool(K.jload(t.plan_chain, []))
                      and (K.jload(t.plan_chain, []) or [])[-1].get("plan_id") == plan_id)

    risks = db.query(PmwbPbRisk).filter(PmwbPbRisk.plan_id == plan_id,
                                        PmwbPbRisk.status == "open").all()
    blocks = [r for r in risks if int(r.affect_release or 0) == 1]
    batches = db.query(PmwbPbSuperviseBatch).filter_by(plan_id=plan_id).all()
    batch_ids = [b.id for b in batches]
    items = db.query(PmwbPbSuperviseItem).filter(
        PmwbPbSuperviseItem.batch_id.in_(batch_ids)).all() if batch_ids else []
    real = [x for x in items if x.send_status in ("sent", "dry_run")]
    replied = [x for x in real if x.receipt_status == "received"]
    fb_pending = db.query(PmwbPbFeedback).filter(
        PmwbPbFeedback.track_id.in_(ids) if ids else PmwbPbFeedback.id == -1,
        PmwbPbFeedback.adopt_status.in_(("pending", "conflict", "parse_failed")),
        PmwbPbFeedback.rolled_back == 0,
    ).count()

    focus = [K.serialize_track(db, t) for t in tracks
             if int(t.active or 0) == 1 and int(t.focus_flag or 0) == 1]
    abnormal = [K.serialize_track(db, t) for t in tracks
                if int(t.active or 0) == 1 and int(t.abnormal_flag or 0) == 1]
    exception = [K.serialize_track(db, t) for t in tracks
                 if int(t.active or 0) == 1 and int(t.exception_flag or 0) == 1]
    freeze_late = [K.serialize_track(db, t) for t in tracks
                   if int(t.active or 0) == 1 and int(t.freeze_late or 0) == 1]
    missing_plan = [K.serialize_track(db, t) for t in db.query(PmwbPbTrack).filter(
        PmwbPbTrack.active == 1, PmwbPbTrack.current_plan_id.is_(None)
    ).all()]

    def brief(x):
        return {"track_id": x["id"], "ticket_no": x["ticket_no"], "title": x["title"],
                "stage": x["stage"], "admit_status": x["admit_status"],
                "defer_count": x["defer_count"], "plan_source": x["plan_source"]}

    return {
        "plan": VS.serialize_plan(plan),
        "main_row_count": main_count,
        "team_row_count": db.query(PmwbPbTrackTeam).filter(
            PmwbPbTrackTeam.track_id.in_(ids)).count() if ids else 0,
        "stage_counts": stage_counts, "admit_counts": admit_counts,
        "result_counts": result_counts,
        "kpi": {
            "should_go_live": main_count,
            "admitted": cnt(lambda t: t.admit_status == "admitted"),
            "pending": cnt(lambda t: t.admit_status == "pending"),
            "not_admitted": cnt(lambda t: t.admit_status == "not_admitted"),
            "exception": len(exception),
            "live": cnt(lambda t: t.result == "live"),
            "not_scheduled": cnt(lambda t: t.result == "not_scheduled"),
            "failed": cnt(lambda t: t.result == "failed"),
            "deferred_in": deferred_in,
            "blocking_risks": len(blocks),
            "pending_feedback": fb_pending,
            "receipt_rate": round(len(replied) / len(real), 4) if real else 0,
        },
        "rates": {
            "decided_count": len(decided), "achieved_count": len(achieved),
            "planned_rate": round(len(planned_hits) / len(decided), 4) if decided else None,
            "raw_rate": round(len(achieved) / len(decided), 4) if decided else None,
            "excluded_from_numerator": len(achieved) - len(planned_hits),
            "note": "分母=已出结果参与单；人工例外/冻结后纳入不计按计划上线率分子",
        },
        "lists": {
            "focus": focus, "abnormal": abnormal, "exception": exception,
            "freeze_late": freeze_late, "missing_plan": missing_plan,
            "blocking_risks": [RS.serialize(x) for x in blocks],
        },
        "brief": {k: [brief(x) for x in v] for k, v in {
            "focus": focus, "abnormal": abnormal, "exception": exception,
            "freeze_late": freeze_late, "missing_plan": missing_plan}.items()},
        "scope_note": SCOPE_NOTE,
        "filter": {"plan_id": plan_id},
    }


def missing_plans(db: Session) -> Dict[str, Any]:
    rows = db.query(PmwbPbTrack).filter(
        PmwbPbTrack.active == 1,
        PmwbPbTrack.current_plan_id.is_(None),
        PmwbPbTrack.result.notin_(C.TERMINAL_RESULTS),
    ).all()
    return {"items": [K.serialize_track(db, x) for x in rows], "total": len(rows),
            "note": "无下一有效版本可顺延：主行持续在跟、不关闭，待补版本计划"}
