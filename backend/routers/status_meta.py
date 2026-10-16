"""状态元数据路由：把「状态注册表」暴露给前端（唯一真相源）。

前端启动时拉取一次并缓存，用于渲染徽标 label/tone、筛选下拉、流转下拉可选目标、
总览矩阵列与邮件/详情文案。新增状态后只需改 backend/constants/status_registry.py，
前端无需改动即可自动兼容。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from constants import status_registry
from core.response import success
from db.base import get_db
from schemas.vendor_dev import VendorTeamCreate, VendorTeamUpdate
from services import vendor_dev as vendor_dev_service

router = APIRouter(prefix="/meta", tags=["元数据"])


@router.get("/status-domains")
def get_status_domains():
    """全站状态域元数据（状态注册表序列化）。"""
    return success(data=status_registry.as_metadata())


# ---------------------------------------------------------------------------
# 厂家团队「别名映射」字典
#
# 注意：本字典**不是**厂家清单的源头，只负责把工单标题里的厂家名/系统别名
# 归一到 system_name。厂家清单的唯一源是「团队评估」中工作量 > 0 的系统。
# ---------------------------------------------------------------------------


@router.get("/vendor-teams")
def list_vendor_teams(db: Session = Depends(get_db)):
    """厂家团队别名映射列表。"""
    return success(data=vendor_dev_service.list_vendor_teams(db))


@router.post("/vendor-teams")
def create_vendor_team(obj_in: VendorTeamCreate, db: Session = Depends(get_db)):
    try:
        data = vendor_dev_service.create_vendor_team(db, obj_in.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(data=data, message=f"厂家团队「{data.get('team_name')}」已新增")


@router.put("/vendor-teams/{team_id}")
def update_vendor_team(team_id: int, obj_in: VendorTeamUpdate, db: Session = Depends(get_db)):
    data = vendor_dev_service.update_vendor_team(db, team_id, obj_in.model_dump(exclude_unset=True))
    if not data:
        raise HTTPException(status_code=404, detail="厂家团队不存在")
    return success(data=data, message="已更新")


@router.delete("/vendor-teams/{team_id}")
def delete_vendor_team(team_id: int, db: Session = Depends(get_db)):
    ok = vendor_dev_service.delete_vendor_team(db, team_id)
    return success(data={"deleted": ok})
