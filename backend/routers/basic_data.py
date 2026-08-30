"""基础数据路由：组织 + 人员主数据 CRUD、选人分组选项。

挂在 /api/v1/basic-data 下，是全站选人组件的统一数据源。
现在通过人员中台代理服务。
"""
from io import BytesIO
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.exceptions import NotFoundException, ValidationException
from core.response import success
from db.base import get_db
from db.models import PmwbBusinessDomain
from schemas.basic_data import (
    OrgCreate,
    OrgOption,
    OrgOut,
    OrgStaffImportOut,
    OrgUpdate,
    RoleCreate,
    RoleOption,
    RoleOut,
    RoleUpdate,
    StaffCreate,
    StaffOptionGroup,
    StaffOut,
    StaffUpdate,
)
from schemas.business_domain import (
    BusinessDomainCreate,
    BusinessDomainTreeNode,
    BusinessDomainUpdate,
)
from services.business_domain import (
    batch_set_domain as batch_set_domain_bd,
    create as create_business_domain,
    delete as delete_business_domain,
    get_related as get_domain_related,
    list_all as list_business_domains_all,
    list_tree as list_business_domains_tree,
    update as update_business_domain,
)
from services.basic_data import basic_data_service

router = APIRouter(prefix="/basic-data", tags=["团队信息"])


# ---------------------------------------------------------------------------
# 业务领域字典
# ---------------------------------------------------------------------------
# 业务领域 — 查询（供前端 BusinessDomainSelect 组件使用）
# ---------------------------------------------------------------------------
@router.get("/business-domains")
def list_business_domains(
    tree: bool = Query(False, description="true=返回树形结构，false=扁平列表"),
    group: Optional[str] = Query(None, description="按业务大类过滤：商客业务/政企业务/系统平台/公共能力/通用"),
    all: bool = Query(False, description="是否包含未启用的领域（管理页专用）"),
    db: Session = Depends(get_db),
):
    """返回业务领域列表。

    - tree=false（默认）：扁平列表，含 parent_domain_code 字段
    - tree=true：树形结构，根节点为一级大类
    - group：按业务大类过滤
    - all=true：含未启用（管理页用）
    """
    if tree:
        data = list_business_domains_tree(db, enabled_only=not all)
        return success(data=data)

    rows = list_business_domains_all(db, enabled_only=not all)

    # 如果是按 group 过滤，在内存过滤
    if group:
        rows = [r for r in rows if r.domain_group == group]

    return success(data=rows)


# ---------------------------------------------------------------------------
# 业务领域 — 管理 CRUD（仅管理入口使用）
# ---------------------------------------------------------------------------
@router.post("/business-domains")
def create_bd(payload: BusinessDomainCreate, db: Session = Depends(get_db)):
    """新增业务领域。"""
    return success(data=create_business_domain(db, payload), message="已创建")


@router.put("/business-domains/{domain_code}")
def update_bd(domain_code: str, payload: BusinessDomainUpdate, db: Session = Depends(get_db)):
    """修改业务领域。"""
    return success(data=update_business_domain(db, domain_code, payload), message="已更新")


@router.delete("/business-domains/{domain_code}")
def delete_bd(domain_code: str, db: Session = Depends(get_db)):
    """删除（软删除：enabled=False）。"""
    result = delete_business_domain(db, domain_code)
    return success(data=result, message="已删除")


@router.get("/business-domains/{domain_code}/related")
def get_bd_related(domain_code: str, db: Session = Depends(get_db)):
    """聚合某业务领域关联的知识条目 / 需求 / 会议 / 运营工单（知识中心按领域浏览详情）。"""
    return success(data=get_domain_related(db, domain_code))


class BatchSetDomainItem(BaseModel):
    """批量关联单条记录。"""
    source_type: str = Field(..., description="记录类型：requirement/ticket/meeting/operation/note/key_work")
    source_id: str = Field(..., description="记录主键（与各模型主键类型一致，字符串或数字均可）")
    domain_code: Optional[str] = Field(None, description="目标业务领域编码；None=置空")


class BatchSetDomainPayload(BaseModel):
    items: List[BatchSetDomainItem]
    overwrite: bool = Field(True, description="False=跳过已有关联(domain_code非空)，不覆盖存量")


@router.post("/business-domains/batch-set-domain")
def batch_set_bd(payload: BatchSetDomainPayload, db: Session = Depends(get_db)):
    """批量设置业务领域关联（知识中心关联便捷性优化 §3.11）。

    用于「批量关联 / 批量修正」场景：录单时漏选领域、或历史数据补关联。
    幂等安全：overwrite=False 跳过已有关联；未知类型 / 不存在记录计入 errors 不阻断其余。
    """
    result = batch_set_domain_bd(
        db, [it.model_dump() for it in payload.items], overwrite=payload.overwrite
    )
    return success(data=result, message=f"已更新 {result['updated']} 条，跳过 {result['skipped']} 条")


# ---------------------------------------------------------------------------
# 选人组件分组选项（放在最前，避免与 /orgs/{id} 混淆）
# ---------------------------------------------------------------------------
@router.get("/staff-options")
def staff_options(db: Session = Depends(get_db)):
    """按组织分组返回全量启用人员选项（选人组件数据源）。"""
    groups = basic_data_service.staff_options(db)
    return success(data=[StaffOptionGroup(**g).model_dump() for g in groups])


# ---------------------------------------------------------------------------
# 轻量选项（选人组件下拉用，不加载人员明细）
# ---------------------------------------------------------------------------
@router.get("/org-options")
def org_options(db: Session = Depends(get_db)):
    """返回启用的组织名称列表（轻量）。"""
    options = basic_data_service.org_options(db)
    return success(data=[OrgOption(**o).model_dump() for o in options])


@router.get("/role-options")
def role_options(db: Session = Depends(get_db)):
    """返回启用的身份名称列表（轻量）。"""
    options = basic_data_service.role_options(db)
    return success(data=[RoleOption(**r).model_dump() for r in options])


# ---------------------------------------------------------------------------
# 角色/身份定义 CRUD
# ---------------------------------------------------------------------------
@router.get("/roles")
def list_roles(db: Session = Depends(get_db)):
    roles = basic_data_service.list_roles(db)
    return success(data=[RoleOut(**r).model_dump() for r in roles])


@router.post("/roles")
def create_role(obj_in: RoleCreate, db: Session = Depends(get_db)):
    obj = basic_data_service.create_role(db, obj_in.model_dump(exclude_unset=True))
    if not obj:
        raise ValidationException("创建身份失败")
    return success(data=RoleOut(**obj).model_dump(), message="身份已创建")


@router.put("/roles/{role_id}")
def update_role(role_id: int, obj_in: RoleUpdate, db: Session = Depends(get_db)):
    obj = basic_data_service.update_role(db, role_id, obj_in.model_dump(exclude_unset=True))
    if not obj:
        raise NotFoundException(f"身份不存在：id={role_id}")
    return success(data=RoleOut(**obj).model_dump(), message="身份已更新")


@router.delete("/roles/{role_id}")
def delete_role(role_id: int, db: Session = Depends(get_db)):
    ok = basic_data_service.delete_role(db, role_id)
    if not ok:
        raise NotFoundException(f"身份不存在：id={role_id}")
    return success(data={"deleted": True}, message="身份已删除")


# ---------------------------------------------------------------------------
# 组织 CRUD
# ---------------------------------------------------------------------------
@router.get("/orgs")
def list_orgs(db: Session = Depends(get_db)):
    orgs = basic_data_service.list_orgs(db)
    return success(data=orgs)


@router.post("/orgs")
def create_org(obj_in: OrgCreate, db: Session = Depends(get_db)):
    obj = basic_data_service.create_org(db, obj_in.model_dump(exclude_unset=True))
    if not obj:
        raise ValidationException("创建组织失败")
    return success(data=obj, message="组织已创建")


@router.put("/orgs/{org_id}")
def update_org(org_id: int, obj_in: OrgUpdate, db: Session = Depends(get_db)):
    obj = basic_data_service.update_org(db, org_id, obj_in.model_dump(exclude_unset=True))
    if not obj:
        raise NotFoundException(f"组织不存在：id={org_id}")
    return success(data=obj, message="组织已更新")


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
    return success(data=staffs)


@router.post("/staffs")
def create_staff(obj_in: StaffCreate, db: Session = Depends(get_db)):
    obj = basic_data_service.create_staff(db, obj_in.model_dump(exclude_unset=True))
    if not obj:
        raise ValidationException("创建人员失败")
    return success(data=obj, message="人员已创建")


@router.put("/staffs/{staff_id}")
def update_staff(staff_id: int, obj_in: StaffUpdate, db: Session = Depends(get_db)):
    obj = basic_data_service.update_staff(db, staff_id, obj_in.model_dump(exclude_unset=True))
    if not obj:
        raise NotFoundException(f"人员不存在：id={staff_id}")
    return success(data=obj, message="人员已更新")


@router.delete("/staffs/{staff_id}")
def delete_staff(staff_id: int, db: Session = Depends(get_db)):
    ok = basic_data_service.delete_staff(db, staff_id)
    if not ok:
        raise NotFoundException(f"人员不存在：id={staff_id}")
    return success(data={"deleted": True}, message="人员已删除")


# ---------------------------------------------------------------------------
# 批量导入与模板
# ---------------------------------------------------------------------------
@router.post("/import")
def import_basic_data(
    file: UploadFile = File(..., description="Excel 文件，列：组织名称, 成员姓名, 邮箱, 电话, 身份, 排序号, 是否启用"),
    db: Session = Depends(get_db),
):
    """上传 Excel 批量导入/更新组织与人员（转发到人员中台）。"""
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise ValidationException("仅支持 .xlsx / .xls 文件")

    contents = file.file.read()
    result = basic_data_service.upload_and_import(contents, file.filename or "import.xlsx")

    if result.get("errors"):
        return success(
            data=OrgStaffImportOut(**result).model_dump(),
            message=f"导入完成：新增 {result['created_orgs']} 个组织、{result['created_staffs']} 名成员（含 {len(result['errors'])} 条错误）",
        )
    return success(
        data=OrgStaffImportOut(**result).model_dump(),
        message=f"导入完成：新增 {result['created_orgs']} 个组织、{result['created_staffs']} 名成员",
    )


@router.get("/template")
def download_template():
    """下载团队信息导入 Excel 模板。"""
    data = basic_data_service.build_template_bytes()
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="team_info_template.xlsx"',
        },
    )
