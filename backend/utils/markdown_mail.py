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
from bleach.css_sanitizer import CSSSanitizer

from core.config import settings

logger = logging.getLogger("pmwb.markdown_mail")

# 仅使用 markdown 内置扩展，无第三方依赖风险（bleach 为新增显式依赖）
_MD_EXTENSIONS = ["tables", "fenced_code", "sane_lists", "nl2br"]

# 内联样式映射：邮件客户端剥离 <style>，必须用内联 style 才能生效
_TAG_STYLES: dict[str, str] = {
    "h1": "font-size:22px;margin:24px 0 12px;border-bottom:2px solid #165dff;padding-bottom:8px;color:#1d2129;",
    "h2": "font-size:18px;margin:22px 0 10px;padding-bottom:6px;border-bottom:1px solid #e5e6eb;color:#165dff;",
    "h3": "font-size:15px;margin:16px 0 8px;color:#1d2129;font-weight:600;",
    "p": "margin:10px 0;",
    "ul": "margin:10px 0;padding-left:26px;",
    "ol": "margin:10px 0;padding-left:26px;",
    "li": "margin:6px 0;",
    "table": "border-collapse:collapse;margin:12px 0;width:100%;font-size:13px;",
    "th": "border:1px solid #d9dbe2;padding:7px 10px;text-align:left;background:#f2f3f5;font-weight:600;color:#1d2129;",
    "td": "border:1px solid #e5e6eb;padding:7px 10px;text-align:left;vertical-align:top;",
    "code": "background:#f2f3f5;padding:1px 5px;border-radius:3px;font-family:Consolas,Menlo,monospace;font-size:13px;",
    "pre": "background:#f7f8fa;border:1px solid #e5e6eb;border-radius:6px;padding:10px;overflow:auto;",
    "blockquote": "margin:12px 0;padding:10px 14px;border-left:4px solid #165dff;color:#1d2129;background:#f0f5ff;border-radius:0 6px 6px 0;",
    "a": "color:#165dff;text-decoration:none;",
    "strong": "font-weight:600;color:#1d2129;",
    "em": "font-style:italic;",
    "hr": "border:none;border-top:1px solid #e5e6eb;margin:16px 0;",
    "img": "max-width:100%;",
}

_BODY_STYLE = (
    "font-family:-apple-system,'Segoe UI','Microsoft YaHei',Arial,sans-serif;"
    "font-size:14px;line-height:1.75;color:#1f2329;word-break:break-word;"
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
    # 邮件表格兼容性属性（Outlook 等客户端更认 HTML 属性而非 CSS）
    "table": ["cellpadding", "cellspacing", "border", "width", "role"],
    "td": ["width", "valign", "colspan", "rowspan"],
    "th": ["width", "valign", "colspan", "rowspan"],
}

# 邮件正文允许的内联 CSS 属性白名单（邮件客户端剥离 <style>，必须依赖内联样式）
_ALLOWED_CSS_PROPERTIES: frozenset[str] = frozenset({
    "color",
    "background",
    "background-color",
    "background-image",
    "background-size",
    "background-position",
    "background-repeat",
    "background-clip",
    "font",
    "font-family",
    "font-size",
    "font-weight",
    "font-style",
    "font-variant",
    "line-height",
    "text-align",
    "text-decoration",
    "text-indent",
    "vertical-align",
    "white-space",
    "word-break",
    "margin",
    "margin-top",
    "margin-bottom",
    "margin-left",
    "margin-right",
    "padding",
    "padding-top",
    "padding-bottom",
    "padding-left",
    "padding-right",
    "border",
    "border-top",
    "border-bottom",
    "border-left",
    "border-right",
    "border-collapse",
    "border-radius",
    "border-color",
    "border-top-color",
    "border-bottom-color",
    "border-left-color",
    "border-right-color",
    "border-spacing",
    "width",
    "max-width",
    "min-width",
    "height",
    "min-height",
    "box-shadow",
    "overflow",
    "display",
    "list-style",
    "list-style-type",
    "opacity",
})

_CSS_SANITIZER = CSSSanitizer(allowed_css_properties=_ALLOWED_CSS_PROPERTIES)


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


def render_work_report_html(md: str, report_type: str, person_name: str = "") -> str:
    """将工作总结 Markdown 转换为带结构化头部/KPI 条的 HTML 邮件正文。

    按 report_type 分派排版方案：
    - daily/weekly → 方案A（简约商务页眉 + 5格 KPI 条）
    - monthly      → 方案B（简约商务页眉 + 6格 KPI 卡片 + 进度条）
    - 其余         → 降级为通用 markdown_to_email_html

    头部信息从 md 第一行提取 H1 标题；若无则自动生成。
    """
    from datetime import date as _date
    import re as _re

    # ---- 1. 提取报告元信息 ----
    title = ""
    period = ""
    type_label = ""
    rest_md = md or ""

    # 从第一行 H1 提取标题和区间
    first_line = rest_md.split("\n")[0].strip() if rest_md else ""
    if first_line.startswith("# "):
        title_part = first_line[2:].strip()
        # 格式："工作周报（统计区间：2026-08-25 ~ 2026-08-29）"
        m = _re.search(r"统计区间[：:]\s*(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})", title_part)
        if m:
            period = f"{m.group(1)} ~ {m.group(2)}"
            # 标题取区间之前的部分，并去掉可能残留的左括号
            title = title_part[: m.start()].strip()
            title = _re.sub(r"[\(（]\s*$", "", title).strip()
            if not title:
                title = "工作汇报"
        else:
            title = title_part or "工作汇报"
    if not title:
        type_map = {"daily": "工作日报", "weekly": "工作周报", "monthly": "工作月报", "custom": "专项报告"}
        title = type_map.get(report_type, "工作汇报")
    if not period:
        # 尝试从 ## 一、本期概述 附近提取区间
        for line in rest_md.split("\n"):
            lm = _re.search(r"统计区间[：:]\s*(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})", line)
            if lm:
                period = f"{lm.group(1)} ~ {lm.group(2)}"
                break
    if not period:
        period = "—"

    # 类型标签
    type_tag_map = {"daily": ("工作日报", "daily"), "weekly": ("工作周报", "weekly"),
                    "monthly": ("工作月报", "monthly"), "custom": ("专项报告", "custom")}
    type_label, type_key = type_tag_map.get(report_type, ("工作汇报", "custom"))

    # ---- 2. 提取 KPI 数字 ----
    kpi_data = _extract_kpi(rest_md)

    # ---- 3. 渲染内层 Markdown HTML ----
    inner_html = markdown.markdown(rest_md, extensions=_MD_EXTENSIONS)
    inner_html = _sanitize(inner_html)
    inner_html = _apply_inline_styles(inner_html)
    # 过滤掉 H1 标题（已在头部展示），保留其余内容
    inner_html = _re.sub(r"<h1[^>]*>.*?</h1>", "", inner_html, flags=_re.DOTALL | _re.IGNORECASE)
    # ---- 3.5 特殊处理：提取双段式 Part A/B 并渲染为两栏布局 ----
    inner_html = _render_dual_overview(inner_html)

    # ---- 4. 组装方案A/B 外壳 ----
    if report_type == "monthly":
        html = _render_scheme_b(title=title, subtitle=f"汇报人：{person_name} &nbsp;·&nbsp; 统计区间：{period}",
                                type_tag=type_label, period=period,
                                kpi=kpi_data, progress=kpi_data.get("progress", []),
                                inner=inner_html)
    else:
        html = _render_scheme_a(title=title, subtitle=f"汇报人：{person_name} &nbsp;·&nbsp; 统计区间：{period}",
                                type_tag=type_label, period=period,
                                kpi=kpi_data, inner=inner_html)
    return html


def _extract_kpi(md: str) -> dict:
    """从 Markdown 文本中提取关键指标数字（用于 KPI 展示）。"""
    import re as _re
    kpi = {}
    # 提取各类 KPI 数字
    patterns = {
        "delivered": r"交付[：:]\s*(\d+)\s*项",
        "added": r"新增[：:]\s*(\d+)\s*项",
        "high_sensitivity": r"高敏[（(]P0/P1[)）]\s*工单\s*(\d+)\s*条",
        "meeting": r"会议\s*(\d+)\s*场",
        "todo_rate": r"待办完成率\s*(\d+)%",
        "kw_active": r"进行中\s*(\d+)\s*项",
        "kw_overdue": r"逾期\s*(\d+)\s*项",
    }
    for key, pat in patterns.items():
        m = _re.search(pat, md)
        if m:
            kpi[key] = m.group(1)
    return kpi


def _render_scheme_a(title: str, subtitle: str, type_tag: str, period: str, kpi: dict, inner: str) -> str:
    """方案A：简约商务风（日报/周报）。

    设计要点（按 2026-08-29 分析报告整改）：
    - 页眉精简：细蓝色分割线，无大面积蓝色背景块
    - 正文容器：680px 黄金阅读宽度，左右内边距 30px
    - 移除 Web 端统计卡片（KPI 条仅预览使用，邮件正文不显示）
    - 所有样式内联，兼容 Outlook/Foxmail
    """
    blue = "#165dff"
    return f'''<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0;padding:0;background:#ffffff;">
<tr><td align="center" style="padding:20px 0;">
<table width="680" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;">
<!-- 简约商务页眉 -->
<tr>
<td style="padding:0 0 16px 0;border-bottom:2px solid {blue};">
<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td align="left" valign="middle">
<span style="font-size:20px;font-weight:700;color:#1d2129;font-family:'Microsoft YaHei',Arial,sans-serif;">{title}</span>
</td>
<td align="right" valign="middle">
<table cellpadding="0" cellspacing="0" border="0"><tr>
<td style="font-size:12px;color:#86909c;font-family:'Microsoft YaHei',Arial,sans-serif;">{type_tag}</td>
<td width="12"></td>
<td style="font-size:12px;color:#86909c;font-family:'Microsoft YaHei',Arial,sans-serif;">{period}</td>
</tr></table>
</td>
</tr>
<tr>
<td colspan="2" style="padding-top:8px;font-size:12px;color:#86909c;font-family:'Microsoft YaHei',Arial,sans-serif;">{subtitle}</td>
</tr>
</table>
</td>
</tr>
<!-- 邮件正文内容 -->
<tr>
<td style="padding:24px 30px 20px 30px;font-size:14px;line-height:1.75;color:#1f2329;font-family:'Microsoft YaHei',Arial,sans-serif;word-break:break-word;">
{inner}
</td>
</tr>
<!-- 页脚 -->
<tr>
<td style="padding:16px 30px;border-top:1px solid #f0f2f5;font-size:11px;color:#c0c4cc;font-family:'Microsoft YaHei',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td align="left">🏢 PMWB · 产品经理个人工作台</td>
<td align="right">本邮件由系统自动生成，请勿直接回复</td>
</tr>
</table>
</td>
</tr>
</table>
</td></tr></table>'''


def _render_scheme_b(title: str, subtitle: str, type_tag: str, period: str, kpi: dict, progress: list, inner: str) -> str:
    """方案B：简约商务风（月报）。

    设计要点（按 2026-08-29 分析报告整改）：
    - 页眉精简：细紫色分割线，无大面积紫色背景块
    - 正文容器：680px 黄金阅读宽度，左右内边距 30px
    - 移除 Web 端统计卡片（KPI 条仅预览使用，邮件正文不显示）
    - 所有样式内联，兼容 Outlook/Foxmail
    """
    purple = "#722ed1"

    # 进度条HTML（若有）- Outlook兼容：移除border-radius
    prog_html = ""
    if progress:
        prog_html = '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:16px 0 20px 0;background:#fafbff;padding:16px 20px;">'
        prog_html += '<tr><td style="font-size:13px;color:#4e5969;font-weight:600;font-family:\'Microsoft YaHei\',Arial,sans-serif;padding-bottom:10px;">📈 本月各模块目标达成进度</td></tr>'
        for p in progress:
            prog_html += f'<tr><td style="padding:3px 0;font-size:12px;color:#86909c;font-family:\'Microsoft YaHei\',Arial,sans-serif;">{p["name"]}</td>'
            prog_html += f'<td style="padding:3px 10px;"><table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#e8e9ef;"><tr>'
            prog_html += f'<td width="{p["pct"]}%" style="height:8px;font-size:0;line-height:0;background:{p["color"]};">&nbsp;</td>'
            prog_html += f'<td style="height:8px;font-size:0;line-height:0;">&nbsp;</td></tr></table></td>'
            prog_html += f'<td width="45" align="right" style="font-size:12px;font-weight:700;color:{p["color"]};font-family:\'Microsoft YaHei\',Arial,sans-serif;padding:3px 0;">{p["pct"]}%</td></tr>'
        prog_html += '</table>'

    return f'''<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0;padding:0;background:#ffffff;">
<tr><td align="center" style="padding:20px 0;">
<table width="680" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;">
<!-- 简约商务页眉 -->
<tr>
<td style="padding:0 0 16px 0;border-bottom:2px solid {purple};">
<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td align="left" valign="middle">
<span style="font-size:20px;font-weight:700;color:#1d2129;font-family:'Microsoft YaHei',Arial,sans-serif;">{title}</span>
</td>
<td align="right" valign="middle">
<table cellpadding="0" cellspacing="0" border="0"><tr>
<td style="font-size:12px;color:#86909c;font-family:'Microsoft YaHei',Arial,sans-serif;">{type_tag}</td>
<td width="12"></td>
<td style="font-size:12px;color:#86909c;font-family:'Microsoft YaHei',Arial,sans-serif;">{period}</td>
</tr></table>
</td>
</tr>
<tr>
<td colspan="2" style="padding-top:8px;font-size:12px;color:#86909c;font-family:'Microsoft YaHei',Arial,sans-serif;">{subtitle}</td>
</tr>
</table>
</td>
</tr>
<!-- 邮件正文内容 -->
<tr>
<td style="padding:24px 30px 20px 30px;font-size:14px;line-height:1.75;color:#1f2329;font-family:'Microsoft YaHei',Arial,sans-serif;word-break:break-word;">
{inner}
</td>
</tr>
<!-- 进度条（若有） -->
{prog_html}
<!-- 页脚 -->
<tr>
<td style="padding:16px 30px;border-top:1px solid #f0f2f5;font-size:11px;color:#c0c4cc;font-family:'Microsoft YaHei',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td align="left">🏢 PMWB · 产品经理个人工作台</td>
<td align="right">本邮件由系统自动生成，请勿直接回复</td>
</tr>
</table>
</td>
</tr>
</table>
</td></tr></table>'''


def _kpi_cell_class(v: str) -> str:
    """根据KPI数值返回样式类名（ok=绿色，warn=红色，空=默认）。"""
    if v and v.replace("%", "").replace(",", "").isdigit():
        num = float(v.replace("%", ""))
        if num > 80: return ' ok'
        if num < 50: return ' warn'
    return ''


def _render_dual_overview(html_str: str) -> str:
    """将 Part A 工作成效 / Part B 待改进问题的双段式概述转换为两栏 HTML 布局。

    邮件兼容性优化（2026-08-29）：
    - 移除 linear-gradient（Outlook 不支持）→ 改用纯色背景
    - 移除 border-radius（Outlook 不支持）→ 保持直角边框
    - 支持 H2 标题和粗体两种格式（**Part A 工作成效** 或 ## Part A 工作成效）
    - 所有样式内联，使用 table 布局
    """
    import re as _re
    # 兼容两种格式：## Part A 工作成效（H2）或 **Part A 工作成效**（粗体）
    pattern = (
        r'(<h2[^>]*>Part\s+A\s+工作成效</h2>|<strong>Part\s+A\s+工作成效</strong>)'
        r'(.*?)(?=<h2|<strong>|$)'
        r'(<h2[^>]*>Part\s+B\s+待改进问题</h2>|<strong>Part\s+B\s+待改进问题</strong>)'
        r'(.*?)(?=<h2|<strong>|$)'
    )
    m = _re.search(pattern, html_str, _re.DOTALL)
    if not m:
        return html_str
    col_a_content = m.group(2).strip()
    col_b_content = m.group(4).strip()
    # Outlook 兼容：纯色背景 + 直角边框
    dual_table = (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="padding:20px 28px;border-bottom:1px solid #f0f2f5;">'
        '<tr>'
        '<td width="50%" valign="top" style="padding-right:7px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="background:#f0f7ff;border:1px solid #c7ddff;padding:16px;">'
        '<tr>'
        '<td style="padding-bottom:10px;">'
        '<table cellpadding="0" cellspacing="0" border="0">'
        '<tr>'
        '<td style="width:28px;height:28px;background:#165dff;'
        'text-align:center;vertical-align:middle;'
        'font-size:14px;font-weight:700;color:#fff;">✓</td>'
        '<td style="padding-left:8px;font-size:14px;font-weight:700;color:#165dff;">工作成效</td>'
        '</tr>'
        '</table>'
        '</td>'
        '</tr>'
        '<tr><td>' f'{col_a_content}' '</td></tr>'
        '</table>'
        '</td>'
        '<td width="50%" valign="top" style="padding-left:7px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="background:#fff7f0;border:1px solid #ffccc7;padding:16px;">'
        '<tr>'
        '<td style="padding-bottom:10px;">'
        '<table cellpadding="0" cellspacing="0" border="0">'
        '<tr>'
        '<td style="width:28px;height:28px;background:#f53f3f;'
        'text-align:center;vertical-align:middle;'
        'font-size:14px;font-weight:700;color:#fff;">!</td>'
        '<td style="padding-left:8px;font-size:14px;font-weight:700;color:#f53f3f;">待改进问题</td>'
        '</tr>'
        '</table>'
        '</td>'
        '</tr>'
        '<tr><td>' f'{col_b_content}' '</td></tr>'
        '</table>'
        '</td>'
        '</tr>'
        '</table>'
    )
    html_str = _re.sub(pattern, dual_table, html_str, flags=_re.DOTALL)
    return html_str


def _sanitize(html_str: str) -> str:
    """白名单净化，剥离脚本/危险标签与属性（对齐 3210 的 DOMPurify 思路）。

    注意：bleach 6+ 必须显式传入 css_sanitizer 才能保留 style 属性值，
    否则 style 会被清空为空字符串，导致邮件排版错乱。
    """
    return bleach.clean(
        html_str,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        css_sanitizer=_CSS_SANITIZER,
        strip=True,
    )


_SYSTEM_NOTE = "备注：此邮件由产品经理个人工作台（PMWB）触发"


def inject_signature_inline(html_str: str, signature: str | None) -> str:
    """将多行纯文本签名渲染为内联 style 签名块，并在签名上方追加系统说明（上下空行）。"""
    if not signature:
        return html_str
    lines = [ln.strip() for ln in signature.splitlines() if ln.strip()]
    if not lines:
        return html_str
    note = f'<p style="margin:2px 0;">{html.escape(_SYSTEM_NOTE)}</p>'
    spacer = '<p style="margin:2px 0;">&nbsp;</p>'
    inner = "".join(f'<p style="margin:2px 0;">{html.escape(ln)}</p>' for ln in lines)
    sig = (
        f'<div style="margin-top:22px;padding-top:12px;'
        f'border-top:1px solid #e5e6eb;color:#4e5969;'
        f'font-size:13px;line-height:1.6;">'
        f'{note}{spacer}{inner}</div>'
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

kpi_cell_class = _kpi_cell_class
