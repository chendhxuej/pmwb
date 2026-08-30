"""轻量级密钥混淆（无第三方依赖）：本地 DB 中 API Key 的静态存储混淆 + 接口脱敏。

说明：本应用为本地单用户运行，数据库仅本机可访问。此处用 XOR+Base64 做静态混淆，
避免明文落库；接口一律返回脱敏值（'***'），绝不回显明文。如后续需要更强保护，
可平滑替换为 cryptography.Fernet（密钥由 settings.SECRET_KEY 派生）。
"""
from __future__ import annotations

import base64
import hashlib
import os

from core.config import settings

# backend/ 目录（secret.py 位于 backend/utils/）
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _env_file_secret_key() -> str | None:
    """读取 backend/.env 中的 SECRET_KEY，作为解密回退候选（自愈）。

    用于防御：当 settings.SECRET_KEY 被 OS 环境变量覆盖（pydantic-settings 优先级
    环境变量 > .env），导致历史密文全部解不开时，仍能用 .env 中真正的加密钥匙解出。
    """
    try:
        env_path = os.path.join(_BACKEND_DIR, ".env")
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or not line.startswith("SECRET_KEY"):
                    continue
                _, _, val = line.partition("=")
                val = val.strip().strip('"').strip("'")
                return val or None
    except Exception:  # noqa: BLE001
        return None
    return None


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


def _decrypt_with(key: str, cipher: str) -> str | None:
    """用指定密钥尝试 XOR+Base64 解密；解不出（乱码/非 UTF-8）返回 None。"""
    if not key:
        return None
    kb = hashlib.sha256(key.encode("utf-8")).digest()
    try:
        data = base64.b64decode(cipher)
    except Exception:  # noqa: BLE001
        return None
    out = bytes(b ^ kb[i % len(kb)] for i, b in enumerate(data))
    try:
        return out.decode("utf-8")
    except Exception:  # noqa: BLE001
        return None


def _looks_like_secret(s: str) -> bool:
    """粗筛：真实 API Key 一般为长度>=8 的可打印 ASCII，排除 XOR 错钥产生的乱码。"""
    if len(s) < 8:
        return False
    return all(32 <= ord(c) < 127 for c in s)


def decrypt_secret(cipher: str | None) -> str | None:
    """混淆密文 -> 明文。

    自愈机制：主密钥（settings.SECRET_KEY，可能被 OS 环境变量覆盖）解不开时，
    依次回退 .env 中的 SECRET_KEY、默认密钥，返回第一个能解出"像密钥"的结果。
    彻底规避 SECRET_KEY 漂移导致全部已存 API Key 失效、静默 401 的问题。
    """
    if not cipher:
        return None
    candidates: list[str] = []
    seen: set[str] = set()
    for k in (settings.SECRET_KEY, _env_file_secret_key(), "pmwb-default-secret"):
        if k and k not in seen:
            seen.add(k)
            candidates.append(k)
    for k in candidates:
        r = _decrypt_with(k, cipher)
        if r is not None and _looks_like_secret(r):
            return r
    return None


def mask_secret(cipher: str | None) -> str:
    """接口展示用：有值返回 '***'，无值返回空串（绝不回显明文）。"""
    return "***" if cipher else ""
