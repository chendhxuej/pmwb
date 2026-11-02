"""登录鉴权接口（mb-1）。

- POST /api/v1/auth/login：校验账号密码（.env 配置），签发 JWT；
- GET  /api/v1/auth/me：回显当前登录用户（token 由全局中间件解析）。

安全护栏：
- 常量时间比较防时序攻击（hmac.compare_digest）；
- 同 IP 连续失败 5 次锁定 5 分钟（内存限速，单实例部署够用，重启清零）；
- AUTH_PASSWORD 未配置时登录一律拒绝（fail-closed）。
"""

import hmac
import time
from collections import defaultdict

from fastapi import APIRouter, Request
from pydantic import BaseModel

from core.config import settings
from core.exceptions import PMWBException
from core.response import success
from core.security import create_token

router = APIRouter()

_FAIL_LIMIT = 5
_LOCK_SECONDS = 300
_fail_records = defaultdict(lambda: {"count": 0, "lock_until": 0.0})


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login", summary="登录获取 token")
async def login(req: LoginRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    rec = _fail_records[ip]
    now = time.time()
    if rec["lock_until"] > now:
        wait = int(rec["lock_until"] - now)
        raise PMWBException(
            f"失败次数过多，请 {wait} 秒后重试", code=429, status_code=429
        )
    ok_user = hmac.compare_digest(
        req.username.encode("utf-8"), settings.AUTH_USERNAME.encode("utf-8")
    )
    ok_pass = bool(settings.AUTH_PASSWORD) and hmac.compare_digest(
        req.password.encode("utf-8"), settings.AUTH_PASSWORD.encode("utf-8")
    )
    if not (ok_user and ok_pass):
        rec["count"] += 1
        if rec["count"] >= _FAIL_LIMIT:
            rec["lock_until"] = now + _LOCK_SECONDS
            rec["count"] = 0
        raise PMWBException("用户名或密码错误", code=401, status_code=401)
    _fail_records.pop(ip, None)
    token = create_token(req.username)
    return success(
        {
            "token": token,
            "token_type": "bearer",
            "expires_in": settings.AUTH_TOKEN_EXPIRE_MINUTES * 60,
            "username": req.username,
        }
    )


@router.get("/auth/me", summary="当前登录用户")
async def me(request: Request):
    return success({"username": getattr(request.state, "auth_user", "")})
