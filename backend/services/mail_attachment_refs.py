"""引用型邮件附件解析收口（唯一实现）。

背景（2026-11-10 会议附件横向推广）：弹窗附件区的「业务附件带出」条目在前端只传
引用（{refType, refId, name}，不带文件字节），统一由本模块按 refType 分派到
各场景附件库只读解析并转 base64：

- operation            → 运营工单   uploads/operation/{refId}/{name}
- research             → 调研工单   uploads/research/{refId}/{name}
- requirement_delivery → 需求交付   Obsidian 需求归档目录（requirement_delivery.attachment_folder）

口径约定：
- 各场景附件的**写入/删除**仍归各自 router/service（写入口径不收口到这里）；
- 本模块只读文件、不写库、不改附件元数据；文件缺失跳过并告警，不阻塞发送；
- 纯 base64 条目（弹窗手工新增）原样透传，不做解析。
"""
from __future__ import annotations

import base64
import logging
import mimetypes
import os
from typing import Any, Dict, List, Optional, Tuple

from utils.file_storage import uploads_root

logger = logging.getLogger("pmwb.mail_attachment_refs")


def split_entries(atts: Optional[List[dict]]) -> Tuple[List[dict], List[dict]]:
    """把弹窗透传的附件列表拆成（引用型条目, 纯 base64 条目）。"""
    refs: List[dict] = []
    base64_atts: List[dict] = []
    for a in atts or []:
        if not isinstance(a, dict):
            continue
        if a.get("contentBase64"):
            base64_atts.append(a)
        elif a.get("refType") and a.get("refId") and a.get("name"):
            refs.append(a)
    return refs, base64_atts


def _read_as_attachment(folder: str, name: str, filename: str) -> Optional[Dict[str, Any]]:
    """读取目录下的单个文件并转为邮件附件结构；缺失/非法返回 None。"""
    fp = os.path.join(folder, os.path.basename(name))
    if not os.path.abspath(fp).startswith(os.path.abspath(folder)) or not os.path.isfile(fp):
        return None
    with open(fp, "rb") as f:
        raw = f.read()
    if not raw:
        return None
    return {
        "filename": filename or os.path.basename(name),
        "contentBase64": base64.b64encode(raw).decode(),
        "mimeType": mimetypes.guess_type(fp)[0] or "application/octet-stream",
    }


def _resolve_one(db: Any, ref: dict) -> List[Dict[str, Any]]:
    """解析单个引用条目 → base64 附件列表（按 refType 分派）。"""
    ref_type = str(ref.get("refType") or "")
    ref_id = ref.get("refId")
    name = ref.get("name") or ""

    if ref_type in ("operation", "research"):
        root = os.path.join(uploads_root(), ref_type, str(ref_id))
        att = _read_as_attachment(root, name, name)
        return [att] if att else []

    if ref_type == "requirement_delivery":
        from services.requirement_delivery import attachment_folder

        folder = attachment_folder(db, str(ref_id))
        att = _read_as_attachment(folder, name, name)
        return [att] if att else []

    logger.warning("未知附件引用类型，跳过: refType=%s refId=%s name=%s", ref_type, ref_id, name)
    return []


def merge_attachments(db: Any, atts: Optional[List[dict]]) -> Optional[List[Dict[str, Any]]]:
    """统一入口：引用型条目解析 + base64 条目透传，合并为可发附件列表。

    空列表/None 返回 None（dispatch_email 语义：None=不带附件）。
    各场景（通用 /mail/send、task_center、high_level、sensitive_req、reminder、
    work_report）发信前统一调用，保证解析口径只有这一份。
    """
    if not atts:
        return None
    refs, base64_atts = split_entries(atts)
    resolved: List[Dict[str, Any]] = []
    seen: set = set()
    for ref in refs:
        try:
            for att in _resolve_one(db, ref):
                key = (att["filename"], att["mimeType"])
                if key in seen:
                    continue
                seen.add(key)
                resolved.append(att)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "解析业务附件失败（跳过不阻塞发信）: refType=%s refId=%s name=%s: %s",
                ref.get("refType"), ref.get("refId"), ref.get("name"), exc,
            )
    for att in base64_atts:
        key = (att.get("filename") or att.get("name") or "", att.get("mimeType") or "")
        if key in seen:
            continue
        seen.add(key)
        resolved.append(att)
    return resolved or None
