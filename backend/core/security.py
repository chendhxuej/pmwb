"""JWT 签发与校验（mb-1 登录鉴权）。

约定：
- 单用户登录态（个人工作台），HS256 对称签名；
- 密钥复用 settings.SECRET_KEY（单一真相源，禁止另设密钥）；
- token 有效期 AUTH_TOKEN_EXPIRE_MINUTES（默认 720 分钟 = 12h）。
"""

import time

import jwt

from core.config import settings

ALGORITHM = "HS256"


def create_token(username: str) -> str:
    now = int(time.time())
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + settings.AUTH_TOKEN_EXPIRE_MINUTES * 60,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
    """校验 token，合法返回 username，否则返回 None。"""
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        return sub if isinstance(sub, str) and sub else None
    except jwt.PyJWTError:
        return None
