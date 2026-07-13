from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.base import get_db
from schemas.dashboard import DashboardData
from services.dashboard import DashboardService

router = APIRouter(prefix="/dashboard", tags=["首页看板"])


@router.get("", response_model=DashboardData)
def get_dashboard(db: Session = Depends(get_db)):
    """获取首页看板数据。"""
    service = DashboardService(db)
    return service.get_dashboard()
