from fastapi import APIRouter

from core.response import success
from utils.email import EmailCenterClient

router = APIRouter(prefix="/mail-center", tags=["邮件中心"])

client = EmailCenterClient()


@router.get("/health")
def mail_center_health():
    """检查统一邮件中心(3210)健康状态。"""
    data = client.health_check()
    return success(data=data)
