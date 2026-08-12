"""人员主数据中间件 — FastAPI 入口。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.exceptions import MasterException
from core.response import error
from routers.basic_data import router as basic_data_router
from routers.import_data import router as import_router

app = FastAPI(title="PMWB Master Service", version="0.1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由注册
app.include_router(basic_data_router, prefix="/api/v1")
app.include_router(import_router, prefix="/api/v1")


# 异常处理
@app.exception_handler(MasterException)
def master_exception_handler(_, exc: MasterException):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=exc.status_code,
        content=error(exc.message, exc.code),
    )


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": "pmwb-master-service"}
