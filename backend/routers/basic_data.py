"""基础数据路由：组织 + 人员主数据 CRUD、选人分组选项。

挂在 /api/v1/basic-data 下，是全站选人组件的统一数据源。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.exceptions import NotFoundException
from core.response import success
from db.base import get_db
from schemas.basic_data import (
    OrgCreate,
    OrgOut,
    OrgUpdate,
    StaffCreate,
    StaffOptionGroup,
    StaffOut,
    StaffUpdate,
)
from services.basic_data import basic_data_service

router = APIRouter(prefix="/basic-data", tags=["基础数据"])


# ---------------------------------------------------------------------------
# 选人组件分组选项（放在最前，避免与 /orgs/{id} 混淆）
# ---------------------------------------------------------------------------
@router.get("/staff-options")
def staff_options(db: Session = Depends(get_db)):
    """按组织分组返回全量启用人员选项（选人组件数据源）。"""
    groups = basic_data_service.staff_options(db)
    return success(data=[StaffOptionGroup(**g).model_dump() for g in groups])


# ---------------------------------------------------------------------------
# 组织 CRUD
# ---------------------------------------------------------------------------
@router.get("/orgs")
def list_orgs(db: Session = Depends(get_db)):
    orgs = basic_data_service.list_orgs(db)
    result = []
    for o in orgs:
        out = OrgOut.model_validate(o)
        out.staff_count = len(o.staffs)
        result.append(out.model_dump())
    return success(data=result)


@router.post("/orgs")
def create_org(obj_in: OrgCreate, db: Session = Depends(get_db)):
    obj = basic_data_service.create_org(db, obj_in.model_dump(exclude_unset=True))
    return success(data=OrgOut.model_validate(obj).model_dump(), message="组织已创建")


@router.put("/orgs/{org_id}")
def update_org(org_id: int, obj_in: OrgUpdate, db: Session = Depends(get_db)):
    obj = basic_data_service.update_org(db, org_id, obj_in.model_dump(exclude_unset=True))
    if not obj:
        raise NotFoundException(f"组织不存在：id={org_id}")
    return success(data=OrgOut.model_validate(obj).model_dump(), message="组织已更新")


@router.delete("/orgs/{org_id}")
def delete_org(org_id: int, db: Session = Depends(get_db)):
    ok = basic_data_service.delete_org(db, org_id)
    if not ok:
        raise NotFoundException(f"组织不存在：id={org_id}")
    return success(data={"deleted": True}, message="组织已删除")


# ---------------------------------------------------------------------------
# 人员 CRUD
# ---------------------------------------------------------------------------
@router.get("/staffs")
def list_staffs(
    org_id: Optional[int] = Query(None, description="按组织过滤"),
    keyword: Optional[str] = Query(None, description="姓名/邮箱关键字"),
    db: Session = Depends(get_db),
):
    staffs = basic_data_service.list_staffs(db, org_id=org_id, keyword=keyword)
    result = []
    for s in staffs:
        out = StaffOut.model_validate(s)
        out.org_name = s.org.name if s.org else None
        result.append(out.model_dump())
    return success(data=result)


@router.post("/staffs")
def create_staff(obj_in: StaffCreate, db: Session = Depends(get_db)):
    obj = basic_data_service.create_staff(db, obj_in.model_dump(exclude_unset=True))
    out = StaffOut.model_validate(obj)
    out.org_name = obj.org.name if obj.org else None
    return success(data=out.model_dump(), message="人员已创建")


@router.put("/staffs/{staff_id}")
def update_staff(staff_id: int, obj_in: StaffUpdate, db: Session = Depends(get_db)):
    obj = basic_data_service.update_staff(db, staff_id, obj_in.model_dump(exclude_unset=True))
    if not obj:
        raise NotFoundException(f"人员不存在：id={staff_id}")
    out = StaffOut.model_validate(obj)
    out.org_name = obj.org.name if obj.org else None
    return success(data=out.model_dump(), message="人员已更新")


@router.delete("/staffs/{staff_id}")
def delete_staff(staff_id: int, db: Session = Depends(get_db)):
    ok = basic_data_service.delete_staff(db, staff_id)
    if not ok:
        raise NotFoundException(f"人员不存在：id={staff_id}")
    return success(data={"deleted": True}, message="人员已删除")
