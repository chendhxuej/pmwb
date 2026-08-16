"""Markdown → 带内联样式 HTML 邮件正文工具（统一邮件治理层复用）。

所有发邮件触点统一调用本模块把用户/系统生成的 Markdown 正文转换为
带内联样式的 HTML 邮件，并可选注入全局邮件签名，保证各场景排版一致。

设计要点（2026-08-16 整改）：
- 邮件客户端会剥离 <style>/<head>，因此正文样式必须**内联**到每个标签（_apply_inline_styles）；
- 正文经 bleach 白名单净化，杜绝 Markdown 透传原始 HTML 带来的注入隐患；
- 签名用 inject_signature_inline 以**内联 style** 拼接（逐行 html.escape 防注入），
  与 3210 渲染产出的 HTML 风格一致，预览即实发。
"""
from __future__ import annotations

import html
import logging
import re

import bleach
import markdown

from core.config import settings

logger = logging.getLogger("pmwb.markdown_mail")

# 仅使用 markdown 内置扩展，无第三方依赖风险（bleach 为新增显式依赖）
_MD_EXTENSIONS = ["tables", "fenced_code", "sane_lists", "nl2br"]

# 内联样式映射：邮件客户端剥离 <style>，必须用内联 style 才能生效
_TAG_STYLES: dict[str, str] = {
    "h1": "font-size:20px;margin:18px 0 10px;border-bottom:1px solid #e5e6eb;padding-bottom:6px;color:#1d2129;",
    "h2": "font-size:17px;margin:16px 0 8px;color:#1d2129;",
    "h3": "font-size:15px;margin:14px 0 6px;color:#1d2129;",
    "p": "margin:8px 0;",
    "ul": "margin:8px 0;padding-left:22px;",
    "ol": "margin:8px 0;padding-left:22px;",
    "li": "margin:4px 0;",
    "table": "border-collapse:collapse;margin:10px 0;width:100%;font-size:13px;",
    "th": "border:1px solid #e5e6eb;padding:6px 10px;text-align:left;background:#f2f3f5;font-weight:600;",
    "td": "border:1px solid #e5e6eb;padding:6px 10px;text-align:left;",
    "code": "background:#f2f3f5;padding:1px 5px;border-radius:3px;font-family:Consolas,Menlo,monospace;font-size:13px;",
    "pre": "background:#f7f8fa;border:1px solid #e5e6eb;border-radius:6px;padding:10px;overflow:auto;",
    "blockquote": "margin:8px 0;padding:4px 12px;border-left:3px solid #c9cdd4;color:#4e5969;background:#f7f8fa;",
    "a": "color:#165dff;text-decoration:none;",
    "strong": "font-weight:600;",
    "em": "font-style:italic;",
    "hr": "border:none;border-top:1px solid #e5e6eb;margin:12px 0;",
    "img": "max-width:100%;",
}

_BODY_STYLE = (
    "font-family:-apple-system,'Segoe UI','Microsoft YaHei',Arial,sans-serif;"
    "font-size:14px;line-height:1.7;color:#1f2329;word-break:break-word;"
)

_ALLOWED_TAGS = [
    "p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "b", "em", "i", "u", "s", "span", "div",
    "a", "img", "ul", "ol", "li", "blockquote", "code", "pre",
    "table", "thead", "tbody", "tr", "th", "td",
]
_ALLOWED_ATTRS = {
    "*": ["style"],
    "a": ["href", "title", "target"],
    "img": ["src", "alt", "width", "height"],
}


def _apply_inline_styles(html_str: str) -> str:
    """为常见标签注入内联 style（已带 style 的标签不覆盖）。"""
    def repl(m: re.Match) -> str:
        tag = m.group(1).lower()
        attrs = m.group(2) or ""
        style = _TAG_STYLES.get(tag)
        if style is None:
            return m.group(0)
        if re.search(r"\bstyle\s*=", attrs, re.IGNORECASE):
            return m.group(0)
        new_attrs = f' style="{style}"' + (f" {attrs.strip()}" if attrs.strip() else "")
        return f"<{m.group(1)}{new_attrs}>"
    return re.sub(r"<([a-zA-Z0-9]+)([^>]*)>", repl, html_str)


def _sanitize(html_str: str) -> str:
    """白名单净化，剥离脚本/危险标签与属性（对齐 3210 的 DOMPurify 思路）。"""
    return bleach.clean(html_str, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)


def inject_signature_inline(html_str: str, signature: str | None) -> str:
    """将多行纯文本签名渲染为内联 style 签名块（逐行转义，防止注入）。"""
    if not signature:
        return html_str
    lines = [ln.strip() for ln in signature.splitlines() if ln.strip()]
    if not lines:
        return html_str
    inner = "".join(f'<p style="margin:2px 0;">{html.escape(ln)}</p>' for ln in lines)
    sig = (
        f'<div style="margin-top:22px;padding-top:12px;'
        f'border-top:1px solid #e5e6eb;color:#4e5969;'
        f'font-size:13px;line-height:1.6;">{inner}</div>'
    )
    return html_str + sig


def markdown_to_email_html(
    md: str,
    *,
    inject_signature: bool = True,
    signature: str | None = None,
) -> str:
    """Markdown 文本 → 带内联样式 + 统一签名的完整 HTML 邮件正文。

    - md 为空时仅返回签名（若有）。
    - 正文经 bleach 净化，签名默认取自 settings.EMAIL_SIGNATURE，可经 signature 覆盖。
    """
    md = md or ""
    try:
        body_html = markdown.markdown(md, extensions=_MD_EXTENSIONS)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Markdown 转换失败，降级为纯文本转义: %s", exc)
        body_html = f"<p>{html.escape(md)}</p>"
    # 1. 先白名单净化，剥离脚本/危险标签与属性
    body_html = _sanitize(body_html)
    # 2. 再注入内联样式（bleach 无 css_sanitizer 时会清空 style 属性，故顺序在后）
    body_html = _apply_inline_styles(body_html)
    styled = f'<div style="{_BODY_STYLE}">{body_html}</div>'
    if inject_signature:
        styled = inject_signature_inline(
            styled, signature if signature is not None else settings.EMAIL_SIGNATURE
        )
    return styled


def render_signature_html(signature: str | None) -> str:
    """兼容保留：旧 class 式签名块（新代码请改用 inject_signature_inline）。"""
    if not signature:
        return ""
    lines = [ln.strip() for ln in signature.splitlines() if ln.strip()]
    if not lines:
        return ""
    inner = "".join(f"<p>{html.escape(line)}</p>" for line in lines)
    return f'<div class="pmwb-sign">{inner}</div>'
