"""邮件统一治理层路由：提供正文预览（Markdown→HTML，含签名）等辅助端点。"""
from __future__ import annotations

import html
import logging

from fastapi import APIRouter

from core.config import settings
from core.response import success
from utils.markdown_mail import markdown_to_email_html

logger = logging.getLogger("pmwb.mail_dispatch_router")

router = APIRouter(prefix="/mail-dispatch", tags=["邮件治理"])


@router.post("/preview")
def preview_email(req: dict):
    """将邮件正文（Markdown 或纯文本）渲染为带样式 + 签名的 HTML，供前端实时预览。

    请求体：{ body, body_format?"html"|"text", add_signature?true }
    """
    body = req.get("body") or ""
    fmt = req.get("body_format") or "html"
    add_sig = req.get("add_signature", True)

    if fmt == "html":
        rendered = markdown_to_email_html(body, inject_signature=add_sig)
    else:
        sig = settings.EMAIL_SIGNATURE if add_sig else ""
        sig_block = f'<div class="pmwb-sign"><p>{"</p><p>".join(html.escape(s) for s in sig.splitlines() if s.strip())}</p></div>' if sig else ""
        rendered = (
            f'<div class="pmwb-mail-body"><pre style="white-space:pre-wrap;'
            f'font-family:inherit;margin:0;">{html.escape(body)}</pre></div>{sig_block}'
        )
    return success(data={"html": rendered, "body_format": fmt})
