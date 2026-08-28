"""统一邮件治理门面（Mail Dispatch Facade）。

职责：
1. 场景注册表：每个发邮件触点声明 email_type / source / 模板 / 签名档 / 变量 schema；
2. 正文治理：优先消费 3210 服务端模版（按 type 渲染，运营零代码改文案），
   否则走 Markdown→内联样式 HTML（utils.markdown_mail）；
3. 统一签名：按 scene 的 signature_key 注入内联 style 签名块；
4. 统一落库：写入 email_records（与日志/追溯体系对齐），全场景一致；
5. 统一降级：邮件中心/模版不可用时返回 {success:False} 而非抛异常，由调用方决定。

收件人解析（姓名/邮箱/中台解析）由各调用方负责，门面只管「渲染 + 签名 + 落库 + 发信」，
保持职责单一、低风险。预览与发送共用 _render_mail，保证「预览即实发」。
"""
from __future__ import annotations

import html
import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from core.config import settings
from db.models import EmailRecord
from utils.attachment_compress import compress_attachments_for_mail_center
from utils.email import EmailCenterClient
from utils.markdown_mail import (
    _sanitize,
    inject_signature_inline,
    markdown_to_email_html,
)

logger = logging.getLogger("pmwb.mail_dispatch")


@dataclass
class MailScene:
    key: str
    email_type: str = ""               # 写入 EmailRecord.email_type / 3210 type
    source: str = "pmwb"               # 写入 EmailRecord.source
    template_key: Optional[str] = None  # 指向 3210 模版 type；置空则 raw markdown
    raw: bool = True                   # True=Markdown 正文；False=消费 3210 模版
    signature_key: str = "default"     # 引用 settings.EMAIL_SIGNATURE_MAP
    var_schema: list = field(default_factory=list)  # 必填变量键（templated 校验）
    default_subject: Optional[str] = None
    fallback_template: Optional[str] = None  # 3210 不可用时的 Markdown 兜底
    add_signature: bool = True


# 场景注册表：所有发邮件触点在此声明统一样式/签名/类型。
# P0 全量收口：reminder/plugin/work_report/task_center/supervise 均迁入本门面。
# T-B（2026-08-17）：10 场景启用 3210 模板（raw=False + template_key），
# 3210 模板由 scripts/sync_email_templates.py 幂等建设；work_report/plugin 保持 raw。
# 每个切模板场景配 fallback_template（Markdown 兜底），3210 抖动时正文不空。
SCENES: dict[str, MailScene] = {
    "meeting_notice": MailScene(
        "meeting_notice", email_type="meeting_notice", source="pmwb_meeting",
        template_key="meeting_notice", raw=False,
        fallback_template="## 会议通知\n\n会议主题与安排请查看系统通知或联系主持人。",
    ),
    "meeting_minutes": MailScene(
        "meeting_minutes", email_type="meeting_minutes", source="pmwb_meeting",
        template_key="meeting_minutes", raw=False,
        fallback_template="## 会议纪要\n\n纪要正文请查看系统或邮件中心。",
    ),
    "action_dispatch": MailScene(
        "action_dispatch", email_type="action_dispatch", source="pmwb_meeting",
        template_key="action_dispatch", raw=False,
        fallback_template="## 会议行动项派发\n\n请查看邮件中心对应会议的行动项清单，及时跟进处理。",
    ),
    "action_supervise": MailScene(
        "action_supervise", email_type="action_supervise", source="pmwb_supervise",
        template_key="action_supervise", raw=False,
        fallback_template="## 会议行动项督办\n\n请查看系统内行动项详情并及时反馈进展。",
    ),
    "task_reminder": MailScene(
        "task_reminder", email_type="task_reminder", source="pmwb_task",
        template_key="task_reminder", raw=False,
        fallback_template="## 任务督办提醒\n\n任务详情请查看系统或邮件中心。",
    ),
    "requirement_reminder": MailScene(
        "requirement_reminder", email_type="pmwb_reminder", source="pmwb_reminder",
        template_key="xqemail_reminder", raw=False,
        fallback_template="## 需求催办通知\n\n请查看系统内需求详情并及时处理。",
    ),
    # 新增/改造场景（收口后统一走门面）
    "work_report": MailScene("work_report", email_type="work_report", source="pmwb_work_report"),
    "task_center_notify": MailScene(
        "task_center_notify", email_type="pmwb_task_notify", source="task-center",
        template_key="task_center_notify", raw=False,
        fallback_template="## 任务同步通知\n\n任务清单请查看系统任务中心。",
    ),
    "task_center_urge": MailScene(
        "task_center_urge", email_type="pmwb_task_urge", source="task-center",
        template_key="task_center_urge", raw=False,
        fallback_template="## 任务催办提醒\n\n请查看系统任务中心，尽快处理并反馈进展。",
    ),
    "plugin": MailScene("plugin", email_type="xqemail_plugin", source="plugin"),
    # supervise 场景：3210 模板已由 T-A 建设（supervise_urge/supervise_sync type）
    "supervise_sync": MailScene(
        "supervise_sync", email_type="supervise_sync", source="pmwb_supervise",
        template_key="supervise_sync", raw=False,
        fallback_template="## 工单进展同步\n\n工单详情请查看系统运营监控。",
    ),
    "supervise_urge": MailScene(
        "supervise_urge", email_type="supervise_urge", source="pmwb_supervise",
        template_key="supervise_urge", raw=False,
        fallback_template="## 催办通知\n\n工单详情请查看系统运营监控，请尽快处理。",
    ),
    "active_optimization_urge": MailScene(
        "active_optimization_urge", email_type="active_optimization_urge", source="pmwb_active_optimization",
        fallback_template="## 主动优化建议催办\n\n请尽快评估以下优化建议。",
    ),
    "active_optimization_sync": MailScene(
        "active_optimization_sync", email_type="active_optimization_sync", source="pmwb_active_optimization",
        fallback_template="## 主动优化建议同步\n\n请知悉以下优化建议的最新状态。",
    ),
    "keywork_feedback": MailScene(
        "keywork_feedback", email_type="keywork_feedback", source="pmwb_keywork",
        fallback_template="## 周反馈请求\n\n请按邮件正文要求反馈本周工作进展。",
    ),
}


def get_scene(key: str) -> MailScene:
    return SCENES.get(key, MailScene(key))


def _norm_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()]
    return [str(x).strip() for x in v if str(x).strip()]


def _resolve_signature(sc: MailScene) -> str:
    key = sc.signature_key or "default"
    return settings.EMAIL_SIGNATURE_MAP.get(key) or settings.EMAIL_SIGNATURE


def _render_templated(
    sc: MailScene,
    variables: Optional[dict],
    template_id: Optional[str],
    template_data: Optional[dict],
) -> tuple[str, str, str]:
    """调 3210 渲染模版，返回 (body_html, subject, body_format)。失败抛异常由上层降级。"""
    client = EmailCenterClient()
    tpl_id = template_id
    if not tpl_id:
        items = client.list_templates(sc.template_key)
        if not items:
            raise RuntimeError(f"未找到 {sc.template_key} 类型模版")
        default = next((t for t in items if t.get("isDefault")), items[0])
        tpl_id = default["id"]
    # 预处理：body / content 从 Markdown 转 HTML，供模板 {{{var}}} 原始 HTML 插值
    vars_copy = dict(variables or template_data or {})
    for key in ("body", "content"):
        if key in vars_copy and vars_copy[key]:
            vars_copy[key] = markdown_to_email_html(vars_copy[key], inject_signature=False)
    rendered = client.render_template(tpl_id, {"variables": vars_copy})
    subject = rendered.get("subject", "")
    body = rendered.get("body", "")
    fmt = rendered.get("bodyFormat", "html")
    if fmt == "text":
        # 纯文本模版：包成 pre-wrap 的 HTML，保留换行且能被内联签名
        body = (
            f'<div style="white-space:pre-wrap;font-family:-apple-system,'
            f"'Segoe UI','Microsoft YaHei',Arial,sans-serif;"
            f'font-size:14px;line-height:1.7;color:#1f2329;word-break:break-word;">'
            f"{html.escape(body)}</div>"
        )
        fmt = "html"
    return body, subject, fmt


def _render_mail(
    *,
    scene: str = "",
    variables: Optional[dict] = None,
    raw_content: Optional[str] = None,
    subject: Optional[str] = None,
    html_passthrough: bool = False,
    template_id: Optional[str] = None,
    template_data: Optional[dict] = None,
    add_signature: Optional[bool] = None,
    signature: Optional[str] = None,
) -> dict:
    """渲染邮件正文（预览与发送共用，保证预览=实发）。

    返回 {html, subject, body_format, rendered_body}。
    """
    sc = get_scene(scene) if scene else MailScene("")
    sig_on = add_signature if add_signature is not None else sc.add_signature

    # scene 模式下，前端 MailComposeDialog 把可编辑正文放在 variables.body；
    # raw 场景需要将其提取为 raw_content，否则预览/发送正文为空
    if not raw_content and variables:
        raw_content = variables.get("body") or variables.get("content")

    use_templated = bool(template_id) or (sc.template_key and not sc.raw)
    body_html = ""
    rendered_subject = None
    body_format = "html"

    if use_templated:
        try:
            body_html, rendered_subject, body_format = _render_templated(
                sc, variables, template_id, template_data
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("3210 模版渲染失败，走降级: %s", exc)
            # 降级优先用调用方正文（variables.body，信息完整），其次场景通用 Markdown 兜底
            fb = raw_content or sc.fallback_template or ""
            body_html = markdown_to_email_html(fb, inject_signature=False)
            rendered_subject = None
            body_format = "html"
    elif html_passthrough:
        # 插件等外部已带样式的 HTML：净化后直接注入签名
        body_html = _sanitize(raw_content or "")
        body_format = "html"
    else:
        body_html = markdown_to_email_html(raw_content or "", inject_signature=False)
        body_format = "html"

    final_subject = subject or rendered_subject or sc.default_subject or ""

    if sig_on:
        sig = signature if signature is not None else _resolve_signature(sc)
        body_html = inject_signature_inline(body_html, sig)

    return {
        "html": body_html,
        "subject": final_subject,
        "body_format": body_format,
        "rendered_body": body_html,
    }


def dispatch_email(
    *,
    db: Optional[Session] = None,
    to: list | str,
    subject: Optional[str] = None,
    scene: str = "",
    body: Optional[str] = None,          # 兼容旧调用：raw_content 别名
    raw_content: Optional[str] = None,
    variables: Optional[dict] = None,
    template_id: Optional[str] = None,
    template_data: Optional[dict] = None,
    body_format: Optional[str] = None,
    cc: Optional[list | str] = None,
    recipient_name: Optional[str] = None,
    email_type: Optional[str] = None,
    source: Optional[str] = None,
    req_id: Optional[str] = None,
    req_name: Optional[str] = None,
    signature_key: Optional[str] = None,
    add_signature: Optional[bool] = None,
    signature: Optional[str] = None,
    attachments: Optional[list] = None,
    html_passthrough: bool = False,
    raise_on_error: bool = False,
) -> dict:
    """统一发信入口。

    返回 {success, record_id, message, body_format, subject, rendered_body, message_id}。
    邮件中心不可用时默认降级返回 success=False（raise_on_error=True 则抛出）。
    """
    sc = get_scene(scene) if scene else None
    etype = email_type or (sc.email_type if sc else "")
    src = source or (sc.source if sc else "pmwb")
    raw_content = raw_content if raw_content is not None else body

    to_list = _norm_list(to)
    cc_list = _norm_list(cc)

    rendered = _render_mail(
        scene=scene,
        variables=variables,
        raw_content=raw_content,
        subject=subject,
        html_passthrough=html_passthrough,
        template_id=template_id,
        template_data=template_data,
        add_signature=add_signature,
        signature=signature,
    )
    final_subject = rendered["subject"]
    final_body = rendered["html"]
    fmt = body_format or rendered["body_format"] or "html"

    record = None
    if db is not None:
        record = EmailRecord(
            req_id=req_id,
            req_name=req_name,
            email_type=etype or None,
            recipient=",".join(to_list),
            recipient_name=recipient_name or ",".join(to_list),
            subject=final_subject,
            content=final_body,
            send_status="pending",
            source=src,
            sender="pmwb",
        )
        db.add(record)
        db.commit()
        db.refresh(record)

    ok = True
    message = "邮件发送成功"
    message_id = None
    try:
        # 附件图片压缩兜底：避免超 3210 默认 100KB body 上限触发 413
        attachments = compress_attachments_for_mail_center(attachments)
        send_res = EmailCenterClient().send_email(
            to=to_list,
            subject=final_subject,
            body=final_body,
            body_format=fmt,
            cc=cc_list or None,
            email_type=etype or None,
            attachments=attachments,
            raise_on_error=True,
        )
        # 兼容 3210 直接返回 {ok: False, error: ...} 的降级契约
        if isinstance(send_res, dict) and send_res.get("ok") is False:
            error_msg = send_res.get("error") or "邮件中心返回失败"
            raise RuntimeError(error_msg)
        if isinstance(send_res, dict):
            data = send_res.get("data")
            if isinstance(data, dict):
                message_id = data.get("messageId")
            else:
                # 兼容 3210 原始返回结构 {messageId, fromEmail, accountId}
                message_id = send_res.get("messageId")
        if record:
            record.send_status = "success"
    except Exception as exc:  # noqa: BLE001
        ok = False
        msg = str(exc)
        if "413" in msg:
            message = (
                "邮件发送失败：内容/附件超过邮件中心单封上限（约 100KB）。"
                "已自动压缩截图仍超限，请减小附件，或重启统一邮件中心（已放宽至 25MB，待重启生效）后重试。"
            )
        else:
            message = f"邮件发送失败：{exc}"
        logger.warning("dispatch_email 失败 scene=%s: %s", scene, exc)
        if record:
            record.send_status = "failed"
            record.error_msg = str(exc)
        if raise_on_error:
            if record:
                db.commit()
            raise

    if db is not None and record is not None:
        db.commit()
        db.refresh(record)

    return {
        "success": ok,
        "record_id": record.id if record else None,
        "message": message,
        "body_format": fmt,
        "subject": final_subject,
        "rendered_body": final_body,
        "message_id": message_id,
    }
