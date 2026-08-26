"""附件压缩兜底：统一邮件中心(3210) 默认 JSON body 上限约 100KB，
插件发送需求评估邮件常带 base64 截图，易触发 413 Payload Too Large。

本模块在转发 3210 前对**图片**附件自动压缩到安全体积，避免 413；
非图片附件（如 xlsx/pdf）不处理，依赖 3210 重启放宽后的更大上限，
若仍超限由 dispatch_email 的 413 友好化兜底提示。
"""
from __future__ import annotations

import base64
import io
import logging

try:
    from PIL import Image
    HAS_PILLOW = True
except Exception:  # noqa: BLE001
    HAS_PILLOW = False

logger = logging.getLogger("pmwb.attachment_compress")

# 邮件中心单封 body 安全上限（3210 默认 100KB，留足余量避免踩线；
# 实际 JSON 还含 HTML 正文与字段名，故目标压到 70KB 以内以确保不触发 413）
_MAIL_CENTER_SAFE_BYTES = 70 * 1024


def _compress_image(raw: bytes, max_bytes: int) -> bytes:
    """把图片原始字节压缩到 max_bytes 以内。

    双策略：先按 JPEG quality 递减（85→70→55），同一质量下仍超限再按比例缩小
    （scale 下限 0.15）。网页/UI 截图（大量纯色+文字）通常首轮即可压到安全体积；
    纯噪声等极端图可能压不到，由上层 413 兜底提示。
    """
    if not HAS_PILLOW:
        return raw
    try:
        img = Image.open(io.BytesIO(raw))
    except Exception as exc:  # noqa: BLE001
        logger.warning("图片解码失败，跳过压缩: %s", exc)
        return raw
    # 去透明通道，便于 JPEG 压缩
    if img.mode in ("RGBA", "LA", "P", "PA"):
        img = img.convert("RGB")
    last = raw
    for quality in (85, 70, 55):
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=quality, optimize=True, progressive=True)
        data = out.getvalue()
        if len(data) <= max_bytes:
            return data
        last = data
        # 质量不够，按比例缩小再试
        scale = 1.0
        while len(data) > max_bytes and scale > 0.15:
            scale *= 0.8
            w = max(1, int(img.width * scale))
            h = max(1, int(img.height * scale))
            out = io.BytesIO()
            img.resize((w, h), Image.LANCZOS).save(
                out, format="JPEG", quality=quality, optimize=True, progressive=True
            )
            data = out.getvalue()
        if len(data) <= max_bytes:
            return data
        last = data
    return last


def _looks_like_image(a: dict) -> bool:
    """判断附件是否为图片：优先看 mime，mime 不可信时（如 octet-stream）用字节头探测。

    插件截图在 file.type 为空时会被默认成 application/octet-stream，但字节仍是 PNG/JPG，
    必须用字节探测才能正确识别并压缩，否则大图原样转发 3210 触发 413。
    """
    mime = (a.get("mimeType") or "").lower()
    if mime.startswith("image/"):
        return True
    raw = base64.b64decode(a.get("contentBase64", "") or "")
    if not raw:
        return False
    if HAS_PILLOW:
        try:
            with Image.open(io.BytesIO(raw)) as im:
                im.verify()  # 验证像素数据完整性（不改原字节）
            return True
        except Exception:  # noqa: BLE001
            return False
    # 无 Pillow 时退化为扩展名/常见图片头兜底
    head = raw[:12].lower()
    if head.startswith(b"\x89png") or head.startswith(b"\xff\xd8\xff"):
        return True
    fn = (a.get("filename") or "").lower()
    return fn.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"))


def compress_attachments_for_mail_center(
    attachments: list | None,
    safe_bytes: int = _MAIL_CENTER_SAFE_BYTES,
) -> list | None:
    """对超体积附件中的图片做前置压缩；返回（可能修改后的）附件列表。

    仅当附件总 base64 超过 safe_bytes 才处理，避免无谓压缩；
    非图片附件（或 Pillow 不可用时）原样返回。
    图片识别不依赖 mime：mime 缺失/错误时改用字节探测，确保插件截图
    （常被标成 application/octet-stream）也能被压缩，避免 413。
    """
    if not attachments:
        return attachments
    total_b64 = sum(len(a.get("contentBase64", "")) for a in attachments)
    if total_b64 <= safe_bytes:
        return attachments
    images = [a for a in attachments if _looks_like_image(a)]
    if not images:
        return attachments
    per = max(40 * 1024, safe_bytes // len(images))
    for a in images:
        raw = base64.b64decode(a.get("contentBase64", "") or "")
        if not raw:
            continue
        comp = _compress_image(raw, per)
        if len(comp) < len(raw):
            a["contentBase64"] = base64.b64encode(comp).decode()
            a["mimeType"] = "image/jpeg"
            fn = a.get("filename") or "attachment"
            if not fn.lower().endswith((".jpg", ".jpeg")):
                a["filename"] = fn.rsplit(".", 1)[0] + ".jpg"
            logger.info("附件图片已压缩 %d -> %d bytes", len(raw), len(comp))
    return attachments
