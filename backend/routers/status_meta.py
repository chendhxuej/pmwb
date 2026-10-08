"""状态元数据路由：把「状态注册表」暴露给前端（唯一真相源）。

前端启动时拉取一次并缓存，用于渲染徽标 label/tone、筛选下拉、流转下拉可选目标、
总览矩阵列与邮件/详情文案。新增状态后只需改 backend/constants/status_registry.py，
前端无需改动即可自动兼容。
"""

from fastapi import APIRouter

from constants import status_registry
from core.response import success

router = APIRouter(prefix="/meta", tags=["元数据"])


@router.get("/status-domains")
def get_status_domains():
    """全站状态域元数据（状态注册表序列化）。"""
    return success(data=status_registry.as_metadata())
