"""督办邮件服务。

按场景装配正文 + 注入工单完整信息 + 调统一邮件治理门面发信。
发送失败降级（不 500），仅记 Error 日志。

2026-09-07 改造（预览/正文不更新 + 不换行 + 字段空白 修复）：
- 正文改由 PMWB 装配器渲染（utils.mail_content），不再依赖 3210 模板变量；
- 变量名对齐 utils.mail_content.SCENE_FIELDS（category/handler/resolveDate/description），
  修复原 type/owner/due/desc 与模板错配导致的字段空白；
- 工单描述为纯文本，经 Markdown 段落渲染保留换行（原来原样塞进 HTML 不换行）；
- extra_msg（前端留言）此前后端接收后从未使用，现注入正文「补充说明」段；
- 新增 render_supervise_preview()，与发送共用同一装配链路，保证「预览即实发」。
"""

import logging
from typing import Any, Optional

from services.mail_dispatch import _render_mail, dispatch_email
from utils.email import email_client
from utils.mail_content import default_body_md

logger = logging.getLogger("pmwb.supervise")


def _compose_body_md(
    scene_key: str,
    fields: dict[str, Any],
    body_md: Optional[str] = None,
    extra_msg: Optional[str] = None,
) -> str:
    """生成 Markdown 正文：优先用调用方/前端编辑的正文，否则按字段 schema 生成。

    extra_msg（留言）追加为「补充说明」段落——历史上该字段被后端丢弃。
    """
    md = body_md if (body_md and body_md.strip()) else default_body_md(scene_key, fields)
    if extra_msg and extra_msg.strip():
        md = (md + "\n\n" if md else "") + f"### 补充说明\n\n{extra_msg.strip()}"
    return md


def _render_and_send(
    scene: str,
    fields: dict[str, Any],
    recipients: list[str],
    *,
    body_md: Optional[str] = None,
    extra_msg: Optional[str] = None,
    extra_html: str = "",
    attachments: Optional[list] = None,
) -> dict:
    """装配正文 → 解析收件人邮箱 → 走统一邮件治理门面发信。

    Returns:
        {"ok": True, "subject": ..., "body": ...}
        {"ok": False, "error": "..."}
    """
    scene_key = "supervise_" + scene
    if scene_key not in ("supervise_sync", "supervise_urge"):
        return {"ok": False, "error": f"未知的督办场景: {scene}"}

    # 解析收件人邮箱
    resolved = email_client.resolve_contact_emails(recipients)
    to_emails = [v for v in resolved.values() if v]
    if not to_emails:
        logger.warning("督办邮件收件人邮箱全部为空: recipients=%s, resolved=%s", recipients, resolved)
        return {"ok": False, "error": "无法解析收件人邮箱"}

    result = dispatch_email(
        to=to_emails,
        scene=scene_key,
        fields=fields,
        raw_content=_compose_body_md(scene_key, fields, body_md, extra_msg),
        extra_html=extra_html,
        recipient_name="、".join([r for r in (recipients or []) if r]),
        attachments=attachments,
        raise_on_error=False,
        confirm_send=True,
    )
    if not result.get("success"):
        logger.warning("督办邮件发送失败: %s", result.get("message"))
        return {"ok": False, "error": result.get("message", "发送失败")}

    return {
        "ok": True,
        "subject": result.get("subject", ""),
        "body": result.get("rendered_body", ""),
    }


def render_supervise_preview(
    scene: str,
    fields: dict[str, Any],
    *,
    body_md: Optional[str] = None,
    extra_msg: Optional[str] = None,
    extra_html: str = "",
    recipients: Optional[list[str]] = None,
) -> dict:
    """只渲染不发送：与 _render_and_send 共用装配链路，保证「预览即实发」。

    Returns:
        {"ok": True, "subject": ..., "html": ...}
    """
    scene_key = "supervise_" + scene
    if scene_key not in ("supervise_sync", "supervise_urge"):
        return {"ok": False, "error": f"未知的督办场景: {scene}"}
    try:
        out = _render_mail(
            scene=scene_key,
            fields=fields,
            raw_content=_compose_body_md(scene_key, fields, body_md, extra_msg),
            extra_html=extra_html,
            recipient_name="、".join([r for r in (recipients or []) if r]),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("督办邮件预览渲染失败: %s", exc)
        return {"ok": False, "error": f"预览渲染失败：{exc}"}
    return {"ok": True, "subject": out.get("subject", ""), "html": out.get("html", "")}


def build_ticket_fields(ticket: dict[str, Any]) -> dict[str, Any]:
    """工单信息 → 邮件字段（key 对齐 utils.mail_content.SCENE_FIELDS）。

    变量名从旧的 type/owner/due/desc 修正为 category/handler/resolveDate/description，
    修复「类型 / 处理人 / 计划完成日期 / 问题描述 恒空」的问题。
    """
    return {
        "no": ticket.get("issue_no") or ticket.get("no") or "",
        "title": ticket.get("title") or "",
        "category": ticket.get("category") or ticket.get("issue_type") or "",
        "handler": ticket.get("handler") or ticket.get("owner") or "",
        # 计划完成日期：优先上游装配好的 due，其次各类工单的计划/上线日期列名
        # （运营工单 go_live_date、开发工单 planned_finish_date、需求 version_required_date）
        "resolveDate": (
            ticket.get("due")
            or ticket.get("plan_end")
            or ticket.get("go_live_date")
            or ticket.get("planned_finish_date")
            or ticket.get("version_required_date")
            or ""
        ),
        "status": ticket.get("status") or "",
        "description": (
            ticket.get("situation_desc")
            or ticket.get("description")
            or ticket.get("desc")
            or ""
        ),
    }


def build_action_fields(action: dict[str, Any], scene: str) -> dict[str, Any]:
    """会议行动项 → 邮件字段（对齐 action_supervise schema）。"""
    return {
        "content": action.get("content") or action.get("title") or "",
        "owner": action.get("owner") or "",
        "dueDate": action.get("due_date") or action.get("due") or "",
        "status": action.get("status") or "",
        "sceneLabel": "催办" if scene == "urge" else "同步",
    }


def collect_attachment_block(ticket: dict[str, Any]) -> tuple[str, list]:
    """工单挂靠附件 → (正文附件清单 HTML, 真实附件列表)。

    预览与发送共用，保证「预览即实发」。
    """
    issue_id = ticket.get("issue_id")
    att_metas = ticket.get("attachments") or []
    if issue_id is not None and att_metas:
        from utils.operation_attachment import build_operation_attachment_block
        return build_operation_attachment_block(issue_id, att_metas)
    return "", []


def supervise_ticket(
    scene: str,
    ticket: dict[str, Any],
    recipients: list[str],
    *,
    extra_msg: Optional[str] = None,
    body_md: Optional[str] = None,
) -> dict:
    """发送工单督办邮件（含工单完整信息 + 挂靠附件）。

    Args:
        scene: "sync" | "urge"
        ticket: 工单信息（含 issue_no, title, category, handler, due, status, situation_desc 等）
        recipients: 负责人姓名列表
        extra_msg: 补充说明（前端留言），注入正文「补充说明」段
        body_md: 前端编辑的 Markdown 正文；为空时按字段自动生成

    Returns:
        {"ok": True, ...} | {"ok": False, "error": "..."}
    """
    fields = build_ticket_fields(ticket)

    # 自动带出运营工单挂靠的全部附件：清单注入正文 + 真实文件作为邮件附件
    att_section, real_atts = collect_attachment_block(ticket)

    return _render_and_send(
        scene,
        fields,
        recipients,
        body_md=body_md,
        extra_msg=extra_msg,
        extra_html=att_section,
        attachments=real_atts,
    )


def supervise_action(
    scene: str,
    action: dict[str, Any],
    recipients: list[str],
    *,
    extra_msg: Optional[str] = None,
    body_md: Optional[str] = None,
) -> dict:
    """发送会议行动项督办邮件（含行动项完整信息）。"""
    return _render_and_send(
        scene,
        build_action_fields(action, scene),
        recipients,
        body_md=body_md,
        extra_msg=extra_msg,
    )
