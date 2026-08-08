"""工作总结服务：生成/查询/编辑/删除/定稿归档/发送。"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.exceptions import ValidationException
from db.models import PmwbWorkReport
from services.report_collector import ReportDataCollector
from services.report_llm import generate_report_markdown, render_rule_template
from services.report_prompt import build_system_prompt, build_user_message
from utils.email import EmailCenterClient
from utils.master_service import master_service_client
from utils.obsidian import sanitize_filename, write_markdown
from utils.validators import validate_email_strict

logger = logging.getLogger(__name__)

REPORT_TYPE_LABELS = {"daily": "日报", "weekly": "周报", "monthly": "月报", "custom": "自定义"}
STATUS_LABELS = {"draft": "草稿", "finalized": "已定稿", "sent": "已发送"}
OBSIDIAN_ROOT = "15-工作总结"


def _type_label(rt: str) -> str:
    return REPORT_TYPE_LABELS.get(rt, rt or "日报")


def _status_label(s: str) -> str:
    return STATUS_LABELS.get(s, s or "草稿")


def to_out(r: PmwbWorkReport) -> Dict[str, Any]:
    return {
        "id": r.id,
        "report_type": r.report_type,
        "report_type_label": _type_label(r.report_type),
        "title": r.title,
        "content": r.content,
        "date_start": r.date_start.isoformat() if r.date_start else None,
        "date_end": r.date_end.isoformat() if r.date_end else None,
        "status": r.status,
        "status_label": _status_label(r.status),
        "recipient": r.recipient,
        "cc": r.cc,
        "obsidian_path": r.obsidian_path,
        "finalized_at": r.finalized_at.isoformat() if r.finalized_at else None,
        "sent_at": r.sent_at.isoformat() if r.sent_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _date_range(report_type: str, ds: Optional[date], de: Optional[date]):
    today = date.today()
    end = de or today
    if ds:
        return ds, end
    if report_type == "weekly":
        start = end - timedelta(days=6)
    elif report_type == "monthly":
        start = end.replace(day=1)
    else:  # daily / custom
        start = end
    return start, end


def list_reports(db: Session, status: Optional[str] = None) -> List[Dict[str, Any]]:
    q = db.query(PmwbWorkReport)
    if status:
        q = q.filter(PmwbWorkReport.status == status)
    rows = q.order_by(PmwbWorkReport.created_at.desc()).all()
    return [to_out(r) for r in rows]


def get_report(db: Session, report_id: int) -> Dict[str, Any]:
    r = db.query(PmwbWorkReport).filter(PmwbWorkReport.id == report_id).first()
    if not r:
        raise ValidationException("报告不存在")
    return to_out(r)


def create_report(db: Session, data: Dict[str, Any]) -> Dict[str, Any]:
    r = PmwbWorkReport(
        report_type=data.get("report_type", "daily"),
        title=data.get("title"),
        content=data.get("content"),
        date_start=data.get("date_start"),
        date_end=data.get("date_end"),
        status="draft",
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return to_out(r)


def update_report(db: Session, report_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    r = db.query(PmwbWorkReport).filter(PmwbWorkReport.id == report_id).first()
    if not r:
        raise ValidationException("报告不存在")
    if r.status != "draft":
        raise ValidationException("仅草稿状态可编辑")
    for key in ("title", "content", "date_start", "date_end", "report_type"):
        if key in data and data[key] is not None:
            setattr(r, key, data[key])
    db.commit()
    db.refresh(r)
    return to_out(r)


def delete_report(db: Session, report_id: int) -> None:
    r = db.query(PmwbWorkReport).filter(PmwbWorkReport.id == report_id).first()
    if not r:
        raise ValidationException("报告不存在")
    db.delete(r)
    db.commit()


def generate_report(db: Session, params: Dict[str, Any]) -> Dict[str, Any]:
    report_type = params.get("report_type", "daily")
    ds = params.get("date_start")
    de = params.get("date_end")
    start, end = _date_range(report_type, ds, de)
    data = ReportDataCollector(db).collect(start, end)
    system = build_system_prompt(report_type)
    user = build_user_message(data, report_type)
    md, _used_llm = generate_report_markdown(system, user)
    if not md:
        md = render_rule_template(data)
    title = f"{_type_label(report_type)}（{start.isoformat()}~{end.isoformat()}）"
    r = PmwbWorkReport(
        report_type=report_type, title=title, content=md,
        date_start=start, date_end=end, status="draft",
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return to_out(r)


def _archive_to_obsidian(r: PmwbWorkReport) -> str:
    type_label = _type_label(r.report_type)
    day = (r.date_end or r.created_at or datetime.now()).strftime("%Y-%m-%d")
    fname = sanitize_filename(f"{day}.md")
    rel = f"{OBSIDIAN_ROOT}/{type_label}/{fname}"
    front = [
        "---",
        f"title: {r.title or type_label}",
        f"type: {type_label}",
        f"date_start: {r.date_start.isoformat() if r.date_start else ''}",
        f"date_end: {r.date_end.isoformat() if r.date_end else ''}",
        f"finalized_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "source: PMWB-AI总结",
        "---",
        "",
    ]
    content = "".join(front) + (r.content or "")
    write_markdown(rel, content)
    return rel


def finalize_report(db: Session, report_id: int) -> Dict[str, Any]:
    r = db.query(PmwbWorkReport).filter(PmwbWorkReport.id == report_id).first()
    if not r:
        raise ValidationException("报告不存在")
    if r.status != "draft":
        raise ValidationException("仅草稿状态可定稿（已定稿/已发送的报告不可重复定稿）")
    r.status = "finalized"
    r.finalized_at = datetime.now()
    # 归档 Obsidian（失败不阻断定稿）
    try:
        r.obsidian_path = _archive_to_obsidian(r)
    except Exception as e:  # noqa: BLE001
        logger.warning("定稿归档 Obsidian 失败（不阻断）: %s", e)
        r.error_msg = f"archive: {e}"
    db.commit()
    db.refresh(r)
    return to_out(r)


def _resolve_recipients(raw_list: List[str]):
    emails: List[str] = []
    unresolved: List[str] = []
    for item in raw_list or []:
        item = (item or "").strip()
        if not item:
            continue
        if validate_email_strict(item):
            emails.append(item)
        else:
            resolved = master_service_client.resolve_staff_emails([item])
            mail = resolved.get(item)
            if mail:
                emails.append(mail)
            else:
                unresolved.append(item)
    note = ""
    if unresolved:
        note = f"以下名称未在人员中台解析到邮箱，已忽略：{', '.join(unresolved)}"
    return emails, note


def send_report(db: Session, report_id: int, req: Dict[str, Any]) -> Dict[str, Any]:
    r = db.query(PmwbWorkReport).filter(PmwbWorkReport.id == report_id).first()
    if not r:
        raise ValidationException("报告不存在")
    to_raw = req.get("to") or []
    cc_raw = req.get("cc") or []
    to_emails, to_note = _resolve_recipients(to_raw)
    cc_emails, cc_note = _resolve_recipients(cc_raw)
    notes = [n for n in (to_note, cc_note) if n]
    if not to_emails:
        raise ValidationException("没有可用的收件人邮箱（姓名需能在人员中台解析）")
    subject = req.get("subject") or r.title or "工作总结"
    body = req.get("body") or r.content or ""
    client = EmailCenterClient()
    try:
        result = client.send_email(
            to=to_emails, subject=subject, body=body,
            body_format="text", cc=cc_emails or None, raise_on_error=False,
        )
    except Exception as e:  # noqa: BLE001
        r.error_msg = f"send: {e}"
        db.commit()
        raise ValidationException(f"邮件发送失败：{e}")

    ok = True
    if isinstance(result, dict):
        ok = result.get("ok", True) is not False
    if not ok:
        r.error_msg = f"send: {result.get('error') if isinstance(result, dict) else result}"
        db.commit()
        raise ValidationException(f"邮件发送失败：{r.error_msg}")

    r.status = "sent"
    r.sent_at = datetime.now()
    r.recipient = ", ".join(to_emails)
    r.cc = ", ".join(cc_emails) if cc_emails else None
    if notes:
        r.error_msg = " | ".join(notes)
    db.commit()
    db.refresh(r)
    return to_out(r)
