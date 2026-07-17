import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from core.exceptions import PMWBException
from db.base import engine
from db.models import Base  # noqa: F401
from routers import (
    dashboard,
    dev_ticket,
    health,
    knowledge,
    mail_center,
    meeting,
    obsidian,
    plugin,
    operation,
    product_bible,
    reminder,
    requirement,
    todo,
)


def setup_logging() -> logging.Logger:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"pmwb_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO if not settings.DEBUG else logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return logging.getLogger("pmwb")


logger = setup_logging()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="产品经理个人工作台 API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
app.include_router(operation.router, prefix="/api/v1", tags=["业务运营监控"])
app.include_router(meeting.router, prefix="/api/v1", tags=["会议管理"])
app.include_router(knowledge.router, prefix="/api/v1", tags=["知识库"])
app.include_router(mail_center.router, prefix="/api/v1", tags=["邮件中心"])
app.include_router(plugin.router, prefix="/api/v1", tags=["插件接入"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["首页看板"])
app.include_router(todo.router, prefix="/api/v1", tags=["待办中心"])
app.include_router(requirement.router, prefix="/api/v1", tags=["需求管理"])
app.include_router(dev_ticket.router, prefix="/api/v1", tags=["开发工单"])
app.include_router(reminder.router, prefix="/api/v1", tags=["邮件催办"])
app.include_router(product_bible.router, prefix="/api/v1", tags=["产品圣经"])
app.include_router(obsidian.router, prefix="/api/v1", tags=["Obsidian 联动"])


@app.on_event("startup")
async def startup_event():
    logger.info("PMWB backend started")
    # 幂等创建缺失的数据表（对已有表无副作用；与 Alembic 不冲突）
    Base.metadata.create_all(bind=engine)


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
