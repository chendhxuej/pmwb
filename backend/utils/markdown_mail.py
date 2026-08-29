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
    - daily/weekly → 方案A（蓝色渐变头部 + 5格 KPI 条）
    - monthly      → 方案B（紫色渐变头部 + 6格 KPI 卡片 + 进度条）
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
            # 标题取区间之前的部分
            title = title_part[: m.start()].strip() or "工作汇报"
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
        html = _render_scheme_b(title=title, subtitle=f"👤 {person_name} &nbsp;·&nbsp; 统计区间：{period}",
                                type_tag=type_label, period=period,
                                kpi=kpi_data, progress=kpi_data.get("progress", []),
                                inner=inner_html)
    else:
        html = _render_scheme_a(title=title, subtitle=f"👤 {person_name} &nbsp;·&nbsp; 统计区间：{period}",
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
    """方案A：蓝调商务风（日报/周报）"""
    blue = "#165dff"
    kpi_items = [
        ("本周交付", kpi.get("delivered", "0"), "target", ""),
        ("新增需求", kpi.get("added", "0"), "added", ""),
        ("高敏工单", kpi.get("high_sensitivity", "0"), "high", "P0/P1"),
        ("会议场次", kpi.get("meeting", "0"), "meeting", ""),
        ("待办完成率", kpi.get("todo_rate", "0%"), "rate", ""),
    ]
    kpi_cells = "".join(
        f'<div class="kpi-item"><div class="kpi-num{kpi_cell_class(v)}">{v}</div>'
        f'<div class="kpi-label">{l}</div><div class="kpi-sub">{s}</div></div>'
        for l, v, _, s in kpi_items
    )
    return f'''<div style="max-width:820px;width:100%;margin:0 auto;font-family:-apple-system,'Microsoft YaHei',Arial,sans-serif;">
<div style="background:linear-gradient(135deg,{blue} 0%,#308ffd 100%);padding:24px 20px 20px;color:#fff;">
<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;">
<div><div style="font-size:15px;font-weight:700;opacity:0.9;">📋 PMWB 个人工作台</div>
<div style="font-size:11px;opacity:0.7;margin-top:2px;">产品经理工作总结 · 自动生成</div></div>
<div style="display:flex;gap:5px;align-items:center;">
<span style="background:rgba(255,255,255,0.2);color:#fff;padding:3px 10px;border-radius:5px;font-size:11px;font-weight:600;">{type_tag}</span>
<span style="background:rgba(255,255,255,0.15);color:rgba(255,255,255,0.9);padding:3px 8px;border-radius:5px;font-size:10px;">{period}</span>
</div>
</div>
<div style="font-size:20px;font-weight:800;letter-spacing:-0.5px;margin-bottom:4px;text-align:center;">{title}</div>
<div style="font-size:12px;opacity:0.85;text-align:center;">{subtitle}</div>
</div>
<div style="display:grid;grid-template-columns:repeat(5,1fr);border-bottom:1px solid #f0f2f5;">{kpi_cells}</div>
<div style="background:#fff;border-radius:0 0 12px 12px;box-shadow:0 4px 24px rgba(0,0,0,0.08);overflow:hidden;">
{inner}
<div style="padding:14px 28px;background:#fafbfc;border-top:1px solid #f0f2f5;font-size:11px;color:#c0c4cc;display:flex;justify-content:space-between;">
<span>🏢 PMWB · 产品经理个人工作台</span>
<span>本邮件由系统自动生成，请勿直接回复</span>
</div>
</div>
</div>'''


def _render_scheme_b(title: str, subtitle: str, type_tag: str, period: str, kpi: dict, progress: list, inner: str) -> str:
    """方案B：紫调仪表盘风（月报）"""
    purple = "#722ed1"
    kpi_items = [
        ("需求交付", kpi.get("delivered", "0"), "#165dff", "目标25项"),
        ("高敏工单", kpi.get("high_sensitivity", "0"), "#f53f3f", "未闭环"),
        ("待办完成率", kpi.get("todo_rate", "0%"), "#00b42a", ""),
        ("重点工作", kpi.get("kw_active", "0"), purple, "进行中"),
        ("会议场次", kpi.get("meeting", "0"), "#165dff", ""),
        ("知识沉淀", kpi.get("added", "0"), "#00b42a", "较上月"),
    ]
    kpi_cells = "".join(
        f'<div class="dash-cell"><div class="dash-num" style="color:{c};font-size:28px;font-weight:800;line-height:1;">{v}</div>'
        f'<div class="dash-label" style="font-size:12px;color:#86909c;margin-top:6px;">{l}</div>'
        f'<div class="dash-sub" style="font-size:11px;color:#c0c4cc;margin-top:2px;">{s}</div>'
        f'<div class="mini-bar" style="height:4px;background:#f0f0f0;border-radius:2px;margin-top:8px;overflow:hidden;">'
        f'<div class="fill" style="height:100%;width:72%;background:{c};border-radius:2px;"></div></div></div>'
        for l, v, c, s in kpi_items
    )
    prog_html = ""
    if progress:
        prog_html = '<div class="progress-section" style="padding:14px 28px;background:#fafbff;border-bottom:1px solid #f0f0f0;">'
        prog_html += '<div class="prog-title" style="font-size:13px;color:#4e5969;font-weight:600;margin-bottom:10px;">📈 本月各模块目标达成进度</div>'
        for p in progress:
            prog_html += f'<div class="prog-row" style="display:flex;align-items:center;gap:10px;margin-bottom:7px;">'
            prog_html += f'<span class="prog-name" style="font-size:12px;color:#86909c;width:80px;">{p["name"]}</span>'
            prog_html += f'<div class="prog-bar" style="flex:1;height:8px;background:#e8e9ef;border-radius:4px;overflow:hidden;">'
            prog_html += f'<div class="prog-fill" style="height:100%;width:{p["pct"]}%;background:{p["color"]};border-radius:4px;"></div></div>'
            prog_html += f'<span class="prog-pct" style="font-size:12px;font-weight:700;width:36px;text-align:right;color:{p["color"]};">{p["pct"]}%</span></div>'
        prog_html += '</div>'

    return f'''<div style="max-width:820px;width:100%;margin:0 auto;font-family:-apple-system,'Microsoft YaHei',Arial,sans-serif;">
<div style="background:linear-gradient(135deg,{purple} 0%,#9064d9 100%);padding:24px 20px 20px;color:#fff;">
<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;">
<div><div style="font-size:15px;font-weight:700;opacity:0.9;">📊 PMWB 个人工作台</div>
<div style="font-size:11px;opacity:0.7;margin-top:2px;">产品经理工作总结 · 自动生成</div></div>
<div style="display:flex;gap:5px;align-items:center;">
<span style="background:rgba(255,255,255,0.2);color:#fff;padding:3px 10px;border-radius:5px;font-size:11px;font-weight:600;">{type_tag}</span>
<span style="background:rgba(255,255,255,0.15);color:rgba(255,255,255,0.9);padding:3px 8px;border-radius:5px;font-size:10px;">{period}</span>
</div>
</div>
<div style="font-size:20px;font-weight:800;letter-spacing:-0.5px;margin-bottom:4px;text-align:center;">{title}</div>
<div style="font-size:12px;opacity:0.85;text-align:center;">{subtitle}</div>
</div>
<div style="display:grid;grid-template-columns:repeat(3,1fr);border-bottom:1px solid #f0f0f0;">{kpi_cells}</div>
{prog_html}
<div style="background:#fff;border-radius:0 0 12px 12px;box-shadow:0 4px 24px rgba(0,0,0,0.08);overflow:hidden;">
{inner}
<div style="padding:14px 28px;background:#fafbfc;border-top:1px solid #f0f0f0;font-size:11px;color:#c0c4cc;display:flex;justify-content:space-between;">
<span>🏢 PMWB · 产品经理个人工作台</span>
<span>本邮件由系统自动生成，请勿直接回复</span>
</div>
</div>
</div>'''


def _kpi_cell_class(v: str) -> str:
    """根据KPI数值返回样式类名（ok=绿色，warn=红色，空=默认）。"""
    if v and v.replace("%", "").replace(",", "").isdigit():
        num = float(v.replace("%", ""))
        if num > 80: return ' ok'
        if num < 50: return ' warn'
    return ''


def _render_dual_overview(html_str: str) -> str:
    """将 Part A 工作成效 / Part B 待改进问题的双段式概述转换为两栏 HTML 布局。"""
    import re as _re
    pattern = (
        r'<h2[^>]*>Part\s+A\s+工作成效</h2>(.*?)'
        r'<h2[^>]*>Part\s+B\s+待改进问题</h2>(.*?)'
        r'(?=<h2|</div>$)'
    )
    m = _re.search(pattern, html_str, _re.DOTALL)
    if not m:
        return html_str
    col_a_content = m.group(1).strip()
    col_b_content = m.group(2).strip()
    dual_div = (
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;'
        'padding:20px 28px;border-bottom:1px solid #f0f2f5;">'
        '<div style="background:linear-gradient(135deg,#f0f7ff 0%,#e8f3ff 100%);'
        'border:1px solid #c7ddff;border-radius:10px;padding:16px;">'
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">'
        '<div style="width:28px;height:28px;border-radius:8px;'
        'background:#165dff;color:#fff;display:flex;align-items:center;'
        'justify-content:center;font-size:14px;font-weight:700;">✓</div>'
        '<div style="font-size:14px;font-weight:700;color:#165dff;">工作成效</div>'
        '</div>'
        f'{col_a_content}'
        '</div>'
        '<div style="background:linear-gradient(135deg,#fff7f0 0%,#fff0e8 100%);'
        'border:1px solid #ffccc7;border-radius:10px;padding:16px;">'
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">'
        '<div style="width:28px;height:28px;border-radius:8px;'
        'background:#f53f3f;color:#fff;display:flex;align-items:center;'
        'justify-content:center;font-size:14px;font-weight:700;">!</div>'
        '<div style="font-size:14px;font-weight:700;color:#f53f3f;">待改进问题</div>'
        '</div>'
        f'{col_b_content}'
        '</div>'
        '</div>'
    )
    replacement = dual_div
    html_str = _re.sub(pattern, replacement, html_str, flags=_re.DOTALL)
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
