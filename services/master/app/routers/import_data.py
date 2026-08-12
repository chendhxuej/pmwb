"""数据导入路由：触发邮件中心通讯录 / sa_info 导入。"""
from typing import List

from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from schemas.basic_data import ImportStatsOut
from services.import_service import contact_import_service

router = APIRouter(prefix="/import", tags=["数据导入"])


@router.post("/contacts")
def import_email_contacts(
    contacts: List[dict] = Body(..., description="邮件中心联系人JSON数组"),
    db: Session = Depends(get_db),
):
    """批量导入邮件中心通讯录数据。"""
    result = contact_import_service.import_email_center_contacts(db, contacts)
    return success(
        data=ImportStatsOut(**result).model_dump(),
        message=f"导入完成：新增 {result['created_staffs']} 人，更新 {result['updated_staffs']} 人",
    )


@router.post("/sa-info")
def import_sa_info(
    sa_rows: List[dict] = Body(..., description="sa_info 行数据"),
    db: Session = Depends(get_db),
):
    """批量导入 PMWB sa_info 数据。"""
    result = contact_import_service.import_sa_info(db, sa_rows)
    return success(
        data=ImportStatsOut(**result).model_dump(),
        message=f"导入完成：新增 {result['created_staffs']} 人，更新 {result['updated_staffs']} 人",
    )
