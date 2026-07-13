from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from services.dashboard import DashboardService

router = APIRouter(prefix="/dashboard", tags=["首页看板"])


@router.get("")
def get_dashboard(db: Session = Depends(get_db)):
    """获取首页看板数据。"""
    service = DashboardService(db)
    return success(data=service.get_dashboard())
