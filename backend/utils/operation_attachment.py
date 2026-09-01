"""运营监控工单附件收集：把工单挂靠的全部附件自动带出到邮件。

两条产出：
1. **邮件正文附件清单（HTML section）**——供预览与正式发送共用，列出每个附件文件名 +
   大小 + 系统下载链接；超限附件标注「体积过大未随信附上，请点击链接下载」。
2. **真实 MIME 附件列表**——未超限的真实文件字节转 base64，交给 dispatch_email 作为
   邮件附件真实发出（收件人直接收到文件）。

数据来源：
- 元信息：pmwb_operation_issue.attachments（JSON 数组：[{name, bytes, size}]）
- 文件：backend/uploads/operation/{issue_id}/{name}

超限策略（避免触发 3210 约 100KB body 上限导致 413）：单文件 > 20MB 或累计 > 50MB 的附件
不随信发出，仅在正文标注，保证邮件正常送达。
"""
from __future__ import annotations

import base64
import mimetypes
import os
from html import escape
from typing import Any
from urllib.parse import quote

from core.config import settings

# 体积上限（MB）。超出则不作为邮件附件发出，正文标注下载链接。
_MAX_SINGLE_MB = 20.0
_MAX_TOTAL_MB = 50.0

_UPLOAD_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "uploads",
    "operation",
)


def _issue_folder(issue_id: int) -> str:
    return os.path.join(_UPLOAD_ROOT, str(issue_id))


def _base_url() -> str:
    base = (settings.PUBLIC_BASE_URL or "").rstrip("/")
    if not base:
        base = f"http://{settings.BACKEND_HOST}:{settings.BACKEND_PORT}"
    return base


def _download_url(issue_id: int, name: str) -> str:
    return (
        f"{_base_url()}/api/v1/operation/issues/{issue_id}"
        f"/attachments/download?filename={quote(name)}"
    )


def build_operation_attachment_block(
    issue_id: int,
    att_metas: list[dict],
    *,
    max_single_mb: float = _MAX_SINGLE_MB,
    max_total_mb: float = _MAX_TOTAL_MB,
) -> tuple[str, list[dict]]:
    """根据工单附件元信息构建邮件附件区块。

    Args:
        issue_id: 运营工单 id（对应 uploads/operation/{issue_id}/ 目录）
        att_metas: 工单 attachments 字段解析出的元信息列表，每项含 name/bytes/size

    Returns:
        (html_section, real_attachments)
        - html_section: 追加到邮件正文的 HTML 附件清单；无附件时返回空串
        - real_attachments: dispatch_email 所需的真实附件列表
          [{filename, mimeType, contentBase64}]（超限/缺失文件不在此列）
    """
    metas = [m for m in (att_metas or []) if isinstance(m, dict) and m.get("name")]
    if not metas:
        return "", []

    folder = _issue_folder(issue_id)
    rows_html: list[str] = []
    real_atts: list[dict] = []
    total_bytes = 0

    for m in metas:
        name = m["name"]
        fp = os.path.join(folder, os.path.basename(name))
        size_human = m.get("size") or ""
        # 文件缺失：仅列名，不附真实文件
        if not os.path.isfile(fp):
            rows_html.append(
                f'<li style="margin:6px 0;">{escape(name)}'
                f'<span style="color:#909399;">（{escape(size_human)}，文件缺失）</span></li>'
            )
            continue
        fbytes = os.path.getsize(fp)
        # 超限：不随信发出，正文标注下载链接
        if fbytes > max_single_mb * 1024 * 1024 or total_bytes + fbytes > max_total_mb * 1024 * 1024:
            rows_html.append(
                f'<li style="margin:6px 0;">'
                f'<a href="{escape(_download_url(issue_id, name))}" '
                f'style="color:#165dff;text-decoration:none;">{escape(name)}</a>'
                f'<span style="color:#909399;">'
                f'（{escape(size_human)}，体积过大未随信附上，请点击链接下载）</span></li>'
            )
            continue
        # 未超限：读真实文件转 base64 作为邮件附件
        try:
            with open(fp, "rb") as f:
                raw = f.read()
        except Exception:  # noqa: BLE001
            rows_html.append(
                f'<li style="margin:6px 0;">{escape(name)}'
                f'<span style="color:#909399;">（读取失败）</span></li>'
            )
            continue
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        real_atts.append({
            "filename": name,
            "mimeType": mime,
            "contentBase64": base64.b64encode(raw).decode(),
        })
        total_bytes += fbytes
        rows_html.append(
            f'<li style="margin:6px 0;">'
            f'<a href="{escape(_download_url(issue_id, name))}" '
            f'style="color:#165dff;text-decoration:none;">{escape(name)}</a>'
            f'<span style="color:#909399;">（{escape(size_human)}）</span></li>'
        )

    if not rows_html:
        return "", []

    section = (
        '<div style="margin-top:18px;border-top:1px solid #e5e6eb;padding-top:12px;">'
        f'<div style="font-weight:600;font-size:14px;color:#1d2129;margin-bottom:6px;">'
        f'工单附件（{len(rows_html)} 个）</div>'
        f'<ul style="margin:6px 0;padding-left:20px;font-size:13px;color:#4e5969;">'
        f'{"".join(rows_html)}</ul></div>'
    )
    return section, real_atts
