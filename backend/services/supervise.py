"""督办邮件服务。

按场景选模版 + 注入工单完整信息 + 调统一邮件中心发送。
发送失败降级（不 500），仅记 Error 日志。
"""

import logging
from typing import Any

from utils.email import email_client, proxy_client

logger = logging.getLogger("pmwb.supervise")

# 邮件中心默认模版类型 → 由 sup-1 种子数据创建
TEMPLATE_TYPE_MAP = {
    "sync": "ticket_sync",
    "urge": "ticket_urge",
}


def _render_and_send(
    scene: str,
    template_data: dict[str, Any],
    recipients: list[str],
) -> dict:
    """按场景选模版 → 渲染 → 解析收件人邮箱 → 发送。

    Returns:
        {"ok": True, "subject": ..., "body": ...}
        {"ok": False, "error": "..."}
    """
    tpl_type = TEMPLATE_TYPE_MAP.get(scene)
    if not tpl_type:
        return {"ok": False, "error": f"未知的督办场景: {scene}"}

    # 1. 获取该类型默认模版 ID
    try:
        tpls_resp = proxy_client.request(
            "GET",
            "/api/templates",
            params={"type": tpl_type},
        )
    except Exception as exc:
        logger.warning("查询邮件中心模版列表失败: %s", exc)
        return {"ok": False, "error": f"邮件中心不可用: {exc}"}

    # tpls_resp 可能是 {"items": [...]} 或直接是 list
    tpls = []
    if isinstance(tpls_resp, dict):
        tpls = tpls_resp.get("items", [])
    elif isinstance(tpls_resp, list):
        tpls = tpls_resp

    if not tpls:
        return {"ok": False, "error": f"未找到 {tpl_type} 类型模版"}

    tpl_id = tpls[0]["id"]

    # 2. 渲染模版
    try:
        rendered = email_client.render_template(tpl_id, {"variables": template_data})
    except Exception as exc:
        logger.warning("渲染模版失败 (template=%s): %s", tpl_id, exc)
        return {"ok": False, "error": f"渲染模版失败: {exc}"}

    subject = rendered.get("subject", "")
    body = rendered.get("body", "")
    body_format = rendered.get("bodyFormat", "text")

    # 3. 解析收件人邮箱
    resolved = email_client.resolve_contact_emails(recipients)
    to_emails = [v for v in resolved.values() if v]
    if not to_emails:
        logger.warning("督办邮件收件人邮箱全部为空: recipients=%s, resolved=%s", recipients, resolved)
        return {"ok": False, "error": "无法解析收件人邮箱"}

    # 4. 发送
    send_result = email_client.send_email(
        to=to_emails,
        subject=subject,
        body=body,
        body_format=body_format,
        email_type=f"supervise_{scene}",
        raise_on_error=False,
    )

    if not send_result.get("ok"):
        logger.warning("督办邮件发送失败: %s", send_result.get("error"))
        return send_result

    logger.info(
        "督办邮件发送成功 scene=%s recipients=%s subject=%s",
        scene, recipients, subject,
    )
    return {
        "ok": True,
        "subject": subject,
        "body": body,
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
    template_data = {
        "no": ticket.get("issue_no") or ticket.get("no") or "",
        "title": ticket.get("title") or "",
        "type": ticket.get("issue_type") or ticket.get("category") or "",
        "owner": ticket.get("handler") or ticket.get("owner") or "",
        "due": ticket.get("due") or ticket.get("plan_end") or "",
        "status": ticket.get("status") or "",
        "source": ticket.get("source") or "",
        "desc": ticket.get("situation_desc")
                or ticket.get("description")
                or ticket.get("desc")
                or "",
    }
    return _render_and_send(scene, template_data, recipients)


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
