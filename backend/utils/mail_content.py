"""统一邮件正文装配器（Mail Content Assembler）。

背景（2026-09-07 改造）：
原先邮件正文由统一邮件中心（3210）的服务端模板渲染，暴露三类硬伤：
1. 模板变量名经常与 PMWB 传入的 variables 错配（如模板要 category/handler/resolveDate，
   代码传 type/owner/due），导致字段大面积空白；
2. 3210 模板无 PUT/PATCH 更新接口，模板改不动、宽度只能用 widen_frame 事后打补丁；
3. 前端左侧 Markdown 编辑区的内容放在 variables.body，而绝大多数模板没有 body 变量，
   用户在编辑区改的内容被静默丢弃（"改了不生效"）。

改造后：**正文一律由 PMWB 渲染，3210 退化为发信通道**（MAIL_USE_3210_SHELL 可回切）。
本模块是唯一的正文明细装配入口，输出结构统一：

    4px 品牌色带 → 主标题 → 称呼 → 引导语 → 结构化字段表 → Markdown 正文

签名档由 services.mail_dispatch 统一注入（inject_signature_inline），本模块不重复添加，
避免落款重复。

宽度铁律：幽灵单元格 90% 居中（外层 100% + align="center"，内层 width 90%），
**禁止 max-width:Npx;margin:0 auto**（Outlook 忽略 → 偏左，Foxmail 固定窄列）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Any, Optional

import markdown as markdown_lib

from utils.markdown_mail import (
    _MD_EXTENSIONS,
    _apply_inline_styles,
    _sanitize,
)

__all__ = [
    "MailField",
    "SCENE_META",
    "SCENE_FIELDS",
    "get_scene_fields",
    "get_scene_meta",
    "markdown_fragment",
    "text_to_html",
    "render_greeting",
    "default_body_md",
    "build_mail_body",
    "render_task_center_section",
]


# ---------------------------------------------------------------------------
# 字段 Schema
# ---------------------------------------------------------------------------
@dataclass
class MailField:
    """邮件字段表单项。

    key:       变量名（与 values 字典对应）
    label:     展示/表格标签
    type:      text | date | select | textarea
    options:   select 可选项（[{label, value}] 或字符串列表）
    editable:  是否允许在发送前编辑
    in_body:   True 表示该字段作为 Markdown 正文段落（默认正文生成时使用）
    """

    key: str
    label: str
    type: str = "text"
    options: list = field(default_factory=list)
    editable: bool = True
    in_body: bool = False


def _f(key: str, label: str, **kw) -> MailField:
    return MailField(key=key, label=label, **kw)


# 各场景元信息：主标题 / 品牌色 / 引导语
# 品牌色沿用项目既有口径：日报周报 #165dff、月报 #722ed1、督办类 #f53f3f。
SCENE_META: dict[str, dict[str, str]] = {
    "supervise_urge": {
        "title": "催办通知",
        "brand_color": "#f53f3f",
        "intro": "以下工单需要尽快推进，详情如下：",
    },
    "supervise_sync": {
        "title": "工单进展同步",
        "brand_color": "#165dff",
        "intro": "以下工单最新进展同步如下，请知悉。",
    },
    "action_supervise": {
        "title": "会议行动项督办",
        "brand_color": "#f53f3f",
        "intro": "以下会议行动项请尽快推进，详情如下：",
    },
    "action_dispatch": {
        "title": "会议行动项派发",
        "brand_color": "#165dff",
        "intro": "现将本次会议的行动项派发如下，请及时跟进。",
    },
    "task_reminder": {
        "title": "任务督办提醒",
        "brand_color": "#f53f3f",
        "intro": "以下任务请关注并及时处理：",
    },
    "requirement_reminder": {
        "title": "需求催办通知",
        "brand_color": "#f53f3f",
        "intro": "以下需求请尽快处理并反馈进展：",
    },
    "task_center_notify": {
        "title": "任务同步通知",
        "brand_color": "#165dff",
        "intro": "现将相关任务同步如下，请知悉。",
    },
    "task_center_urge": {
        "title": "任务催办提醒",
        "brand_color": "#f53f3f",
        "intro": "以下任务已临近或超过截止时间，请尽快处理：",
    },
    "meeting_notice": {
        "title": "会议通知",
        "brand_color": "#165dff",
        "intro": "现通知如下会议安排，请准时参加。",
    },
    "meeting_minutes": {
        "title": "会议纪要",
        "brand_color": "#165dff",
        "intro": "现将本次会议纪要同步如下，请知悉。",
    },
    "keywork_feedback": {
        "title": "周反馈请求",
        "brand_color": "#165dff",
        "intro": "请按以下要求反馈本周工作进展。",
    },
}

_TICKET_FIELDS = [
    _f("no", "工单编号"),
    _f("title", "标题"),
    _f("category", "类型"),
    _f("handler", "处理人"),
    _f("resolveDate", "计划完成日期", type="date"),
    _f("status", "当前状态"),
    _f("description", "问题描述", type="textarea", in_body=True),
]

SCENE_FIELDS: dict[str, list[MailField]] = {
    "supervise_urge": list(_TICKET_FIELDS),
    "supervise_sync": list(_TICKET_FIELDS),
    "action_supervise": [
        _f("content", "行动项内容", type="textarea", in_body=True),
        _f("owner", "负责人"),
        _f("dueDate", "截止日期", type="date"),
        _f("status", "当前状态"),
        _f("sceneLabel", "类型"),
    ],
    "action_dispatch": [
        _f("meetingTitle", "会议主题"),
        _f("actions", "行动项清单", type="textarea", in_body=True),
    ],
    "task_reminder": [
        _f("taskTitle", "任务名称"),
        _f("assignee", "负责人"),
        _f("planEnd", "计划完成时间", type="date"),
        _f("status", "当前状态"),
    ],
    "requirement_reminder": [
        _f("reqId", "需求编号"),
        _f("reqName", "需求名称"),
        _f("saName", "SA"),
        _f("proposeTime", "提出时间", type="date"),
        _f("items", "需求清单", type="textarea", in_body=True),
    ],
    "task_center_notify": [
        _f("tasks", "任务清单", type="task_list", in_body=True),
    ],
    "task_center_urge": [
        _f("tasks", "任务清单", type="task_list", in_body=True),
    ],
    "meeting_notice": [
        _f("meetingTopic", "会议主题"),
        _f("meetingTime", "会议时间"),
        _f("meetingLocation", "会议地点"),
        _f("host", "主持人"),
        _f("body", "会议说明", type="textarea", in_body=True),
    ],
    "meeting_minutes": [
        _f("meetingTitle", "会议主题"),
        _f("meetingDate", "会议日期", type="date"),
        _f("attendees", "参会人"),
        _f("content", "纪要正文", type="textarea", in_body=True),
        _f("actionItems", "行动项", type="textarea", in_body=True),
    ],
    "keywork_feedback": [
        _f("work_no", "重点工作编号"),
        _f("title", "重点工作"),
        _f("assignee", "负责人"),
        _f("week", "周次"),
        _f("body", "反馈要求", type="textarea", in_body=True),
    ],
}


def get_scene_fields(scene: str) -> list[MailField]:
    return SCENE_FIELDS.get(scene, [])


def get_scene_meta(scene: str) -> dict[str, str]:
    return SCENE_META.get(scene, {"title": "", "brand_color": "#165dff", "intro": ""})


def scene_schema(scene: str) -> list[dict]:
    """场景字段 schema（供前端渲染表单，GET /mail-dispatch/scenes 返回）。"""
    return [
        {
            "key": f.key,
            "label": f.label,
            "type": f.type,
            "options": f.options,
            "editable": f.editable,
            "inBody": f.in_body,
        }
        for f in get_scene_fields(scene)
    ]


# ---------------------------------------------------------------------------
# 渲染工具
# ---------------------------------------------------------------------------
def markdown_fragment(md: str) -> str:
    """Markdown → 内联样式 HTML **片段**（不含 680px 外壳、不含签名）。

    装配器自己用幽灵表格控制宽度，直接复用 markdown_to_email_html 会套一层
    max-width:680px 的 div，与外层 90% 表格叠加形成"双层窄"，故此处只取片段。
    """
    md = md or ""
    try:
        html_str = markdown_lib.markdown(md, extensions=_MD_EXTENSIONS)
    except Exception:  # noqa: BLE001
        html_str = f"<p>{escape(md)}</p>"
    html_str = _sanitize(html_str)
    return _apply_inline_styles(html_str)


def text_to_html(text: str) -> str:
    """纯文本 → 保留换行的 HTML（工单描述等纯文本字段专用）。

    这是"邮件正文不换行"的根因修复：纯文本 \n 直接插进 HTML 不会换行，
    必须先转义再逐行转 <br>。
    """
    if not text:
        return ""
    escaped = escape(str(text))
    lines = escaped.split("\n")
    return "<br>".join(lines)


def render_greeting(recipient_name: Optional[str] = None) -> str:
    """生成称呼：单人「X 您好，」；多人/未知「各位同事，」。"""
    raw = (recipient_name or "").strip()
    if not raw:
        return "各位同事，"
    # 顿号/逗号/分号分隔视为多人
    names = [n.strip() for n in raw.replace("，", "、").replace(",", "、").split("、") if n.strip()]
    if len(names) >= 2:
        return "各位同事，"
    name = names[0]
    # 已含"您好"不重复添加
    if "您好" in name:
        return name if name.endswith("，") or name.endswith(",") else name + "，"
    return f"{name} 您好，"


def default_body_md(scene: str, values: dict) -> str:
    """按字段 schema 生成默认 Markdown 正文（前端未编辑正文时使用）。

    只取 in_body=True 的字段（问题描述 / 清单 / 纪要正文等），生成
    `### 标签\n内容` 段落，保证字段改了正文也跟着变。
    """
    parts: list[str] = []
    for f in get_scene_fields(scene):
        if not f.in_body:
            continue
        val = (values or {}).get(f.key)
        if val is None or str(val).strip() == "":
            continue
        parts.append(f"### {f.label}\n\n{val}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# 任务中心专用装配（2026-09-07）
# ---------------------------------------------------------------------------
def render_task_center_section(tasks: list[dict], send_type: str = "urge") -> str:
    """结构化任务列表 → Markdown 段（每条 = H3 标题 + 字段表 + 工单内容）。

    任务中心邮件的硬伤（不连贯 / 详情缺失 / 批量不完整）由本函数根治：
    - 不再依赖前端硬编码问候或 buildTaskListHtml 的 `<ul>` 拼接
    - 每条任务独占一段（H3 + 字段表 + 工单内容），空 description 优雅跳过
    - 超期红色标记、临期橙色标记
    - 由 build_mail_body 自动纳入正文（in_body=True 等价效果），无需前端感知

    输入每个 task dict 的字段：
        title, source_label, owner, due_date, status_label,
        priority, description (str, \n 保留), is_overdue, is_due_soon,
        source_url (预留字段字段可暂未使用), index (1-based)

    返回 Markdown 字符串，由 build_mail_body 经 markdown_fragment 渲染为 HTML。
    """
    if not tasks:
        return ""

    blocks: list[str] = []
    for t in tasks:
        idx = t.get("index") or (len(blocks) + 1)
        title = (t.get("title") or "（无标题）").strip()
        # 超期/临期标记
        badge = ""
        if t.get("is_overdue"):
            badge = " <span style=\"color:#f53f3f;font-weight:600;\">【超期】</span>"
        elif t.get("is_due_soon"):
            badge = " <span style=\"color:#ff7d00;font-weight:600;\">【临期】</span>"
        heading = f"### {idx}. {title}{badge}" if badge else f"### {idx}. {title}"

        # 字段表（5 列：来源 / 负责人 / 截止 / 状态 / 优先级）
        cells = [
            str(t.get("source_label") or "—"),
            str(t.get("owner") or "未分配"),
            str(t.get("due_date") or "未设定"),
            str(t.get("status_label") or "—"),
            str(t.get("priority") or "—"),
        ]
        field_table = (
            "| 来源 | 负责人 | 截止 | 状态 | 优先级 |\n"
            "| --- | --- | --- | --- | --- |\n"
            f"| {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} | {cells[4]} |"
        )

        parts = [heading, "", field_table]
        desc = (t.get("description") or "").strip()
        if desc:
            parts.extend(["", "**工单内容**：", "", desc])
        blocks.append("\n".join(parts))

    return "\n\n---\n\n".join(blocks)


def _render_fields_table(scene: str, values: dict) -> str:
    """结构化字段表（表格项 = 非 in_body 字段）。"""
    rows: list[str] = []
    for f in get_scene_fields(scene):
        if f.in_body:
            continue
        val = (values or {}).get(f.key)
        if val is None or str(val).strip() == "":
            continue
        rows.append(
            '<tr>'
            f'<td width="110" style="padding:8px 10px;border:1px solid #e5e6eb;'
            f'background:#f7f8fa;color:#4e5969;font-weight:600;font-size:14px;">'
            f'{escape(f.label)}</td>'
            f'<td style="padding:8px 10px;border:1px solid #e5e6eb;color:#1d2129;'
            f'font-size:14px;word-break:break-word;">{text_to_html(str(val))}</td>'
            '</tr>'
        )
    if not rows:
        return ""
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="border-collapse:collapse;margin:16px 0;font-size:14px;">'
        f'{"".join(rows)}</table>'
    )


# ---------------------------------------------------------------------------
# 主装配入口
# ---------------------------------------------------------------------------
def build_mail_body(
    *,
    scene: str,
    fields: Optional[dict] = None,
    body_md: Optional[str] = None,
    recipient_name: Optional[str] = None,
    brand_color: Optional[str] = None,
    title: Optional[str] = None,
    intro: Optional[str] = None,
    extra_html: str = "",
) -> str:
    """装配完整邮件正文 HTML（不含签名，签名由门面统一注入）。

    Args:
        scene: 场景 key（决定标题/品牌色/引导语/字段 schema）
        fields: 字段值 dict（key 对应 SCENE_FIELDS）
        body_md: Markdown 正文；为空时按 in_body 字段自动生成
        recipient_name: 收件人姓名（多人自动降级为"各位同事，"）
        brand_color / title / intro: 覆盖场景默认
        extra_html: 追加的 HTML 片段（如工单附件清单），插在正文之后

    Returns:
        完整 HTML 字符串（幽灵单元格 90% 居中）
    """
    meta = get_scene_meta(scene)
    values = dict(fields or {})
    color = brand_color or meta.get("brand_color", "#165dff")
    head_title = title if title is not None else meta.get("title", "")
    lead = intro if intro is not None else meta.get("intro", "")

    # 正文 = 调用方/用户编辑的 Markdown + 未出现在其中的 in_body 字段段落。
    # 为什么是拼接而非二选一：任务中心等场景正文只是一句引导语，任务清单在 tasks 字段里，
    # 若二选一会直接丢掉清单；而去重判断可避免工单描述在正文中重复出现两次。
    md = (body_md or "").strip()

    # task_center_* 专用装配（2026-09-07）：当 fields.tasks 是结构化列表时
    # 走 render_task_center_section，输出每条任务的 H3+字段表+工单内容。
    # 兼容旧调用方：tasks 是 str（HTML）时保持原 auto_parts 拼接。
    tc_skip_keys: set[str] = set()
    if scene in ("task_center_notify", "task_center_urge"):
        tasks_val = (values or {}).get("tasks")
        if isinstance(tasks_val, list) and tasks_val:
            send_type = "urge" if "urge" in scene else "notify"
            section_md = render_task_center_section(tasks_val, send_type)
            if section_md:
                if section_md.strip() not in md:
                    md = (md + "\n\n" if md else "") + section_md
            # 标记跳过通用 in_body 拼接，避免重复出现 "### 任务清单"
            tc_skip_keys.add("tasks")

    auto_parts: list[str] = []
    for f in get_scene_fields(scene):
        if not f.in_body:
            continue
        if f.key in tc_skip_keys:
            continue
        val = (values or {}).get(f.key)
        if val is None or not str(val).strip():
            continue
        sval = str(val).strip()
        if sval in md:  # 正文已包含该内容，跳过避免重复
            continue
        auto_parts.append(f"### {f.label}\n\n{sval}")
    if auto_parts:
        md = (md + "\n\n" if md else "") + "\n\n".join(auto_parts)
    body_html = markdown_fragment(md)

    blocks: list[str] = []
    if head_title:
        blocks.append(
            f'<h2 style="margin:0 0 14px;font-size:20px;color:#1d2129;'
            f'font-weight:600;">{escape(head_title)}</h2>'
        )
    blocks.append(
        f'<p style="margin:0 0 10px;font-size:14px;color:#1d2129;">'
        f'{escape(render_greeting(recipient_name))}</p>'
    )
    if lead:
        blocks.append(
            f'<p style="margin:0 0 4px;font-size:14px;color:#4e5969;">{escape(lead)}</p>'
        )
    fields_table = _render_fields_table(scene, values)
    if fields_table:
        blocks.append(fields_table)
    if body_html:
        blocks.append(f'<div style="font-size:14px;color:#1d2129;">{body_html}</div>')
    if extra_html:
        blocks.append(extra_html)

    inner = "".join(blocks)

    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="background:#f5f7fa;padding:16px 0;">'
        '<tr><td align="center">'
        f'<table width="90%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background:#ffffff;border:1px solid #e5e6eb;border-radius:6px;'
        f'font-family:-apple-system,&#39;Segoe UI&#39;,&#39;Microsoft YaHei&#39;,Arial,sans-serif;">'
        f'<tr><td style="background:{escape(color)};height:4px;font-size:0;'
        f'line-height:0;border-radius:6px 6px 0 0;">&nbsp;</td></tr>'
        f'<tr><td style="padding:22px 26px;line-height:1.75;">{inner}</td></tr>'
        '</table>'
        '</td></tr>'
        '</table>'
    )
