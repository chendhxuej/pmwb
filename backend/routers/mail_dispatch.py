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
from utils.markdown_mail import inject_signature_inline, markdown_to_email_html
from utils.validators import split_and_validate_emails

logger = logging.getLogger("pmwb.mail_dispatch_router")

router = APIRouter(prefix="/mail-dispatch", tags=["邮件治理"])


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

    bad: list[str] = []
    for addr in to_raw:
        _, invalid = split_and_validate_emails(addr)
        bad.extend(invalid)
    if cc_raw:
        for addr in cc_raw:
            _, invalid = split_and_validate_emails(addr)
            bad.extend(invalid)
    if bad:
        raise ValidationException(
            "收件人邮箱格式不正确：" + "、".join(bad)
            + "。请填写真实邮箱（可在统一邮件中心通讯录按姓名查询）。"
        )

    res = dispatch_email(
        db=db,
        to=req.get("to") or [],
        cc=req.get("cc"),
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
