"""统一邮件治理门面（Mail Dispatch Facade）。

职责：
1. 场景注册表：每个发邮件触点声明 body_format / email_type / source / 是否加签名；
2. 正文治理：html 场景统一走 Markdown→HTML（utils.markdown_mail），text 场景追加纯文本签名；
3. 统一签名：默认注入 settings.EMAIL_SIGNATURE；
4. 统一落库：写入 email_records（与现有日志/追溯体系对齐）；
5. 统一降级：邮件中心不可用时返回 {ok:False} 而非抛异常，由调用方决定。

收件人解析（姓名/邮箱/中台解析）由各调用方负责，门面只管「正文格式化 + 签名 + 落库 + 发信」，
保持职责单一、低风险。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from core.config import settings
from db.models import EmailRecord
from utils.email import EmailCenterClient
from utils.markdown_mail import markdown_to_email_html

logger = logging.getLogger("pmwb.mail_dispatch")


@dataclass
class MailScene:
    key: str
    body_format: str = "html"          # html | text
    email_type: str = ""               # 写入 EmailRecord.email_type
    source: str = "pmwb"               # 写入 EmailRecord.source
    add_signature: bool = True


# 场景注册表：所有发邮件触点在此声明统一样式/签名/类型，后续触点逐步迁入
SCENES: dict[str, MailScene] = {
    "meeting_notice": MailScene("meeting_notice", body_format="html", email_type="meeting_notice", source="pmwb_meeting"),
    "meeting_minutes": MailScene("meeting_minutes", body_format="html", email_type="meeting_minutes", source="pmwb_meeting"),
    "action_dispatch": MailScene("action_dispatch", body_format="html", email_type="action_dispatch", source="pmwb_meeting"),
    "action_supervise": MailScene("action_supervise", body_format="html", email_type="action_supervise", source="pmwb_supervise"),
    "task_reminder": MailScene("task_reminder", body_format="html", email_type="task_reminder", source="pmwb_task"),
    "requirement_reminder": MailScene("requirement_reminder", body_format="html", email_type="requirement_reminder", source="pmwb_reminder"),
}


def get_scene(key: str) -> MailScene:
    return SCENES.get(key, MailScene(key))


def _format_body(
    body: str,
    body_format: str,
    add_signature: bool,
    signature: Optional[str],
) -> str:
    if body_format == "html":
        return markdown_to_email_html(body, inject_signature=add_signature, signature=signature)
    # text 场景：纯文本追加签名
    final = body or ""
    if add_signature:
        sig = signature if signature is not None else settings.EMAIL_SIGNATURE
        if sig:
            final = final.rstrip() + "\n\n" + sig
    return final


def dispatch_email(
    *,
    db: Optional[Session] = None,
    to: list[str],
    subject: str,
    body: str,
    scene: str = "",
    body_format: Optional[str] = None,
    cc: Optional[list[str]] = None,
    email_type: Optional[str] = None,
    source: Optional[str] = None,
    req_id: Optional[str] = None,
    req_name: Optional[str] = None,
    add_signature: Optional[bool] = None,
    signature: Optional[str] = None,
    raise_on_error: bool = False,
) -> dict:
    """统一发信入口。

    返回 {"success": bool, "record_id": int|None, "message": str, "body_format": str}。
    邮件中心不可用时默认降级返回 success=False（raise_on_error=True 则抛出）。
    """
    sc = get_scene(scene) if scene else None
    fmt = body_format or (sc.body_format if sc else "html")
    sig_on = add_signature if add_signature is not None else (sc.add_signature if sc else True)
    etype = email_type or (sc.email_type if sc else "")
    src = source or (sc.source if sc else "pmwb")

    to_list = [str(t).strip() for t in (to or []) if str(t).strip()]
    cc_list = [str(c).strip() for c in (cc or []) if str(c).strip()]

    final_body = _format_body(body, fmt, sig_on, signature)

    record = None
    if db is not None:
        record = EmailRecord(
            req_id=req_id,
            req_name=req_name,
            email_type=etype or None,
            recipient=",".join(to_list),
            recipient_name=",".join(to_list),
            subject=subject,
            content=final_body,
            send_status="pending",
            source=src,
            sender="pmwb",
        )
        db.add(record)
        db.commit()
        db.refresh(record)

    ok = True
    message = "邮件发送成功"
    try:
        EmailCenterClient().send_email(
            to=to_list,
            subject=subject,
            body=final_body,
            body_format=fmt,
            cc=cc_list or None,
            email_type=etype or None,
            raise_on_error=True,
        )
        if record:
            record.send_status = "success"
    except Exception as exc:  # noqa: BLE001
        ok = False
        message = f"邮件发送失败：{exc}"
        logger.warning("dispatch_email 失败 scene=%s: %s", scene, exc)
        if record:
            record.send_status = "failed"
            record.error_msg = str(exc)
        if raise_on_error:
            if record:
                db.commit()
            raise

    if db is not None and record is not None:
        db.commit()
        db.refresh(record)

    return {
        "success": ok,
        "record_id": record.id if record else None,
        "message": message,
        "body_format": fmt,
    }
