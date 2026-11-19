"""反馈同步四通道（pb-7 / L9）—— 邮件回执 / 团队批量更新 / 行内记一笔 / 代录。

铁律（方案 7.7）：
  - 结构化四字段齐全 → 自动采纳；自由文本 → 只出建议进待核对，**不改任何状态**；
  - 原文全量留存不覆盖；同批次冲突全保留，不取最后一条静默覆盖；
  - 采纳前值保留可一键回滚；同一 Message-ID 幂等；
  - 风险按 (工单, 类型) 未消除合并更新不新建；影响上线触发硬门禁；
  - 邮件通道不可达 → 标「待自动补跑」，不转人工判定、不关键词兜底猜状态；
  - 反馈不登记「已上线」结果，仍走 paiban_track.set_result 门禁。
"""

import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from constants import paiban as C
from core.exceptions import ValidationException
from db.models import (
    PmwbPbFeedback, PmwbPbRisk, PmwbPbSuperviseItem, PmwbPbTrack,
    PmwbPbTrackTeam, now_cn,
)
from services import paiban_common as K
from services import paiban_risk as RS
from services import paiban_team as TEAM

STAGE_WORDS = {v: k for k, v in C.STAGES}
RISK_HINTS = [
    ("env_dependency", ("环境", "依赖", "接口未", "资源未到")),
    ("dev_delay", ("开发延期", "开发进度", "排期")),
    ("test_blocked", ("测试阻塞", "测试不过", "缺陷未修")),
    ("requirement_change", ("需求变更", "方案调整")),
    ("plan_undecided", ("方案未定", "待确认方案")),
    ("window_conflict", ("窗口冲突", "发布窗口")),
    ("resource", ("人手", "资源不足")),
]


def _infer_risk_type(text: str) -> str:
    for key, words in RISK_HINTS:
        if any(w in text for w in words):
            return key
    return "other"


def _parse_free_text(text: str) -> Dict[str, Any]:
    """自由文本只提取建议，不产生采纳动作。"""
    stage = next((key for word, key in STAGE_WORDS.items() if word in text), "")
    m = re.search(r"(?:预计|承诺|计划)(?:完成)?日期?\s*[:：]?\s*(\d{4}-\d{2}-\d{2})", text)
    return {
        "stage": stage, "promise_date": m.group(1) if m else "",
        "progress": text.strip()[:2000], "risk": text.strip()[:2000],
    }


def _structured(payload: Dict[str, Any]) -> bool:
    """四字段齐全才自动采纳；缺一项一律待核对。"""
    return all(str(payload.get(k) or "").strip() for k in C.RECEIPT_FIELDS)


def _suggested(payload: Dict[str, Any], raw: str) -> Dict[str, Any]:
    stage = (payload.get("stage") or "").strip()
    if stage in STAGE_WORDS:
        stage = STAGE_WORDS[stage]
    if stage not in C.STAGE_LABELS:
        stage = ""
    return {
        "stage": stage,
        "progress": (payload.get("progress") or "").strip(),
        "risk": (payload.get("risk") or "").strip(),
        "promise_date": (payload.get("promise_date") or "").strip(),
        "risk_type": (payload.get("risk_type") or _infer_risk_type(
            (payload.get("risk") or "") + raw)).strip(),
        "affect_release": int(payload.get("affect_release") or 0),
    }


def _team_for(db: Session, t: PmwbPbTrack, team_id: Optional[int]) -> Optional[PmwbPbTrackTeam]:
    if team_id:
        return db.query(PmwbPbTrackTeam).filter_by(id=team_id, track_id=t.id).first()
    subs = K.teams_of(db, t.id)
    return subs[0] if subs else None


def apply_suggestion(db: Session, fb: PmwbPbFeedback, suggestion: Dict[str, Any],
                     *, source: str, operator: str) -> Dict[str, Any]:
    """唯一采纳实现：写流转留痕 + 团队进度 + 风险；不改结果态，不跳版本。"""
    t = K.track_or_404(db, fb.track_id)
    before = {"stage": t.stage, "admit_status": t.admit_status,
              "plan_id": t.current_plan_id, "result": t.result}
    sub = _team_for(db, t, fb.team_id)
    changes: List[str] = []
    if suggestion.get("stage") and sub and suggestion["stage"] != sub.stage:
        new_stage = suggestion["stage"]
        forward = K.STAGE_INDEX[new_stage] >= K.STAGE_INDEX[sub.stage]
        if not forward and not suggestion.get("reason"):
            fb.adopt_status = "pending"
            fb.review_note = "反馈含状态回退但未给出原因，按规则不自动落回退，待核对"
            db.flush()
            return {"adopted": False, "reason": fb.review_note}
        TEAM.set_team_stage(db, sub.id, new_stage,
                            reason=suggestion.get("reason") or "",
                            operator=operator, source=source, feedback_id=fb.id)
        changes.append(f"环节 {C.STAGE_LABELS.get(sub.stage, sub.stage)} → "
                       f"{C.STAGE_LABELS.get(new_stage, new_stage)}")
    if sub:
        note = f"[{K.dt_iso(now_cn())}][{source}] 进度：{suggestion.get('progress') or '-'}"
        if suggestion.get("promise_date"):
            note += f"；预计完成日：{suggestion['promise_date']}"
        sub.note = f"{sub.note or ''}\n{note}".strip()
        sub.last_feedback_at = now_cn()
        changes.append("进度与预计完成日")
    risk_row = None
    if suggestion.get("risk"):
        risk_row = RS.upsert(
            db, t, suggestion.get("risk_type") or "other",
            suggestion["risk"], affect_release=int(suggestion.get("affect_release") or 0),
            source=source, raw_ref=suggestion["risk"], reporter=operator or "厂家反馈",
        )
        fb.risk_id = risk_row.id
        changes.append("风险事件")
    fb.before_value, fb.after_value = K.jdump(before), K.jdump(suggestion)
    fb.adopt_status = "auto" if source in ("mail", "batch", "proxy") else "auto"
    fb.review_note = "；".join(changes) or "仅记录反馈原文"
    t.feedback_count = (t.feedback_count or 0) + 1
    t.last_feedback_at = now_cn()
    K.recompute_counters(db, t)
    db.flush()
    return {"adopted": True, "changes": changes, "risk_id": risk_row.id if risk_row else None}


def submit(db: Session, payload: Dict[str, Any], *, channel: str = "") -> Dict[str, Any]:
    """B/C/D 通道统一提交入口；A 邮件回执走 pull_mail()。"""
    ch = (channel or payload.get("channel") or "").strip()
    if ch not in [k for k, _ in C.FEEDBACK_CHANNELS]:
        raise ValidationException("反馈通道不在闭集内")
    if ch == "mail":
        raise ValidationException("邮件回执请走 /feedback/mail/pull（只读收件箱）")
    if ch == "proxy" and not (payload.get("reporter") or "").strip():
        raise ValidationException("代录必须填写反馈人")
    track_id = int(payload.get("track_id") or 0)
    t = K.track_or_404(db, track_id)
    raw = (payload.get("raw_text") or "").strip()
    structured = _structured(payload)
    suggestion = _suggested(payload, raw)
    if ch == "inline" and not structured and not payload.get("stage"):
        suggestion = _parse_free_text(raw)
    conflict = db.query(PmwbPbFeedback).filter(
        PmwbPbFeedback.track_id == track_id,
        PmwbPbFeedback.batch_no == (payload.get("batch_no") or ""),
        PmwbPbFeedback.rolled_back == 0,
    ).first()
    if conflict is not None and conflict.parsed_json:
        old = K.jload(conflict.parsed_json, {})
        if suggestion.get("stage") and old.get("stage") and old["stage"] != suggestion["stage"]:
            structured = False
    fb = PmwbPbFeedback(
        track_id=track_id, team_id=payload.get("team_id") or None, channel=ch,
        batch_no=payload.get("batch_no") or None, receipt_code=payload.get("receipt_code") or None,
        source_ref=payload.get("source_ref") or None,
        sender=payload.get("sender") or payload.get("reporter") or "",
        raw_text=raw, parsed_json=K.jdump(suggestion),
        suggested_json=K.jdump(suggestion if not structured else {}),
        adopt_status="pending", reporter=payload.get("reporter") or None,
        created_at=now_cn(), feedback_at=now_cn(),
    )
    db.add(fb)
    db.flush()
    out: Dict[str, Any] = {"id": fb.id, "channel": ch, "adopt_status": "pending"}
    if structured:
        apply_result = apply_suggestion(db, fb, suggestion, source=ch,
                                        operator=(payload.get("operator") or "").strip())
        out.update(apply_result)
        if conflict is not None:
            conflict.adopt_status = "conflict"
            conflict.review_note = f"同批次存在多份反馈（#{conflict.id} / #{fb.id}），原文均保留，待核对"
    else:
        fb.adopt_status = "conflict" if conflict is not None else "pending"
        fb.review_note = "自由文本或字段不全：只出建议，不自动改状态"
        K.recompute_counters(db, t)
    db.commit()
    out["adopt_status"] = fb.adopt_status
    out["feedback"] = serialize(fb)
    return out


def batch_submit(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    rows = []
    for it in payload.get("items") or []:
        p = dict(it)
        p.setdefault("channel", "batch")
        p.setdefault("batch_no", payload.get("batch_no"))
        p.setdefault("operator", payload.get("operator"))
        try:
            rows.append(submit(db, p, channel="batch"))
        except Exception as exc:
            rows.append({"ticket_no": it.get("ticket_no"), "error": str(exc)[:200]})
    return {"items": rows, "total": len(rows),
            "auto_count": sum(1 for x in rows if x.get("adopt_status") == "auto"),
            "pending_count": sum(1 for x in rows if x.get("adopt_status") in ("pending", "conflict"))}


def pull_mail(db: Session, *, since: str = "", until: str = "") -> Dict[str, Any]:
    """A 通道：按批次号前缀只读拉收件箱；Message-ID 幂等；不可达→待自动补跑。"""
    from services.keywork_mail_import import mail_db_ready, mail_db_path
    import sqlite3

    ready, reason = mail_db_ready()
    if not ready:
        pending = db.query(PmwbPbFeedback).filter(
            PmwbPbFeedback.channel == "mail",
            PmwbPbFeedback.pending_rerun == 1,
        ).count()
        return {"ok": False, "reason": reason, "pending_rerun": pending,
                "scope_note": "邮件通道不可达：标待自动补跑，不转人工判定"}
    path = mail_db_path().replace("\\", "/")
    where, args = [], []
    where.append("subject LIKE ?")
    args.append("%【排版督办回执】%")
    if since:
        where.append("date(sentAt/1000,'unixepoch','+8 hours') >= ?")
        args.append(since)
    if until:
        where.append("date(sentAt/1000,'unixepoch','+8 hours') <= ?")
        args.append(until)
    sql = ("SELECT id, COALESCE(messageId,''), COALESCE(fromEmail,''), "
           "COALESCE(subject,''), COALESCE(textBody,''), COALESCE(htmlBody,'') "
           "FROM InboxMessage WHERE " + " AND ".join(where) + " ORDER BY sentAt")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
    try:
        rows = conn.execute(sql, args).fetchall()
    finally:
        conn.close()
    created, duplicate, failed = [], 0, 0
    for mid, message_id, sender, subject, text, html in rows:
        body = text or re.sub(r"<[^>]+>", "\n", html or "")
        m = re.search(r"回执码\s*[:：]?\s*(PB-[A-Z0-9]+)", subject + "\n" + body)
        code = m.group(1) if m else ""
        item = db.query(PmwbPbSuperviseItem).filter_by(receipt_code=code).first() if code else None
        key = (message_id or f"local-{mid}")
        exists = db.query(PmwbPbFeedback).filter_by(
            track_id=item.track_id if item else 0, message_id=key
        ).first() if item else db.query(PmwbPbFeedback).filter_by(message_id=key).first()
        if exists is not None:
            duplicate += 1
            continue
        fields: Dict[str, Any] = {}
        for label, field in (("环节", "stage"), ("进度", "progress"),
                             ("风险", "risk"), ("预计完成日", "promise_date")):
            mm = re.search(label + r"\s*[:：]\s*([^\n\r]+)", body)
            if mm:
                fields[field] = mm.group(1).strip()
        suggestion = _suggested(fields, body[:2000])
        structured = bool(item and _structured(fields) and suggestion["stage"])
        fb = PmwbPbFeedback(
            track_id=item.track_id if item else 0, team_id=item.team_id if item else None,
            channel="mail", batch_no=item.batch_no if item else "",
            receipt_code=code or None, message_id=key, source_ref=str(mid),
            sender=sender or "", raw_text=body, parsed_json=K.jdump(suggestion),
            suggested_json=K.jdump({} if structured else suggestion),
            adopt_status="pending", created_at=now_cn(), feedback_at=now_cn(),
        )
        db.add(fb)
        db.flush()
        if item is None or not structured:
            fb.adopt_status = "parse_failed" if item is None else "pending"
            fb.review_note = "无法匹配回执锚或四字段不全，原文保留待核对"
            if item is None:
                fb.pending_rerun = 1
        else:
            apply_suggestion(db, fb, suggestion, source="mail_feedback",
                             operator=sender or "厂家")
            item.receipt_status, item.receipt_at = "received", now_cn()
        created.append({"id": fb.id, "adopt_status": fb.adopt_status,
                        "ticket_no": item.ticket_no if item else ""})
    db.commit()
    return {"ok": True, "scanned": len(rows), "created": created,
            "duplicate": duplicate, "failed": failed,
            "scope_note": "同 Message-ID 幂等；读自建连接，不写邮件中心"}


def review(db: Session, feedback_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    """待核对反馈人工采纳 / 驳回：采纳仍走同一 apply_suggestion，不另写状态。"""
    fb = db.query(PmwbPbFeedback).filter_by(id=feedback_id).first()
    if fb is None:
        raise ValidationException(f"反馈 {feedback_id} 不存在")
    action = (payload.get("action") or "").strip()
    if action not in ("adopt", "reject"):
        raise ValidationException("核对动作只能是 adopt / reject")
    reviewer = (payload.get("reviewer") or "").strip()
    if not reviewer:
        raise ValidationException("核对必须填写操作人")
    fb.reviewer, fb.reviewed_at = reviewer, now_cn()
    fb.review_note = (payload.get("review_note") or "").strip()
    if action == "reject":
        fb.adopt_status = "rejected"
        db.commit()
        return {"id": fb.id, "adopt_status": "rejected"}
    suggestion = K.jload(fb.suggested_json, {}) or K.jload(fb.parsed_json, {})
    result = apply_suggestion(db, fb, suggestion, source="inline", operator=reviewer)
    db.commit()
    return {"id": fb.id, "adopt_status": fb.adopt_status, **result}


def rollback(db: Session, feedback_id: int, *, operator: str) -> Dict[str, Any]:
    """一键回滚：恢复采纳前主行状态，反馈原文与留痕不删；回滚本身写留痕。"""
    fb = db.query(PmwbPbFeedback).filter_by(id=feedback_id).first()
    if fb is None:
        raise ValidationException(f"反馈 {feedback_id} 不存在")
    if fb.rolled_back or not fb.before_value:
        raise ValidationException("该反馈无可回滚的采纳前值")
    before = K.jload(fb.before_value, {}) or {}
    t = K.track_or_404(db, fb.track_id)
    target_stage = before.get("stage") or t.stage
    for sub in K.teams_of(db, t.id):
        if fb.team_id and sub.id != fb.team_id:
            continue
        sub.stage, sub.done, sub.stage_entered_at = target_stage, 0, now_cn()
    t.stage, t.stage_entered_at, t.wait_release_at = target_stage, now_cn(), None
    t.admit_status, t.current_plan_id = before.get("admit_status", "pending"), before.get("plan_id")
    t.result, t.result_date, t.result_reason = before.get("result", ""), None, ""
    fb.rolled_back, fb.rollback_at = 1, now_cn()
    fb.review_note = f"{fb.review_note or ''}\n[{K.dt_iso(now_cn())}] {operator} 一键回滚".strip()
    K.add_stage_log(db, t, target_stage, source="inline", operator=operator,
                    reason=f"回滚反馈 #{fb.id}", feedback_id=fb.id,
                    before_value=K.jload(fb.after_value, {}), after_value=before)
    K.recompute_counters(db, t)
    db.commit()
    return {"id": fb.id, "rolled_back": True, "restored": before}


def serialize(f: PmwbPbFeedback) -> Dict[str, Any]:
    return {
        "id": f.id, "track_id": f.track_id, "team_id": f.team_id,
        "channel": f.channel, "batch_no": f.batch_no, "receipt_code": f.receipt_code,
        "message_id": f.message_id, "sender": f.sender, "raw_text": f.raw_text,
        "parsed": K.jload(f.parsed_json, {}), "suggested": K.jload(f.suggested_json, {}),
        "adopt_status": f.adopt_status, "review_note": f.review_note,
        "reviewer": f.reviewer, "reviewed_at": K.dt_iso(f.reviewed_at),
        "rolled_back": int(f.rolled_back or 0), "pending_rerun": int(f.pending_rerun or 0),
        "reporter": f.reporter, "created_at": K.dt_iso(f.created_at),
    }


def pending_list(db: Session, *, status: str = "") -> Dict[str, Any]:
    q = db.query(PmwbPbFeedback).filter(
        PmwbPbFeedback.adopt_status.in_(("pending", "conflict", "parse_failed")),
        PmwbPbFeedback.rolled_back == 0,
    )
    if status:
        q = q.filter(PmwbPbFeedback.adopt_status == status)
    rows = q.order_by(PmwbPbFeedback.id).all()
    t0 = K.today()
    items = []
    for f in rows:
        x = serialize(f)
        d = f.created_at.date() if isinstance(f.created_at, __import__("datetime").datetime) else t0
        x["age_days"] = (t0 - d).days
        items.append(x)
    return {"items": items, "total": len(items),
            "max_age_days": max((x["age_days"] for x in items), default=0),
            "scope_note": "自由文本只出建议；待核对项未经采纳不改任何状态"}
