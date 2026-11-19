"""四环节状态机 + 准入判定 + 上线结果 + 自动顺延 + 手工例外（pb-3 / L3，核心）。

唯一写入口，禁止其它服务直接改主行的 stage / admit_status / result / 归属版本：
  - 主行环节 = 团队子行最慢值，禁手工直接设；回退必填原因并写留痕 + 自动风险；
  - 准入四态，判定事实只取主行进入「等待发布」时间，时点由版本计划派生；
  - 未准入 / 未排进版本 / 上线失败 → **默认自动顺延**到下一有效版本，直到成功上线；
  - 手工处理：逐单「确认顺延 / 例外放行留本版」，四要素齐全、可撤销、不污染分子；
  - 上线结果硬门禁：有「影响上线且未消除」风险时拒绝登记「已线上」。

终态仅 live / cancelled；主行唯一、顺延不新建主行、不清空反馈与风险历史。
"""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from constants import paiban as C
from core.exceptions import NotFoundException, ValidationException
from db.models import (
    PmwbPbFeedback, PmwbPbParticipation, PmwbPbTrack, PmwbPbTrackTeam,
    PmwbPbVersionChangeLog, PmwbPbVersionPlan, now_cn,
)
from services import paiban_common as K
from services import paiban_risk as RS
from services import paiban_version as VS


# ── 初始化 / 归属解析 ────────────────────────────────────────────
def initialize(db: Session, t: PmwbPbTrack, *, operator: str = "") -> None:
    """纳入时唯一一次解析版本归属；派生截止不落库、回落不落副本。"""
    resolved = VS.resolve_plan(db, t.system_name or "")
    plan = resolved.get("plan")
    if plan:
        t.current_plan_id = plan["id"]
        t.plan_source = "default" if resolved.get("source") == "default" else "exclusive"
        obj = db.query(PmwbPbVersionPlan).filter(PmwbPbVersionPlan.id == plan["id"]).first()
        freeze = obj and C.derive_deadlines(obj.release_date)["freeze_date"]
        t.freeze_late = int(bool(freeze and K.today() > date.fromisoformat(freeze)))
        K.ensure_participation(db, t, obj, "pending")
    else:
        t.current_plan_id = None
        t.plan_source = "missing"
    t.stage = "plan_confirm"
    t.stage_entered_at = now_cn()
    t.admit_status = "pending"
    evaluate_admission(db, t, auto_defer=False)
    K.recompute_counters(db, t)


# ── 主行环节 = 子行最慢值 ────────────────────────────────────────
def recompute_main_stage(db: Session, t: PmwbPbTrack, *, operator: str = "",
                         source: str = "page") -> str:
    subs = K.teams_of(db, t.id)
    if not subs:
        return t.stage
    slowest = min(K.STAGE_INDEX.get(x.stage, 0) for x in subs)
    all_done = all(int(x.done or 0) == 1 and x.stage == "wait_release" for x in subs)
    target = K.STAGE_KEYS[slowest]
    if not all_done and target == "wait_release":
        target = "test"  # 存在未完成子行时主行不能进入等待发布（AC-D4）
    before = t.stage
    if target != before:
        t.stage = target
        t.stage_entered_at = now_cn()
        K.add_stage_log(db, t, target, from_stage=before, source=source,
                        operator=operator, is_rollback=K.STAGE_INDEX[target] < K.STAGE_INDEX[before],
                        reason="团队子行最慢值重算" if source == "auto" else "")
    if target == "wait_release" and not t.wait_release_at:
        t.wait_release_at = now_cn()
        K.add_stage_log(db, t, "wait_release", from_stage=before, source=source,
                        operator=operator, reason="全部团队子行完成测试，进入等待发布")
    elif target != "wait_release" and t.wait_release_at:
        t.wait_release_at = None
        if t.admit_status == "admitted":
            t.admit_status = "pending"  # 回退后重新触发准入判定
    evaluate_admission(db, t, auto_defer=False)
    K.recompute_counters(db, t)
    return t.stage


# ── 准入判定（唯一实现）──────────────────────────────────────────
def simulate_admission(release_date: date, lead_days: int, fact_date: Optional[date],
                       as_of: Optional[date] = None) -> Dict[str, Any]:
    """页面准入模拟器与后端判定共用同一规则；fact=进入等待发布日期。"""
    gate = release_date - timedelta(days=int(lead_days))
    as_of = as_of or K.today()
    if fact_date and fact_date <= gate:
        status, hint = "admitted", "在判定时点前（含当天）进入等待发布 → 冻结在本版本"
    elif fact_date and fact_date > gate:
        status, hint = "not_admitted", "时点后才进入等待发布 → 未准入，默认自动顺延"
    elif as_of <= gate:
        status, hint = "pending", "未到判定时点，准入状态待判定"
    else:
        status, hint = "not_admitted", "判定时点已过仍未进入等待发布 → 未准入，默认自动顺延"
    return {
        "gate_at": gate.isoformat(), "fact_date": fact_date.isoformat() if fact_date else "",
        "diff_days": (gate - fact_date).days if fact_date else None,
        "status": status, "status_label": dict(C.ADMIT_STATUSES).get(status, status),
        "hint": hint,
    }


def evaluate_admission(db: Session, t: PmwbPbTrack, *, as_of: Optional[date] = None,
                       auto_defer: bool = False) -> str:
    plan = K.plan_of(db, t)
    if t.admit_status == "exception":
        return t.admit_status
    if plan is None:
        t.admit_status = "pending"
        return t.admit_status
    if plan.admit_mode != "wait_release_n_days":
        t.admit_status = "admitted"       # 开放模式无闸门
        t.admit_decided_at = now_cn()
    else:
        gate_s = C.admit_gate_at(plan.release_date, plan.admit_mode, plan.admit_lead_days)
        fact = t.wait_release_at.date() if isinstance(t.wait_release_at, datetime) else None
        sim = simulate_admission(plan.release_date, plan.admit_lead_days or 0, fact, as_of)
        t.admit_status = sim["status"]
        t.admit_decided_at = now_cn() if sim["status"] != "pending" else None
    K.ensure_participation(db, t, plan, t.admit_status)
    if t.admit_status == "not_admitted" and auto_defer:
        auto_defer_to_next(db, t, "准入未通过（未提前进入等待发布）", "not_scheduled")
    return t.admit_status


def admission_snapshot(db: Session, t: PmwbPbTrack) -> Dict[str, Any]:
    plan = K.plan_of(db, t)
    if not plan:
        return {"gate_at": "", "fact_at": K.dt_iso(t.wait_release_at), "diff_days": None,
                "original_status": t.admit_status, "plan_no": ""}
    gate = C.admit_gate_at(plan.release_date, plan.admit_mode, plan.admit_lead_days)
    fact = t.wait_release_at.date() if isinstance(t.wait_release_at, datetime) else None
    return {
        "gate_at": gate, "fact_at": fact.isoformat() if fact else "",
        "diff_days": (date.fromisoformat(gate) - fact).days if gate and fact else None,
        "original_status": t.admit_status, "plan_no": plan.version_no,
        "plan_id": plan.id,
    }


# ── 自动顺延（默认动作，不需人工确认）───────────────────────────
def auto_defer_to_next(db: Session, t: PmwbPbTrack, reason: str, result: str) -> Dict[str, Any]:
    """主行唯一、循环到成功上线；无下一版进待补版本计划清单，主行不关闭。"""
    old_plan = K.plan_of(db, t)
    nxt = VS.next_plan(db, old_plan) if old_plan else None
    t.result = result
    K.close_participation(db, t, old_plan.id if old_plan else None, result, "not_achieved")
    chain = K.jload(t.plan_chain, [])
    chain.append({
        "plan_id": old_plan.id if old_plan else None,
        "version_no": old_plan.version_no if old_plan else "",
        "result": result, "reason": reason, "at": K.dt_iso(now_cn()),
    })
    t.plan_chain = K.jdump(chain)
    t.defer_count = (t.defer_count or 0) + 1
    t.last_defer_reason, t.last_defer_at = reason, now_cn()
    before = {"admit_status": t.admit_status, "plan_id": t.current_plan_id}
    if nxt:
        t.current_plan_id = nxt["id"]
        t.plan_source = "default" if nxt.get("scope_type") == "default" else "exclusive"
    else:
        t.current_plan_id = None
        t.plan_source = "missing"
    t.result, t.result_date, t.result_reason = "", None, ""
    t.admit_status, t.admit_decided_at = "pending", None
    t.exception_flag, t.exception_reason, t.exception_operator = 0, None, None
    t.exception_at, t.exception_fact = None, None
    if result == "failed":
        t.fail_count = (t.fail_count or 0) + 1
        t.stage, t.wait_release_at = "test", None
        t.stage_entered_at = now_cn()
        for sub in K.teams_of(db, t.id):
            sub.stage, sub.done, sub.stage_entered_at = "test", 0, now_cn()
    rs = RS.auto(db, t, "go_live_failed" if result == "failed" else "admit_failed",
                 f"{reason}；自动顺延第 {t.defer_count} 次" + ("（无下一版本，待补版本计划）" if not nxt else ""),
                 raw_ref=f"原版本 {old_plan.version_no if old_plan else '-'} / 结果 {result}")
    K.add_stage_log(db, t, t.stage, from_stage=before.get("stage", ""), source="auto",
                    is_rollback=(result == "failed"), reason=reason, risk_id=rs.id,
                    before_value=before, after_value={"plan_id": t.current_plan_id,
                                                      "defer_count": t.defer_count})
    if nxt:
        obj = db.query(PmwbPbVersionPlan).filter(PmwbPbVersionPlan.id == nxt["id"]).first()
        K.ensure_participation(db, t, obj, "pending")
        # 未排进版本保留等待发布事实，新版本可快速判定；上线失败已清空事实需重走测试
        evaluate_admission(db, t, auto_defer=False)
    K.recompute_counters(db, t)
    return {
        "deferred": True, "defer_count": t.defer_count,
        "next_plan": nxt["version_no"] if nxt else "",
        "missing_plan": not bool(nxt), "risk_id": rs.id,
        "terminal": False,
    }


# ── 上线结果（四态 + 硬门禁）────────────────────────────────────
def set_result(db: Session, track_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    t = K.track_or_404(db, track_id)
    result = (payload.get("result") or "").strip()
    if result not in [k for k, _ in C.RESULTS] or not result:
        raise ValidationException("上线结果必须在四态闭集内")
    reason = (payload.get("reason") or "").strip()
    operator = (payload.get("operator") or "").strip()
    if result in C.RESULT_REQUIRE_REASON and not reason:
        raise ValidationException("未排进版本 / 上线失败 / 取消必须填写原因")
    if t.result in C.TERMINAL_RESULTS:
        raise ValidationException("主行已处于终态，仅可查看轨迹，不可重复登记结果")
    gate_msg = ""
    if result == "live":
        if t.stage != "wait_release":
            raise ValidationException("仅「等待发布」环节可登记「已上线」")
        if t.admit_status not in ("admitted", "exception"):
            raise ValidationException("准入未通过（或仍待判定），不能登记已上线；请先手工处理或等待自动顺延")
        gate_msg = RS.gate_message(db, t.id)
        if gate_msg:
            raise ValidationException(gate_msg)
    try:
        rd = date.fromisoformat((payload.get("result_date") or "").strip() or K.today().isoformat())
    except ValueError:
        raise ValidationException("结果日期格式应为 YYYY-MM-DD")
    t.result, t.result_date, t.result_reason = result, rd, reason
    t.result_operator, t.result_at = operator, now_cn()
    plan = K.plan_of(db, t)
    planned = bool(result == "live" and not t.exception_flag and not t.freeze_late
                   and plan and rd <= plan.release_date)
    part = K.ensure_participation(db, t, plan, t.admit_status)
    if part:
        part.result, part.result_date = result, rd
        part.outcome = "achieved" if result == "live" else "not_achieved"
    K.add_stage_log(db, t, t.stage, from_stage=t.stage, source="page", operator=operator,
                    reason=f"登记上线结果：{dict(C.RESULTS).get(result)} {reason}".strip())
    out: Dict[str, Any] = {"result": result, "planned": planned, "deferred": False}
    if result in C.DEFER_RESULTS:
        out.update(auto_defer_to_next(db, t, reason, result))
        out["planned"] = False
    else:
        K.close_participation(db, t, plan.id if plan else None, result,
                              "achieved" if result == "live" else "not_achieved")
        K.recompute_counters(db, t)
        out["terminal"] = result in C.TERMINAL_RESULTS
    snapshot = K.serialize_track(db, t)
    db.commit()
    out["track"] = snapshot
    return out


# ── 手工处理：确认顺延 / 例外放行 / 撤销（v1.2 决策 #3）──────────
def manual_handle(db: Session, track_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    t = K.track_or_404(db, track_id)
    action = (payload.get("action") or "").strip()
    operator = (payload.get("operator") or "").strip()
    if action not in ("defer", "allow", "revoke"):
        raise ValidationException("手工处理仅支持 确认顺延 / 例外放行 / 撤销例外")
    if t.result in C.TERMINAL_RESULTS:
        raise ValidationException("终态主行不适用手工处理")
    out: Dict[str, Any] = {"action": action, "idempotent": False}

    if action == "revoke":
        if not t.exception_flag:
            raise ValidationException("该主行不是人工例外准入，无需撤销")
        before = K.jload(t.before_value, {})
        t.exception_flag, t.exception_reason = 0, None
        t.exception_operator, t.exception_at, t.exception_fact = None, None, None
        t.admit_status = "not_admitted"
        K.add_stage_log(db, t, t.stage, source="manual_exception", operator=operator,
                        reason="撤销人工例外放行，回到未准入并按默认自动顺延",
                        before_value={"admit_status": "exception"},
                        after_value={"admit_status": "not_admitted"})
        out.update(auto_defer_to_next(db, t, "撤销例外后默认顺延", "not_scheduled"))
        snapshot = K.serialize_track(db, t)
        db.commit()
        out["track"] = snapshot
        return out

    if action == "defer":
        if t.admit_status == "exception":
            raise ValidationException("已人工例外留在本版；如需顺延请先撤销例外")
        if t.admit_status != "not_admitted":
            raise ValidationException("仅未准入工单需要确认顺延")
        out.update(auto_defer_to_next(db, t, "手工处理：确认顺延（默认动作）", "not_scheduled"))
        snapshot = K.serialize_track(db, t)
        db.commit()
        out["track"] = snapshot
        return out

    # action == allow：四要素齐全、幂等、不改版本计划规则
    reason = (payload.get("reason") or "").strip()
    if not reason:
        raise ValidationException("例外放行必须填写原因")
    if reason not in [k for k, _ in C.EXCEPTION_REASONS]:
        raise ValidationException("例外原因必须取自闭集字典")
    if reason == "other" and not (payload.get("reason_note") or "").strip():
        raise ValidationException("选择「其他」时必须填写说明")
    if not operator:
        raise ValidationException("例外放行必须填写操作人")
    fact = admission_snapshot(db, t)
    key = f"{t.id}|{fact.get('plan_id')}|{fact.get('gate_at')}"
    if t.exception_flag and (K.jload(t.exception_fact, {}) or {}).get("key") == key:
        out["idempotent"] = True
        out["track"] = K.serialize_track(db, t)
        return out
    before = {"admit_status": t.admit_status, "plan_id": t.current_plan_id,
              "defer_count": t.defer_count or 0}
    # 已自动顺延的可「召回本版」：取原属版本链最后一条
    chain = K.jload(t.plan_chain, [])
    if chain and chain[-1].get("plan_id"):
        t.current_plan_id = chain[-1]["plan_id"]
        t.plan_source = "exclusive"
    t.exception_flag, t.exception_reason = 1, reason
    t.exception_operator, t.exception_at = operator, now_cn()
    t.admit_status, t.admit_decided_at = "exception", now_cn()
    t.result, t.result_date, t.result_reason = "", None, ""
    t.before_value = K.jdump(before)
    fact.update({"key": key, "operator": operator, "at": K.dt_iso(now_cn()),
                 "reason_note": (payload.get("reason_note") or "").strip()})
    t.exception_fact = K.jdump(fact)
    plan = K.plan_of(db, t)
    part = K.ensure_participation(db, t, plan, "exception")
    if part:
        part.is_exception, part.result, part.outcome = 1, "", "in_progress"
    K.add_stage_log(db, t, t.stage, source="manual_exception", operator=operator,
                    reason=f"人工例外放行：{dict(C.EXCEPTION_REASONS).get(reason)}",
                    before_value=before, after_value={"admit_status": "exception",
                                                      "plan_id": t.current_plan_id})
    if plan:
        db.add(PmwbPbVersionChangeLog(
            plan_id=plan.id, version_no=plan.version_no, change_type="update",
            field="manual_exception", old_value=before["admit_status"], new_value="exception",
            affected_count=1, operator=operator, changed_at=now_cn(),
            remark=f"工单 {t.ticket_no} 例外放行；原判定事实 {K.jdump(fact)}",
        ))
    K.recompute_counters(db, t)
    snapshot = K.serialize_track(db, t)
    db.commit()
    out["track"] = snapshot
    out["fact"] = fact
    return out


# ── 列表 / 轨迹 ─────────────────────────────────────────────────
def list_tracks(db: Session, *, plan_id: Optional[int] = None, ticket_type: str = "",
                stage: str = "", admit_status: str = "", result: str = "",
                keyword: str = "", include_inactive: bool = False) -> Dict[str, Any]:
    q = K.track_where(db, plan_id, active_only=not include_inactive,
                      ticket_type=ticket_type, stage=stage, admit_status=admit_status)
    if result:
        q = q.filter(PmwbPbTrack.result == result)
    if keyword:
        q = q.filter(PmwbPbTrack.ticket_no.like(f"%{keyword}%") | PmwbPbTrack.title.like(f"%{keyword}%"))
    rows = q.order_by(PmwbPbTrack.id.desc()).all()
    return {
        "items": [K.serialize_track(db, x) for x in rows], "total": len(rows),
        "main_row_count": len(rows),
        "scope_note": "本列表按主行计数；团队视图按团队子行计数，不可加总",
        "filter": {"plan_id": plan_id, "ticket_type": ticket_type, "stage": stage,
                   "admit_status": admit_status, "result": result, "keyword": keyword},
    }


def timeline(db: Session, track_id: int) -> Dict[str, Any]:
    from db.models import PmwbPbStageLog
    t = K.track_or_404(db, track_id)
    logs = db.query(PmwbPbStageLog).filter(
        PmwbPbStageLog.track_id == track_id
    ).order_by(PmwbPbStageLog.id).all()
    parts = db.query(PmwbPbParticipation).filter(
        PmwbPbParticipation.track_id == track_id
    ).order_by(PmwbPbParticipation.id).all()
    risks = RS.list_risks(db, track_id=track_id)
    feedbacks = db.query(PmwbPbFeedback).filter(
        PmwbPbFeedback.track_id == track_id
    ).order_by(PmwbPbFeedback.id).all()
    return {
        "track": K.serialize_track(db, t),
        "stage_logs": [{
            "id": x.id, "from_stage": x.from_stage, "to_stage": x.to_stage,
            "is_rollback": int(x.is_rollback or 0), "rollback_count": x.rollback_count or 0,
            "reason": x.reason, "source": x.source, "operator": x.operator,
            "changed_at": K.dt_iso(x.changed_at), "before_value": K.jload(x.before_value, {}),
            "after_value": K.jload(x.after_value, {}),
        } for x in logs],
        "participations": [{
            "plan_id": p.plan_id, "version_no": p.version_no, "admit_status": p.admit_status,
            "result": p.result, "outcome": p.outcome, "is_exception": int(p.is_exception or 0),
            "joined_at": K.dt_iso(p.joined_at), "left_at": K.dt_iso(p.left_at),
        } for p in parts],
        "risks": risks["items"],
        "feedbacks": [{
            "id": f.id, "channel": f.channel, "adopt_status": f.adopt_status,
            "raw_text": f.raw_text, "created_at": K.dt_iso(f.created_at),
            "rolled_back": int(f.rolled_back or 0),
        } for f in feedbacks],
    }
