"""会议附件管理（唯一实现）。

数据落位（铁律）：
- 文件实体：settings.MEETING_ATTACHMENT_DIR/{会议主键}/{安全文件名}；
  目录留空自动推导为项目根/data/meeting_attachments（项目内，禁写 C 盘）。
- 元数据：pmwb_meeting.attachments JSON 数组 [{name, size, uploaded_at}]。

口径：
- 上传同名文件 = 替换（覆盖文件实体 + 刷新该条元数据的 size/uploaded_at）；
- 删除 = 文件实体与元数据同删，删不到文件但元数据在时仍清元数据（自愈）；
- 发信联动：send_mail 未传附件名单时默认带出全部会议附件（自动关联），
  前端邮件弹窗可裁剪（仅本邮件生效）或临时追加文件（仅随邮件发送，不回存）。
"""
from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.config import settings
from core.exceptions import NotFoundException, ValidationException
from db.models import PmwbMeeting

logger = logging.getLogger(__name__)

# 单文件上限：与业务资料库 MAX_UPLOAD_SIZE_MB 收口一致
MAX_ATTACHMENT_MB = settings.MAX_UPLOAD_SIZE_MB

_BAD_CHARS_RE = re.compile(r'[\\/:*?"<>|\r\n\t]+')
MAX_NAME_LEN = 180


def sanitize_filename(name: str) -> str:
    """文件名清洗：去路径分隔符/非法字符，限长。同名上传即替换的键。"""
    safe = _BAD_CHARS_RE.sub("_", str(name or "未命名文件")).strip().strip(".")
    if not safe:
        safe = "未命名文件"
    return safe[:MAX_NAME_LEN]


def base_dir() -> str:
    d = (settings.MEETING_ATTACHMENT_DIR or "").strip()
    if not d:
        d = str(Path(__file__).resolve().parents[2] / "data" / "meeting_attachments")
    return d


def meeting_dir(meeting_pk: int, create: bool = False) -> str:
    d = os.path.join(base_dir(), str(meeting_pk))
    if create:
        os.makedirs(d, exist_ok=True)
    return d


def parse_attachments(raw) -> List[Dict[str, Any]]:
    """pmwb_meeting.attachments 文本 → 数组（坏数据自愈为空列表，不抛错）。"""
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:  # noqa: BLE001
        logger.warning("会议附件元数据解析失败，按空处理: %r", raw[:120] if isinstance(raw, str) else raw)
        return []


def _dump(items: List[Dict[str, Any]]) -> str:
    return json.dumps(items, ensure_ascii=False)


def _save_meta(db: Session, meeting: PmwbMeeting, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    meeting.attachments = _dump(items)
    db.commit()
    db.refresh(meeting)
    return parse_attachments(meeting.attachments)


def list_attachments(db: Session, meeting_id: int) -> List[Dict[str, Any]]:
    meeting = db.query(PmwbMeeting).filter(PmwbMeeting.id == meeting_id).first()
    if not meeting:
        raise NotFoundException(f"会议不存在：id={meeting_id}")
    return parse_attachments(meeting.attachments)


def file_path(meeting_pk: int, name: str) -> str:
    return os.path.join(meeting_dir(meeting_pk), sanitize_filename(name))


def upload(db: Session, meeting_id: int, filename: str, content: bytes) -> Dict[str, Any]:
    """上传 / 同名替换。返回 {items, replaced, entry}。"""
    if content is None or len(content) == 0:
        raise ValidationException("附件内容为空")
    if len(content) > MAX_ATTACHMENT_MB * 1024 * 1024:
        raise ValidationException(f"附件超过单文件上限（{MAX_ATTACHMENT_MB}MB）")
    meeting = db.query(PmwbMeeting).filter(PmwbMeeting.id == meeting_id).first()
    if not meeting:
        raise NotFoundException(f"会议不存在：id={meeting_id}")

    safe = sanitize_filename(filename)
    fp = file_path(meeting_id, safe)
    meeting_dir(meeting_id, create=True)
    with open(fp, "wb") as f:
        f.write(content)

    items = parse_attachments(meeting.attachments)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {"name": safe, "size": len(content), "uploaded_at": now}
    replaced = False
    for i, it in enumerate(items):
        if it.get("name") == safe:
            items[i] = entry
            replaced = True
            break
    else:
        items.append(entry)
    items = _save_meta(db, meeting, items)
    logger.info("会议附件%s meeting_id=%s name=%s size=%d", "替换" if replaced else "上传", meeting_id, safe, len(content))
    return {"items": items, "replaced": replaced, "entry": entry}


def delete(db: Session, meeting_id: int, name: str) -> Dict[str, Any]:
    """删除附件：文件实体 + 元数据同删。文件已不在时仍清元数据（自愈）。"""
    meeting = db.query(PmwbMeeting).filter(PmwbMeeting.id == meeting_id).first()
    if not meeting:
        raise NotFoundException(f"会议不存在：id={meeting_id}")
    safe = sanitize_filename(name)
    items = parse_attachments(meeting.attachments)
    hit = next((it for it in items if it.get("name") == safe), None)
    if not hit:
        raise NotFoundException(f"附件不存在：{safe}")

    fp = file_path(meeting_id, safe)
    try:
        if os.path.exists(fp):
            os.remove(fp)
    except OSError as exc:  # noqa: BLE001
        # 受保护环境禁止程序化删除：给明确提示而非 500，元数据先不动保证一致
        raise ValidationException(f"删除被环境拒绝：{exc}")
    items = [it for it in items if it.get("name") != safe]
    items = _save_meta(db, meeting, items)
    return {"items": items, "deleted": safe}


def build_mail_attachments(
    db: Session,
    meeting: PmwbMeeting,
    names: Optional[List[str]] = None,
    extras: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """构建发信附件列表（dispatch_email 契约：[{filename, contentBase64, mimeType}]）。

    - names=None → 自动关联全部会议附件（send_mail 默认口径）；
      names=[] → 明确不带任何会议附件（用户在邮件弹窗全裁剪）；
    - extras：邮件弹窗临时追加的文件（{filename, contentBase64, mimeType}），仅随本邮件发送。
    - 会议附件文件缺失时跳过并告警（不阻断发信）。
    """
    out: List[Dict[str, Any]] = []
    items = parse_attachments(meeting.attachments)
    if names is None:
        chosen = items
    else:
        wanted = [sanitize_filename(n) for n in (names or [])]
        seen: set = set()
        chosen = []
        for it in items:
            if it.get("name") in wanted and it.get("name") not in seen:
                chosen.append(it)
                seen.add(it.get("name"))

    for it in chosen:
        fp = file_path(meeting.id, it.get("name", ""))
        if not os.path.exists(fp):
            logger.warning("会议附件文件缺失，跳过: meeting_id=%s %s", meeting.id, fp)
            continue
        mime = mimetypes.guess_type(fp)[0] or "application/octet-stream"
        with open(fp, "rb") as f:
            raw = f.read()
        out.append(
            {
                "filename": it.get("name"),
                "contentBase64": base64.b64encode(raw).decode(),
                "mimeType": mime,
            }
        )

    for ex in extras or []:
        fn = sanitize_filename(ex.get("filename") or ex.get("name") or "attachment")
        b64 = ex.get("contentBase64") or ""
        if not b64:
            continue
        try:
            base64.b64decode(b64, validate=True)
        except Exception:  # noqa: BLE001
            logger.warning("邮件弹窗追加附件 base64 非法，跳过: %s", fn)
            continue
        out.append(
            {
                "filename": fn,
                "contentBase64": b64,
                "mimeType": ex.get("mimeType") or mimetypes.guess_type(fn)[0] or "application/octet-stream",
            }
        )
    return out


class MeetingAttachmentService:
    """命名空间封装：与其它 *Service 单例风格一致，实际逻辑即上方模块级函数（唯一实现）。"""

    parse_attachments = staticmethod(parse_attachments)
    sanitize_filename = staticmethod(sanitize_filename)
    list_attachments = staticmethod(list_attachments)
    upload = staticmethod(upload)
    delete = staticmethod(delete)
    file_path = staticmethod(file_path)
    build_mail_attachments = staticmethod(build_mail_attachments)


meeting_attachment_service = MeetingAttachmentService()
