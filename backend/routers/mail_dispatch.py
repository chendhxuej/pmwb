"""邮件统一治理层路由：提供正文预览与统一发送端点。

预览（/preview）与发送（/send）共用 services.mail_dispatch._render_mail，保证「预览即实发」。
"""
from __future__ import annotations

import html
import logging

from fastapi import APIRouter, Depends

from core.config import settings
from core.exceptions import ValidationException
from core.response import success
from db.base import get_db
from services.mail_dispatch import dispatch_email, _render_mail
from utils.email import EmailCenterClient
from utils.markdown_mail import inject_signature_inline, markdown_to_email_html
from utils.validators import split_and_validate_emails

logger = logging.getLogger("pmwb.mail_dispatch_router")

router = APIRouter(prefix="/mail-dispatch", tags=["邮件治理"])


def _resolve_recipients(raw_list: list) -> list[str]:
    """将收件人列表中的姓名解析为邮箱地址；已是邮箱的保持不变。

    统一发送端点接受姓名和邮箱混合输入，通过邮件中心通讯录解析姓名→邮箱。
    解析失败的姓名原样保留，后续邮箱格式校验会给出明确提示。
    """
    if not raw_list:
        return []
    emails: list[str] = []
    names: list[str] = []
    for addr in raw_list:
        s = addr.strip() if isinstance(addr, str) else str(addr).strip()
        if not s:
            continue
        if "@" in s:
            emails.append(s)
        else:
            names.append(s)
    if names:
        try:
            client = EmailCenterClient()
            resolved = client.resolve_contact_emails(names)
            for name in names:
                email = resolved.get(name)
                if email:
                    emails.append(email)
                else:
                    emails.append(name)  # 保留原名，校验时会报错提示
        except Exception as exc:  # noqa: BLE001
            logger.warning("收件人姓名解析失败，原样传递: %s", exc)
            emails.extend(names)
    return emails


@router.post("/preview")
def preview_email(req: dict):
    """渲染邮件正文 HTML 供前端实时预览。

    新调用（统一场景）：{ scene, to?, cc?, subject?, variables? | rawContent? | body?, htmlPassthrough?, templateId?, templateData?, add_signature? }
    兼容旧调用（仅 Markdown 预览）：{ body, body_format?"html", add_signature?true }
    """
    scene = req.get("scene")
    if scene:
        out = _render_mail(
            scene=scene,
            variables=req.get("variables"),
            raw_content=req.get("rawContent") or req.get("body"),
            subject=req.get("subject"),
            html_passthrough=req.get("htmlPassthrough", False),
            template_id=req.get("templateId"),
            template_data=req.get("templateData"),
            add_signature=req.get("add_signature", True),
        )
        return success(data={"html": out["html"], "subject": out["subject"], "body_format": out["body_format"]})

    # 兼容旧调用：纯 Markdown 预览
    body = req.get("body") or ""
    fmt = req.get("body_format") or "html"
    add_sig = req.get("add_signature", True)
    if fmt == "html":
        rendered = markdown_to_email_html(body, inject_signature=add_sig)
    else:
        rendered = (
            f'<div style="white-space:pre-wrap;font-family:inherit;margin:0;">'
            f"{html.escape(body)}</div>"
        )
        if add_sig:
            rendered = inject_signature_inline(rendered, settings.EMAIL_SIGNATURE)
    return success(data={"html": rendered, "body_format": fmt})


@router.post("/send")
def send_email_endpoint(req: dict, db=Depends(get_db)):
    """统一发送端点（全场景收口入口）。

    请求体：{ to, cc?, subject?, scene?, rawContent?|body?, variables?, templateId?,
             templateData?, req_id?, req_name?, htmlPassthrough? }
    返回 core.response.success 包装的 dispatch_email 结果。
    """
    to_raw = req.get("to") or []
    cc_raw = req.get("cc")
    if isinstance(to_raw, str):
        to_raw = [to_raw]
    if isinstance(cc_raw, str):
        cc_raw = [cc_raw]

    # 统一端点兼容姓名输入：先解析姓名→邮箱，再校验邮箱格式
    resolved_to = _resolve_recipients(to_raw)
    resolved_cc = _resolve_recipients(cc_raw) if cc_raw else None

    bad: list[str] = []
    for addr in resolved_to:
        _, invalid = split_and_validate_emails(addr)
        bad.extend(invalid)
    if resolved_cc:
        for addr in resolved_cc:
            _, invalid = split_and_validate_emails(addr)
            bad.extend(invalid)
    if bad:
        raise ValidationException(
            "收件人邮箱格式不正确：" + "、".join(bad)
            + "。请填写真实邮箱（可在统一邮件中心通讯录按姓名查询）。"
        )

    res = dispatch_email(
        db=db,
        to=resolved_to,
        cc=resolved_cc,
        subject=req.get("subject"),
        scene=req.get("scene") or "",
        raw_content=req.get("rawContent") or req.get("body"),
        variables=req.get("variables"),
        template_id=req.get("templateId"),
        template_data=req.get("templateData"),
        req_id=req.get("req_id"),
        req_name=req.get("req_name"),
        html_passthrough=req.get("htmlPassthrough", False),
    )
    return success(data=res)
