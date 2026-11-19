"""团队 × 工单类型一键批量督办（pb-6 / L6）—— 规则圈定 + 预览 + 确认发送 + 结果记录。

铁律：
  - AI 自测一律 dry_run；真发仅页面显式 confirm_send=true 且 dry_run=false；
  - 24h 冷却（成功发出计），5 类例外可显式忽略；跳过原因逐单可见；
  - 每逐单唯一回执码 = 反馈回执锚点；批次号 = 邮件主题路由锚点；
  - 收件人解析失败不静默丢弃，进「无法督办」清单；解析链只用 resolve_contact_emails。
"""

import hashlib
from html import escape as _esc
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from constants import paiban as C
from core.exceptions import ValidationException
from db.models import (
    PmwbPbRisk, PmwbPbStageLog, PmwbPbSuperviseBatch, PmwbPbSuperviseItem,
    PmwbPbTrack, PmwbPbTrackTeam, PmwbPbVersionPlan, now_cn,
)
from services import paiban_common as K

RECEIPT_SUBJECT_PREFIX = "【排版督办回执】"


def _preview_receipt(track_id: int, team_id: int, plan_id: int) -> str:
    """确定性预览回执码：同一(工单,团队,版本)在预览与实发间恒定，保证预览=实发同源。"""
    seed = f"PB|{plan_id}|{track_id}|{team_id}".encode("utf-8")
    return "PB-" + hashlib.md5(seed).hexdigest()[:12].upper()


def _last_sent(db: Session, track_id: int, team_id: Optional[int]) -> Optional[PmwbPbSuperviseItem]:
    q = db.query(PmwbPbSuperviseItem).join(
        PmwbPbSuperviseBatch, PmwbPbSuperviseBatch.id == PmwbPbSuperviseItem.batch_id
    ).filter(
        PmwbPbSuperviseItem.track_id == track_id,
        PmwbPbSuperviseItem.send_status == "sent",
        PmwbPbSuperviseBatch.dry_run == 0,
    )
    if team_id:
        q = q.filter(PmwbPbSuperviseItem.team_id == team_id)
    return q.order_by(PmwbPbSuperviseItem.id.desc()).first()


def cooldown_left_hours(db: Session, track_id: int, team_id: Optional[int]) -> int:
    last = _last_sent(db, track_id, team_id)
    if last is None or not last.created_at:
        return 0
    delta = timedelta(hours=C.COOLDOWN_HOURS) - (now_cn() - last.created_at)
    return max(0, int(delta.total_seconds() // 3600 + (1 if delta.total_seconds() % 3600 else 0)))


def _names(sub: PmwbPbTrackTeam) -> List[str]:
    return [x.strip() for x in (sub.owner or "").replace("，", ",").split(",") if x.strip()]


def resolve_recipients(sub: PmwbPbTrackTeam) -> Tuple[List[str], Dict[str, Any]]:
    """唯一收件人链：通讯录 → 人员主数据；失败返回可见状态，不猜邮箱。"""
    names = _names(sub)
    if not names:
        return [], {"status": "missing", "detail": "团队对接人为空"}
    try:
        from utils.email import ContactResolver
        mapped = ContactResolver().resolve_contact_emails(names)
    except Exception as exc:  # 通道不可用 → 不可督办，不转人工猜
        return [], {"status": "missing", "detail": f"收件人通道不可用：{str(exc)[:120]}"}
    emails = [v for v in mapped.values() if v]
    if not emails:
        return [], {"status": "missing", "detail": "姓名均无法解析到邮箱"}
    detail = {"status": "ok", "resolved": len(emails), "total": len(names)}
    if len(emails) < len(names):
        detail["status"] = "partial"
    return emails, detail


def _trigger_rules(db: Session, t: PmwbPbTrack, sub: PmwbPbTrackTeam) -> List[Dict[str, str]]:
    m = K.stage_metrics(db, t)
    out: List[Dict[str, str]] = []

    def add(key: str):
        label = dict(C.SUPERVISE_INCLUDE_RULES).get(key, key)
        out.append({"key": key, "label": label})

    if m["overdue"]:
        add("overdue")
    if m["near_due"]:
        add("near_due")
    if m["stalled"]:
        add("stalled")
    if t.blocking_hint if hasattr(t, "blocking_hint") else False:
        add("blocking_risk")
    blocking = db.query(PmwbPbRisk).filter(
        PmwbPbRisk.track_id == t.id, PmwbPbRisk.affect_release == 1,
        PmwbPbRisk.status == "open",
    ).count()
    if blocking:
        add("blocking_risk")
    if t.stage == "wait_release" and m["release_date"] and K.today().isoformat() > m["release_date"] and not t.result:
        add("wait_past_release")
    logs = db.query(PmwbPbStageLog).filter_by(track_id=t.id, is_rollback=1).count()
    if logs:
        add("rolled_back")
    if t.admit_status == "pending" and m["admit_gate_at"]:
        left = (datetime.strptime(m["admit_gate_at"], "%Y-%m-%d").date() - K.today()).days
        if 0 <= left <= C.NEAR_DUE_DAYS:
            add("admit_pending")
    if t.defer_count or (K.jload(t.plan_chain, []) or []):
        add("deferred")
    if t.pending_receipt_batch:
        add("receipt_overdue")
    return out


def _skip_reason(db: Session, t: PmwbPbTrack, sub: PmwbPbTrackTeam, *,
                 ignore_cooldown: bool, exception_reason: str) -> str:
    if t.result in C.TERMINAL_RESULTS or not t.active:
        return "terminal"
    if int(sub.done or 0) == 1 and sub.stage == "wait_release":
        return "team_done"
    left = cooldown_left_hours(db, t.id, sub.id)
    if left and not ignore_cooldown:
        return "cooldown"
    if ignore_cooldown and exception_reason not in [k for k, _ in C.COOLDOWN_EXCEPTIONS]:
        return "cooldown_exception_invalid"
    return ""


def build_preview(db: Session, *, plan_id: int, team_name: str = "",
                  ticket_type: str = "", ignore_cooldown: bool = False,
                  exception_reason: str = "") -> Dict[str, Any]:
    """预览：按团队 × 类型分组，逐单列规则/跳过原因；**不写任何数据、不发邮件**。"""
    if not plan_id:
        raise ValidationException("请先选择版本计划")
    q = db.query(PmwbPbTrackTeam, PmwbPbTrack).join(
        PmwbPbTrack, PmwbPbTrackTeam.track_id == PmwbPbTrack.id
    ).filter(PmwbPbTrack.active == 1, PmwbPbTrack.current_plan_id == plan_id)
    if team_name:
        q = q.filter(PmwbPbTrackTeam.team_name == team_name)
    if ticket_type:
        q = q.filter(PmwbPbTrack.ticket_type == ticket_type)
    groups: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for sub, t in q.all():
        triggers = _trigger_rules(db, t, sub)
        if not triggers:
            continue
        skip = _skip_reason(db, t, sub, ignore_cooldown=ignore_cooldown,
                            exception_reason=exception_reason)
        emails, recipient = resolve_recipients(sub)
        if not emails and not skip:
            skip = "no_recipient"
        key = (sub.team_name, t.ticket_type)
        g = groups.setdefault(key, {
            "team_name": sub.team_name, "ticket_type": t.ticket_type,
            "ticket_type_label": dict(C.TICKET_TYPES).get(t.ticket_type, t.ticket_type),
            "recipients": emails, "recipient_detail": recipient,
            "items": [], "included_count": 0, "skipped_count": 0,
        })
        item = {
            "track_id": t.id, "team_id": sub.id, "ticket_no": t.ticket_no,
            "title": t.title, "stage": t.stage,
            "stage_label": C.STAGE_LABELS.get(t.stage, t.stage),
            "deadline": K.stage_metrics(db, t)["deadline"],
            "receipt_code": _preview_receipt(t.id, sub.id, plan_id),
            "triggers": triggers, "skip_reason": skip,
            "skip_reason_label": dict(C.SUPERVISE_EXCLUDE_RULES).get(skip, skip),
            "cooldown_left_h": cooldown_left_hours(db, t.id, sub.id),
        }
        g["items"].append(item)
        if skip:
            g["skipped_count"] += 1
        else:
            g["included_count"] += 1
    plan = db.query(PmwbPbVersionPlan).filter_by(id=plan_id).first()
    plan_no = plan.version_no if plan else str(plan_id)
    result_groups = sorted(groups.values(), key=lambda x: (x["team_name"], x["ticket_type"]))
    for g in result_groups:
        batch_no = f"PB{plan_id}-预览-{g['team_name']}-{g['ticket_type']}"
        g["batch_no_hint"] = _batch_no(db, plan_id)
        g["mail"] = {
            "subject": f"{RECEIPT_SUBJECT_PREFIX}{plan_no} / {g['team_name']} / {g['batch_no_hint']}",
            "body_html": _body(g, g["batch_no_hint"], plan_no),
        }
    return {
        "plan_id": plan_id, "groups": result_groups,
        "cooldown_hours": C.COOLDOWN_HOURS,
        "exception_options": [{"value": k, "label": v} for k, v in C.COOLDOWN_EXCEPTIONS],
        "scope_note": "预览含真实邮件正文，可在发送前编辑；回执码预览与实发同源",
        "dry_run_note": "自测一律 dry_run；真发仅页面显式 confirm_send=true",
    }


def _batch_no(db: Session, plan_id: int) -> str:
    stamp = now_cn().strftime("%Y%m%d%H%M%S")
    seq = db.query(PmwbPbSuperviseBatch).filter(
        PmwbPbSuperviseBatch.batch_no.like(f"PB{plan_id}-{stamp}-%")
    ).count() + 1
    return f"PB{plan_id}-{stamp}-{seq:02d}"


def _body(group: Dict[str, Any], batch_no: str, plan_no: str) -> str:
    lines = [f"<p>{group['team_name']} 团队：</p>",
             f"<p>版本 {plan_no} 以下工单需按计划推进，请回复本邮件反馈实际进度与风险。</p>",
             "<ol>"]
    for it in group["items"]:
        if it["skip_reason"]:
            continue
        lines.append(f"<li>{_esc(it['ticket_no'])} {_esc(it['title'])}"
                     f"（当前环节：{C.STAGE_LABELS.get(it['stage'], it['stage'])}，"
                     f"截止：{it['deadline'] or '-'}，回执码："
                     f"<b>{_esc(it['receipt_code'])}</b>）</li>")
    lines.append("</ol>")
    lines.append("<p>请按四字段回复：环节 / 进度说明 / 风险 / 预计完成日，"
                 "并保留邮件主题中的批次号。批次号：" + _esc(batch_no) + "</p>")
    return "".join(lines)


def send(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    """确认发送：默认 dry_run；真发必须显式 confirm_send=true 且 dry_run=false。"""
    plan_id = int(payload.get("plan_id") or 0)
    dry_run = bool(payload.get("dry_run", True))
    confirm = bool(payload.get("confirm_send", False))
    if not dry_run and not confirm:
        raise ValidationException("真发必须同时 dry_run=false 且 confirm_send=true（页面显式点击）")
    ignore = bool(payload.get("ignore_cooldown", False))
    ex_reason = (payload.get("exception_reason") or "").strip()
    groups_req = payload.get("groups")
    # 编辑后的邮件正文（预览=实发同源）：按 team|ticket_type 索引 {subject, body_html}。
    # 安全护栏：编辑正文必须保留本组全部回执码，否则拒绝（回执码是反馈回收唯一锚点）。
    edited = payload.get("edited_mails") or {}
    preview = build_preview(db, plan_id=plan_id, team_name=(payload.get("team_name") or "").strip(),
                            ticket_type=(payload.get("ticket_type") or "").strip(),
                            ignore_cooldown=ignore, exception_reason=ex_reason)
    chosen = set()
    for g in (groups_req or []):
        chosen.add((g.get("team_name"), g.get("ticket_type")))
    groups = [g for g in preview["groups"]
              if not chosen or (g["team_name"], g["ticket_type"]) in chosen]
    if not groups:
        raise ValidationException("没有符合督办条件的团队×类型分组")
    plan = db.query(PmwbPbVersionPlan).filter_by(id=plan_id).first()
    plan_no = plan.version_no if plan else str(plan_id)
    results = []
    for g in groups:
        batch_no = _batch_no(db, plan_id)
        sent, skipped, failed = 0, 0, 0
        for it in g["items"]:
            # 回执码与预览同源（确定性生成）；仍是本批次唯一锚点，反馈回收按此精确匹配。
            it["receipt_code"] = _preview_receipt(it["track_id"], it["team_id"], plan_id)
        batch = PmwbPbSuperviseBatch(
            batch_no=batch_no, team_name=g["team_name"], ticket_type=g["ticket_type"],
            plan_id=plan_id, rules_snapshot=K.jdump(
                {"include": C.SUPERVISE_INCLUDE_RULES, "exclude": C.SUPERVISE_EXCLUDE_RULES,
                 "ignore_cooldown": ignore, "exception_reason": ex_reason}),
            item_count=len(g["items"]), sent_count=0, skipped_count=g["skipped_count"],
            dry_run=int(dry_run), confirm_send=int(confirm and not dry_run),
            ignore_cooldown=int(ignore), exception_reason=ex_reason or None,
            operator=payload.get("operator") or "",
            receipt_deadline=(plan.release_date - timedelta(days=1)).isoformat()
            if plan and plan.release_date else "",
            receipt_status="none", created_at=now_cn(),
        )
        db.add(batch)
        db.flush()
        for it in g["items"]:
            status = "skipped" if it["skip_reason"] else ("dry_run" if dry_run else "pending")
            db.add(PmwbPbSuperviseItem(
                batch_id=batch.id, batch_no=batch_no, track_id=it["track_id"], team_id=it["team_id"],
                ticket_no=it["ticket_no"], receipt_code=it["receipt_code"],
                send_status=status, skip_reason=it["skip_reason"] or None,
                supervise_seq=1, cooldown_left_h=it["cooldown_left_h"],
                triggered_rules=K.jdump(it["triggers"]), receipt_status="none",
                created_at=now_cn(),
            ))
            if it["skip_reason"]:
                skipped += 1
        mail_result = None
        if g["included_count"] and g["recipients"]:
            try:
                from services.mail_dispatch import dispatch_email
                subject = f"{RECEIPT_SUBJECT_PREFIX}{plan_no} / {g['team_name']} / {batch_no}"
                body_html = _body(g, batch_no, plan_no)
                edit = edited.get(f"{g['team_name']}|{g['ticket_type']}") or {}
                if edit:
                    es = (edit.get("subject") or "").strip()
                    eb = (edit.get("body_html") or "").strip()
                    # 护栏1：编辑正文必须含全部回执码（反馈回收锚点不可删）。
                    required_codes = [it["receipt_code"] for it in g["items"] if not it["skip_reason"]]
                    missing = [c for c in required_codes if c and c not in eb]
                    if missing:
                        raise ValidationException(
                            f"编辑后的邮件正文缺少回执码锚点（{', '.join(missing[:3])}），已拒绝发送以保护反馈回收")
                    # 护栏2：真实批次号必须以实际为准替换预览批次号。
                    if eb:
                        eb = eb.replace(g.get("batch_no_hint", ""), batch_no)
                        body_html = eb
                    if es:
                        subject = es if batch_no in es else f"{es} / {batch_no}"
                mail_result = dispatch_email(
                    db=db, to=g["recipients"], subject=subject,
                    body=body_html, email_type="pmwb_paiban_supervise",
                    source="pmwb", ref_type="paiban_supervise", ref_id=batch_no,
                    confirm_send=confirm and not dry_run,
                )
                outcome = "dry_run" if dry_run or mail_result.get("dry_run") else "sent"
                for it in g["items"]:
                    if not it["skip_reason"]:
                        db.query(PmwbPbSuperviseItem).filter_by(
                            batch_id=batch.id, track_id=it["track_id"]
                        ).update({"send_status": outcome})
                        if outcome == "sent":
                            t = db.query(PmwbPbTrack).filter_by(id=it["track_id"]).first()
                            if t:
                                t.supervise_count = (t.supervise_count or 0) + 1
                                t.last_supervise_at = now_cn()
                                t.pending_receipt_batch = batch_no
                                sub = db.query(PmwbPbTrackTeam).filter_by(id=it["team_id"]).first()
                                if sub:
                                    sub.supervise_count = (sub.supervise_count or 0) + 1
                sent = g["included_count"] if outcome == "sent" else 0
            except Exception as exc:
                failed = g["included_count"]
                for it in g["items"]:
                    if not it["skip_reason"]:
                        db.query(PmwbPbSuperviseItem).filter_by(
                            batch_id=batch.id, track_id=it["track_id"]
                        ).update({"send_status": "failed",
                                  "failure_reason": str(exc)[:240]})
                mail_result = {"success": False, "message": str(exc)[:240]}
        else:
            failed = g["included_count"]
        batch.sent_count, batch.skipped_count, batch.failed_count = sent, skipped, failed
        batch.mail_result = K.jdump(mail_result) if mail_result else None
        results.append({"batch_no": batch_no, "team_name": g["team_name"],
                        "ticket_type": g["ticket_type"], "item_count": len(g["items"]),
                        "sent": sent, "skipped": skipped, "failed": failed,
                        "dry_run": dry_run, "mail_success": bool(
                            mail_result and mail_result.get("success"))})
    db.commit()
    return {"results": results, "total_batches": len(results),
            "confirm_send": confirm and not dry_run, "dry_run": dry_run,
            "scope_note": "dry_run 不消耗冷却；回执码已登记用于结构化回收"}


def batches(db: Session, plan_id: Optional[int] = None) -> Dict[str, Any]:
    q = db.query(PmwbPbSuperviseBatch)
    if plan_id:
        q = q.filter(PmwbPbSuperviseBatch.plan_id == plan_id)
    rows = q.order_by(PmwbPbSuperviseBatch.id.desc()).limit(100).all()
    return {"items": [{
        "id": x.id, "batch_no": x.batch_no, "team_name": x.team_name,
        "ticket_type": x.ticket_type, "plan_id": x.plan_id,
        "item_count": x.item_count, "sent_count": x.sent_count,
        "skipped_count": x.skipped_count, "dry_run": int(x.dry_run or 0),
        "confirm_send": int(x.confirm_send or 0), "receipt_status": x.receipt_status,
        "receipt_deadline": x.receipt_deadline, "operator": x.operator,
        "created_at": K.dt_iso(x.created_at),
    } for x in rows], "total": len(rows)}


def batch_detail(db: Session, batch_no: str) -> Dict[str, Any]:
    b = db.query(PmwbPbSuperviseBatch).filter(
        PmwbPbSuperviseBatch.batch_no == batch_no).first()
    if b is None:
        raise ValidationException(f"督办批次 {batch_no} 不存在")
    items = db.query(PmwbPbSuperviseItem).filter(
        PmwbPbSuperviseItem.batch_id == b.id).all()
    from db.models import PmwbPbFeedback
    feedbacks = db.query(PmwbPbFeedback).filter(PmwbPbFeedback.batch_no == batch_no).all()
    send_total = sum(1 for x in items if x.send_status in ("sent", "dry_run"))
    replied = sum(1 for x in items if x.receipt_status == "received")
    status = "none"
    if send_total and replied >= send_total:
        status = "all"
    elif replied:
        status = "partial"
    elif b.receipt_deadline and K.today().isoformat() > b.receipt_deadline:
        status = "overdue"
    b.receipt_status = status
    db.commit()
    return {
        "batch": {"batch_no": b.batch_no, "team_name": b.team_name, "plan_id": b.plan_id,
                  "dry_run": int(b.dry_run or 0), "item_count": b.item_count,
                  "sent_count": b.sent_count, "skipped_count": b.skipped_count,
                  "receipt_status": status},
        "items": [{"track_id": x.track_id, "ticket_no": x.ticket_no,
                   "receipt_code": x.receipt_code, "send_status": x.send_status,
                   "skip_reason": x.skip_reason, "receipt_status": x.receipt_status,
                   "cooldown_left_h": x.cooldown_left_h,
                   "triggers": K.jload(x.triggered_rules, [])} for x in items],
        "feedbacks": [{"id": f.id, "track_id": f.track_id, "channel": f.channel,
                       "adopt_status": f.adopt_status, "raw_text": f.raw_text,
                       "created_at": K.dt_iso(f.created_at)} for f in feedbacks],
        "receipt_rate": round(replied / send_total, 4) if send_total else 0,
    }
