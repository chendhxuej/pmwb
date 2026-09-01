"""督办邮件服务。

按场景选模版 + 注入工单完整信息 + 调统一邮件中心发送。
发送失败降级（不 500），仅记 Error 日志。
"""

import logging
from typing import Any, Optional

from services.mail_dispatch import dispatch_email
from utils.email import email_client

logger = logging.getLogger("pmwb.supervise")


def _render_and_send(
    scene: str,
    template_data: dict[str, Any],
    recipients: list[str],
    attachments: Optional[list] = None,
) -> dict:
    """按场景选督办模版 → 解析收件人邮箱 → 走统一邮件治理门面发信。

    模板渲染统一交给 3210 服务端（按 type 渲染），签名注入由门面完成。

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
        subject="",  # 由模版渲染产出
        scene=scene_key,
        variables=template_data,
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


def supervise_ticket(
    scene: str,
    ticket: dict[str, Any],
    recipients: list[str],
) -> dict:
    """发送工单督办邮件（含工单完整信息）。

    Args:
        scene: "sync" | "urge"
        ticket: 工单信息（含 no, title, type, owner, due, status, desc, source 等）
        recipients: 负责人姓名列表

    Returns:
        {"ok": True, ...} | {"ok": False, "error": ...}
    """
    desc_text = (
        ticket.get("situation_desc")
        or ticket.get("description")
        or ticket.get("desc")
        or ""
    )
    template_data = {
        "no": ticket.get("issue_no") or ticket.get("no") or "",
        "title": ticket.get("title") or "",
        "type": ticket.get("issue_type") or ticket.get("category") or "",
        "owner": ticket.get("handler") or ticket.get("owner") or "",
        "due": ticket.get("due") or ticket.get("plan_end") or "",
        "status": ticket.get("status") or "",
        "source": ticket.get("source") or "",
        "desc": desc_text,
    }
    # 自动带出运营工单挂靠的全部附件：清单注入正文 + 真实文件作为邮件附件
    issue_id = ticket.get("issue_id")
    att_metas = ticket.get("attachments") or []
    att_section = ""
    real_atts = []
    if issue_id is not None and att_metas:
        from utils.operation_attachment import build_operation_attachment_block
        att_section, real_atts = build_operation_attachment_block(issue_id, att_metas)
    if att_section:
        full_desc = (desc_text + "\n\n" + att_section) if desc_text else att_section
        # 双写 desc/description：兼容 3210 supervise 模板变量名（模板用 {{{description}}}，历史传 desc）
        template_data["desc"] = full_desc
        template_data["description"] = full_desc
    return _render_and_send(scene, template_data, recipients, attachments=real_atts)


def supervise_action(
    scene: str,
    action: dict[str, Any],
    recipients: list[str],
) -> dict:
    """发送会议行动项督办邮件（含行动项完整信息）。

    Args:
        scene: "sync" | "urge"
        action: 行动项（含 meeting_title, content, owner, due, status 等）
        recipients: 负责人姓名列表

    Returns:
        {"ok": True, ...} | {"ok": False, "error": ...}
    """
    template_data = {
        "no": action.get("id") or "",
        "title": action.get("content") or action.get("title") or "",
        "type": "会议行动项",
        "owner": action.get("owner") or "",
        "due": action.get("due_date") or action.get("due") or "",
        "status": action.get("status") or "",
        "source": action.get("meeting_title") or "",
        "desc": action.get("content") or "",
    }
    return _render_and_send(scene, template_data, recipients)
