"""轻量级密钥混淆（无第三方依赖）：本地 DB 中 API Key 的静态存储混淆 + 接口脱敏。

说明：本应用为本地单用户运行，数据库仅本机可访问。此处用 XOR+Base64 做静态混淆，
避免明文落库；接口一律返回脱敏值（'***'），绝不回显明文。如后续需要更强保护，
可平滑替换为 cryptography.Fernet（密钥由 settings.SECRET_KEY 派生）。
"""
from __future__ import annotations

import base64
import hashlib

from core.config import settings


def _key_bytes() -> bytes:
    raw = (settings.SECRET_KEY or "pmwb-default-secret").encode("utf-8")
    return hashlib.sha256(raw).digest()


def encrypt_secret(plain: str | None) -> str | None:
    """明文 -> 混淆密文（Base64）。空值返回 None。"""
    if not plain:
        return None
    kb = _key_bytes()
    data = plain.encode("utf-8")
    out = bytes(b ^ kb[i % len(kb)] for i, b in enumerate(data))
    return base64.b64encode(out).decode("ascii")


def decrypt_secret(cipher: str | None) -> str | None:
    """混淆密文 -> 明文。失败返回 None。"""
    if not cipher:
        return None
    kb = _key_bytes()
    try:
        data = base64.b64decode(cipher)
    except Exception:  # noqa: BLE001
        return None
    out = bytes(b ^ kb[i % len(kb)] for i, b in enumerate(data))
    try:
        return out.decode("utf-8")
    except Exception:  # noqa: BLE001
        return None


def mask_secret(cipher: str | None) -> str:
    """接口展示用：有值返回 '***'，无值返回空串（绝不回显明文）。"""
    return "***" if cipher else ""
