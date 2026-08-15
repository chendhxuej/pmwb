"""Markdown → 带样式 HTML 邮件正文工具（统一邮件治理层复用）。

所有发邮件触点统一调用本模块把用户/系统生成的 Markdown 正文转换为
带内联样式的 HTML 邮件，并可选注入全局邮件签名，保证各场景排版一致。
"""
from __future__ import annotations

import html
import logging

import markdown

from core.config import settings

logger = logging.getLogger("pmwb.markdown_mail")

# 仅使用 markdown 内置扩展，无第三方依赖风险
_MD_EXTENSIONS = ["tables", "fenced_code", "sane_lists", "nl2br"]

_EMAIL_STYLE = """<style>
.pmwb-mail-body { font-family: -apple-system, "Segoe UI", "Microsoft YaHei", Arial, sans-serif; font-size: 14px; line-height: 1.7; color: #1f2329; word-break: break-word; }
.pmwb-mail-body h1 { font-size: 20px; margin: 18px 0 10px; border-bottom: 1px solid #e5e6eb; padding-bottom: 6px; color: #1d2129; }
.pmwb-mail-body h2 { font-size: 17px; margin: 16px 0 8px; color: #1d2129; }
.pmwb-mail-body h3 { font-size: 15px; margin: 14px 0 6px; color: #1d2129; }
.pmwb-mail-body p { margin: 8px 0; }
.pmwb-mail-body ul, .pmwb-mail-body ol { margin: 8px 0; padding-left: 22px; }
.pmwb-mail-body li { margin: 4px 0; }
.pmwb-mail-body table { border-collapse: collapse; margin: 10px 0; width: 100%; font-size: 13px; }
.pmwb-mail-body th, .pmwb-mail-body td { border: 1px solid #e5e6eb; padding: 6px 10px; text-align: left; }
.pmwb-mail-body th { background: #f2f3f5; font-weight: 600; }
.pmwb-mail-body code { background: #f2f3f5; padding: 1px 5px; border-radius: 3px; font-family: Consolas, Menlo, monospace; font-size: 13px; }
.pmwb-mail-body pre { background: #f7f8fa; border: 1px solid #e5e6eb; border-radius: 6px; padding: 10px; overflow: auto; }
.pmwb-mail-body pre code { background: none; padding: 0; }
.pmwb-mail-body blockquote { margin: 8px 0; padding: 4px 12px; border-left: 3px solid #c9cdd4; color: #4e5969; background: #f7f8fa; }
.pmwb-mail-body a { color: #165dff; text-decoration: none; }
.pmwb-sign { margin-top: 22px; padding-top: 12px; border-top: 1px solid #e5e6eb; color: #4e5969; font-size: 13px; line-height: 1.6; }
.pmwb-sign p { margin: 2px 0; }
</style>"""


def render_signature_html(signature: str | None) -> str:
    """将多行纯文本签名渲染为 HTML 签名块（逐行转义，防止注入）。"""
    if not signature:
        return ""
    lines = [ln.strip() for ln in signature.splitlines() if ln.strip()]
    if not lines:
        return ""
    inner = "".join(f"<p>{html.escape(line)}</p>" for line in lines)
    return f'<div class="pmwb-sign">{inner}</div>'


def markdown_to_email_html(
    md: str,
    *,
    inject_signature: bool = True,
    signature: str | None = None,
) -> str:
    """Markdown 文本 → 带内联样式 + 统一签名的完整 HTML 邮件正文。

    - md 为空时仅返回签名（若有）。
    - 签名默认取自 settings.EMAIL_SIGNATURE，可经 signature 参数覆盖。
    """
    md = md or ""
    try:
        body_html = markdown.markdown(md, extensions=_MD_EXTENSIONS)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Markdown 转换失败，降级为纯文本转义: %s", exc)
        body_html = f"<p>{html.escape(md)}</p>"
    styled = f'<div class="pmwb-mail-body">{body_html}</div>'
    if inject_signature:
        styled += render_signature_html(
            signature if signature is not None else settings.EMAIL_SIGNATURE
        )
    return _EMAIL_STYLE + styled
