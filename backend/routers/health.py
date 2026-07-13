from fastapi import APIRouter

from core.config import settings
from core.response import success

router = APIRouter()


@router.get("/health", summary="健康检查")
async def health_check():
    return success({
        "status": "ok",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
    })
