import logging
import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings
from core.exceptions import PMWBException
from core.security import decode_token
from db.base import engine
from db.models import Base  # noqa: F401
from routers import (
    active_optimization,
    basic_data,
    complaint,
    dashboard,
    dev_ticket,
    health,
    high_level,
    keywork,
    knowledge,
    auth,
    llm_provider,
    mail_center,
    mail_dispatch,
    material,
    meeting,
    meeting_action,
    obsidian,
    plugin,
    operation,
    product_bible,
    reminder,
    requirement,
    requirement_delivery,
    research,
    sensitive_req,
    sql_script,
    status_meta,
    supervise,
    task_center,
    todo,
    user_story,
    work_report,
    workload_analysis,
    ai_qa,
)


def setup_logging() -> logging.Logger:
    log_dir = Path(os.environ.get("PMWB_LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"pmwb_{datetime.now().strftime('%Y%m%d')}.log"

    handlers = [logging.StreamHandler()]
    try:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    except OSError:
        # 日志文件被运行实例占用时（如 import smoke 门禁），降级到控制台
        pass

    logging.basicConfig(
        level=logging.INFO if not settings.DEBUG else logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )
    return logging.getLogger("pmwb")


logger = setup_logging()

class AuthMiddleware(BaseHTTPMiddleware):
    """全局 JWT 鉴权（mb-1）。

    - AUTH_REQUIRED=False 时直通（本地开发默认）；
    - 白名单：登录、健康检查、OpenAPI 文档；
    - OPTIONS 放行（CORS 预检由外层 CORSMiddleware 处理）。
    """

    EXEMPT_PREFIXES = (
        "/api/v1/auth/login",
        "/api/v1/health",
        "/docs",
        "/redoc",
        "/openapi.json",
    )

    async def dispatch(self, request: Request, call_next):
        if not settings.AUTH_REQUIRED:
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)
        path = request.url.path
        if any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return await call_next(request)
        auth_header = request.headers.get("Authorization", "")
        token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else ""
        username = decode_token(token)
        if not username:
            return JSONResponse(
                status_code=401,
                content={"code": 401, "message": "未登录或登录已过期", "data": None},
            )
        request.state.auth_user = username
        return await call_next(request)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="产品经理个人工作台 API",
)

# 注意顺序：先加 AuthMiddleware（内层），再加 CORS（外层），保证 OPTIONS 预检不进鉴权
app.add_middleware(AuthMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(PMWBException)
async def pmwb_exception_handler(request: Request, exc: PMWBException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "data": None,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "系统内部错误",
            "data": None,
        },
    )


app.include_router(health.router, prefix="/api/v1", tags=["健康检查"])
app.include_router(auth.router, prefix="/api/v1", tags=["登录鉴权"])
app.include_router(basic_data.router, prefix="/api/v1", tags=["基础数据"])
app.include_router(keywork.router, prefix="/api/v1", tags=["重点工作"])
app.include_router(operation.router, prefix="/api/v1", tags=["业务运营监控"])
app.include_router(complaint.router, prefix="/api/v1", tags=["客诉专题分析"])
app.include_router(research.router, prefix="/api/v1", tags=["一线调研"])
app.include_router(meeting_action.router, prefix="/api/v1", tags=["会议行动项"])
app.include_router(meeting.router, prefix="/api/v1", tags=["会议管理"])
app.include_router(knowledge.router, prefix="/api/v1", tags=["知识库"])
app.include_router(mail_center.router, prefix="/api/v1", tags=["邮件中心"])
app.include_router(mail_dispatch.router, prefix="/api/v1", tags=["邮件治理"])
app.include_router(plugin.router, prefix="/api/v1", tags=["插件接入"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["首页看板"])
app.include_router(todo.router, prefix="/api/v1", tags=["待办中心"])
app.include_router(requirement.router, prefix="/api/v1", tags=["需求管理"])
app.include_router(requirement_delivery.router, prefix="/api/v1", tags=["需求交付"])
app.include_router(user_story.router, prefix="/api/v1", tags=["用户故事"])
app.include_router(active_optimization.router, prefix="/api/v1", tags=["主动优化"])
app.include_router(dev_ticket.router, prefix="/api/v1", tags=["开发工单"])
app.include_router(reminder.router, prefix="/api/v1", tags=["邮件催办"])
app.include_router(supervise.router, prefix="/api/v1", tags=["邮件督办"])
app.include_router(task_center.router, prefix="/api/v1", tags=["任务中心"])
app.include_router(status_meta.router, prefix="/api/v1", tags=["元数据"])
app.include_router(sql_script.router, prefix="/api/v1", tags=["SQL脚本库"])
app.include_router(product_bible.router, prefix="/api/v1", tags=["产品圣经"])
app.include_router(obsidian.router, prefix="/api/v1", tags=["Obsidian 联动"])
app.include_router(work_report.router, prefix="/api/v1", tags=["AI总结报告"])
app.include_router(llm_provider.router, prefix="/api/v1", tags=["大模型管理"])
app.include_router(ai_qa.router, prefix="/api/v1", tags=["AI问答"])
app.include_router(material.router, prefix="/api/v1", tags=["业务资料库-材料"])
app.include_router(material.cat_router, prefix="/api/v1", tags=["业务资料库-分类"])
app.include_router(high_level.router, prefix="/api/v1", tags=["高级别工单"])
app.include_router(sensitive_req.router, prefix="/api/v1", tags=["敏感需求跟踪"])
app.include_router(workload_analysis.router, prefix="/api/v1", tags=["工作量分析"])


@app.on_event("startup")
async def startup_event():
    # 公网安全门禁：AUTH_REQUIRED 开启但密码未配置时拒绝启动（fail-closed）
    if settings.AUTH_REQUIRED and not settings.AUTH_PASSWORD:
        raise RuntimeError(
            "AUTH_REQUIRED=true 但 AUTH_PASSWORD 未配置，拒绝启动；"
            "请在 .env 中配置强密码后再开启鉴权"
        )
    logger.info("PMWB backend started")
    # 幂等创建缺失的数据表（对已有表无副作用；与 Alembic 不冲突）
    Base.metadata.create_all(bind=engine)
    # 首次运行种子化大模型提供方（从 settings 迁移 Kimi 配置，向后兼容）
    try:
        from db.base import SessionLocal
        from services.llm_provider import ensure_seed
        with SessionLocal() as s:
            ensure_seed(s)
    except Exception as e:  # noqa: BLE001
        logger.warning("LLM provider seed skipped: %s", e)
    # 存量迁移：主动优化工单「关联需求文号」由单值改一对多后，把历史 req_id 灌入
    # pmwb_active_optimization_req。幂等，可安全重复执行（create_all 只建表不搬数据）。
    try:
        from db.base import SessionLocal
        from services.active_optimization import active_optimization_service
        with SessionLocal() as s:
            n = active_optimization_service.migrate_legacy_req_ids(s)
        if n:
            logger.info("active_optimization legacy req_id migrated: %s rows", n)
    except Exception as e:  # noqa: BLE001
        logger.warning("active_optimization legacy migration skipped: %s", e)


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("PMWB backend stopped")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG,
    )
