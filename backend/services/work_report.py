"""工作总结服务：生成/查询/编辑/删除/定稿归档/发送。"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.exceptions import ValidationException
from db.models import PmwbWorkReport
from services.report_collector import ReportDataCollector
from services.report_llm import generate_report_markdown, render_rule_template, build_next_period_section
from services.report_prompt import build_system_prompt, build_user_message
from utils.email import EmailCenterClient
from utils.markdown_mail import markdown_to_email_html
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
        "gen_used_llm": r.gen_used_llm or 0,
        "gen_model": r.gen_model,
        "gen_notice": r.gen_notice,
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


def _has_next_period(content: str, report_type: str) -> bool:
    """判断 LLM 输出是否已包含下期重点计划小节。"""
    _markers = {
        "daily": "明日关注",
        "weekly": "下周重点计划",
        "monthly": "下月重点工作与趋势研判",
        "custom": "下阶段重点",
    }
    return _markers.get(report_type, "下阶段重点") in (content or "")


def _ensure_sections(data: Dict[str, Any], md: str, report_type: str) -> str:
    """保证 LLM 输出包含所有必备小节（防止偶发漏模块），缺失则补占位说明。"""
    required = [
        ("一、本期概述", "本期概述"),
        ("二、重点工作", "重点工作"),
        ("三、需求与交付", "需求与交付"),
        ("四、运营支撑", "运营支撑"),
        ("五、会议与协同", "会议与协同"),
        ("六、个人待办", "个人待办"),
        ("七、知识中心", "知识中心"),
    ]
    out = md or ""
    for title, marker in required:
        if marker not in out:
            out = out.rstrip() + f"\n\n## {title}\n（本期暂无相关数据与进展，建议补充）\n"
    return out


def _strip_next_period(md: str, report_type: str) -> str:
    """剥离 LLM 输出中自带的「下期重点计划」小节，便于用确定性按模块版覆盖。

    提示词强制 LLM 将第八章标题固定写作 `## 八、...`，因此优先按固定编号标题
    `## 八、` 定位并截断（最稳健）；若 LLM 未严格遵循编号，再回退到按类型标记词
    （如「下周重点计划」）剥离，避免 LLM 自带版与确定性版叠成两章。
    """
    text = md or ""
    # 优先按固定编号标题剥离
    idx = text.find("\n## 八、")
    if idx == -1:
        idx = text.find("## 八、")  # 文档开头情形
    if idx != -1:
        return text[:idx].rstrip()
    # 回退：按类型标记词剥离
    _m = {
        "daily": "明日关注",
        "weekly": "下周重点计划",
        "monthly": "下月重点工作与趋势研判",
        "custom": "下阶段重点",
    }.get(report_type, "下阶段重点")
    idx2 = text.find(_m)
    if idx2 == -1:
        return text
    line_start = text.rfind("\n", 0, idx2) + 1
    return text[:line_start].rstrip()


def generate_report(db: Session, params: Dict[str, Any]) -> Dict[str, Any]:
    report_type = params.get("report_type", "daily")
    ds = params.get("date_start")
    de = params.get("date_end")
    start, end = _date_range(report_type, ds, de)
    data = ReportDataCollector(db).collect(start, end)
    data["report_type"] = report_type
    system = build_system_prompt(report_type)
    user = build_user_message(data, report_type)
    md, used_llm, provider_name, notice = generate_report_markdown(db, system, user)
    if not md:
        md = render_rule_template(data, report_type)
    else:
        # LLM 负责「一~七」深度内容；下期重点计划统一用确定性按模块版，
        # 保证「对标本期进展 + 结构稳定」，不依赖 LLM 自觉
        md = _strip_next_period(md, report_type)
        md = _ensure_sections(data, md, report_type)
        md = md.rstrip() + "\n\n" + build_next_period_section(data, report_type)
    title = f"{_type_label(report_type)}（{start.isoformat()}~{end.isoformat()}）"
    r = PmwbWorkReport(
        report_type=report_type, title=title, content=md,
        date_start=start, date_end=end, status="draft",
    )
    r.gen_used_llm = 1 if used_llm else 0
    r.gen_model = provider_name or ""
    r.gen_notice = notice or ""
    db.add(r)
    db.commit()
    db.refresh(r)
    return {**to_out(r), "used_llm": bool(used_llm), "provider_name": provider_name, "llm_notice": notice}


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
    raw_body = req.get("body") or r.content or ""
    # 正文为 Markdown，统一转换为带样式 HTML（含统一签名）后再以 html 格式发送，
    # 保证收件人收到的邮件是排版后的 HTML 而非原始 Markdown 文本
    html_body = markdown_to_email_html(raw_body)
    client = EmailCenterClient()
    try:
        result = client.send_email(
            to=to_emails, subject=subject, body=html_body,
            body_format="html", cc=cc_emails or None, raise_on_error=False,
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
