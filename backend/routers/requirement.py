from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from schemas.requirement import (
    EvaluationCreate,
    EvaluationUpdate,
    RequirementCategoryCreate,
    RequirementCategoryUpdate,
    RequirementCreate,
    RequirementDeliverableCreate,
    RequirementExtUpdate,
    RiskFlagBatchIn,
)
from schemas.vendor_dev import VendorDevCreate, VendorDevUpdate, VendorManualUpload
from services import vendor_dev as vendor_dev_service
from services import requirement_category as category_service
from services.obsidian_link import (
    add_requirement_deliverable,
    get_requirement_deliverables,
    remove_requirement_deliverable,
)
from services.requirement import requirement_service
from services.requirement_delivery import init_folder

router = APIRouter(prefix="/requirements", tags=["需求管理"])


@router.get("")
def list_requirements(
    keyword: Optional[str] = Query(None, description="关键字搜索"),
    req_id: Optional[str] = Query(None, description="需求文号模糊匹配"),
    dev_ticket_no: Optional[str] = Query(None, description="开发单号模糊匹配"),
    status: Optional[str] = Query(None, description="个人跟踪状态"),
    priority: Optional[str] = Query(None, description="优先级"),
    category: Optional[str] = Query(None, description="需求分类（精确匹配）"),
    system_name: Optional[str] = Query(None, description="系统名称"),
    is_involved: Optional[int] = Query(None, description="是否涉及开发"),
    dev_days_gt: Optional[int] = Query(
        None, ge=1, description="已开发天数严格大于 N（口径：开发中且未上线，与 dev 超期专题同源）"
    ),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=1000, description="每页条数"),
    db: Session = Depends(get_db),
):
    """查询需求列表。"""
    data = requirement_service.list_with_filters(
        db=db,
        keyword=keyword,
        req_id=req_id,
        dev_ticket_no=dev_ticket_no,
        status=status,
        priority=priority,
        category=category,
        system_name=system_name,
        is_involved=is_involved,
        dev_days_gt=dev_days_gt,
        page=page,
        page_size=page_size,
    )
    return success(data=data)


@router.post("")
def create_requirement(obj_in: RequirementCreate, db: Session = Depends(get_db)):
    """手工新建需求（插件未抓到的需求在工作台直接录入）。

    - 需求文号留空 → 自动生成「手工需求（2026）第（MMDDNNN）号」
    - 需求文号已存在 → 400 拒绝（避免误覆盖历史需求）
    - 新建记录 origin='manual'，需求宇宙口径不变（列表/统计/任务中心自动纳入）
    """
    try:
        data = requirement_service.create_requirement(db, obj_in.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(data=data, message=f"需求「{data.get('req_id')}」已创建")


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """获取需求统计。"""
    return success(data=requirement_service.get_stats(db))


@router.get("/meta/systems")
def get_systems(db: Session = Depends(get_db)):
    """获取所有系统名称。"""
    return success(data=requirement_service.get_systems(db))


# ---------------------------------------------------------------------------
# 需求分类字典（唯一真相源：工单分类以 pmwb_requirement_category.name 为准）
# 注意：这些字面路径必须注册在 GET /{req_id} 之前，否则 "categories" 会被吞成 req_id
# ---------------------------------------------------------------------------


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    """分类管理视图：全量（含停用），带工单引用计数。"""
    return success(data=category_service.list_categories(db))


@router.get("/categories/options")
def list_category_options(db: Session = Depends(get_db)):
    """分类下拉选项：仅启用，按排序号+名称排序。"""
    return success(data=category_service.list_options(db))


@router.post("/categories")
def create_category(obj_in: RequirementCategoryCreate, db: Session = Depends(get_db)):
    """新增分类（名称去重校验）。"""
    try:
        data = category_service.create_category(db, obj_in.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(data=data, message=f"分类「{data['name']}」已创建")


@router.put("/categories/{cat_id}")
def update_category(cat_id: int, obj_in: RequirementCategoryUpdate, db: Session = Depends(get_db)):
    """更新分类；改名时级联更新存量工单的 category（保证统计口径不分裂）。"""
    try:
        data = category_service.update_category(db, cat_id, obj_in.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(data=data)


@router.delete("/categories/{cat_id}")
def delete_category(cat_id: int, db: Session = Depends(get_db)):
    """删除分类：被工单引用时 400 拒绝（提示改用停用）。"""
    try:
        data = category_service.delete_category(db, cat_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(data=data, message=f"分类「{data.get('name')}」已删除")


@router.put("/risk-flag/batch")
def batch_risk_flag(obj_in: RiskFlagBatchIn, db: Session = Depends(get_db)):
    """超期风险标记批量打标/取消（单个打标 = 传一个 req_id）。

    注意：字面路径注册在 GET /{req_id} 之前（沿袭 categories 注册顺序教训）。
    """
    try:
        data = requirement_service.set_risk_flag(db, obj_in.req_ids, obj_in.action, obj_in.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(data=data)


@router.get("/{req_id}")
def get_requirement(req_id: str, db: Session = Depends(get_db)):
    """获取需求详情。"""
    data = requirement_service.get(db, req_id)
    return success(data=data)


@router.get("/{req_id}/evaluations")
def get_evaluations(req_id: str, db: Session = Depends(get_db)):
    """获取需求下所有团队评估记录（按SA/系统维度）。"""
    data = requirement_service.get_evaluations(db, req_id)
    return success(data=data)


@router.post("/{req_id}/evaluations")
def create_evaluation(req_id: str, obj_in: EvaluationCreate, db: Session = Depends(get_db)):
    """新增一条团队评估记录（手动录入）。"""
    data = requirement_service.create_evaluation(db, req_id, obj_in.model_dump(exclude_unset=True))
    return success(data=data)


@router.put("/{req_id}/evaluations/{eval_id}")
def update_evaluation(req_id: str, eval_id: int, obj_in: EvaluationUpdate, db: Session = Depends(get_db)):
    """更新团队评估记录（SA/系统/工作量/复核工作量/评估意见/开发单号）。"""
    data = requirement_service.update_evaluation(db, eval_id, obj_in.model_dump(exclude_unset=True))
    return success(data=data)


@router.delete("/{req_id}/evaluations/{eval_id}")
def delete_evaluation(req_id: str, eval_id: int, db: Session = Depends(get_db)):
    """删除一条团队评估记录。"""
    ok = requirement_service.delete_evaluation(db, eval_id)
    return success(data={"deleted": ok})


@router.put("/{req_id}")
def update_requirement(req_id: str, obj_in: RequirementExtUpdate, db: Session = Depends(get_db)):
    """更新需求个人跟踪信息。"""
    data = requirement_service.update_ext(db, req_id, obj_in.model_dump(exclude_unset=True))
    return success(data=data)


@router.delete("/{req_id}")
def delete_requirement(req_id: str, db: Session = Depends(get_db)):
    """删除需求：删除扩展、团队评估、用户故事。

    手工新建（origin='manual'）的需求连同 sent_emails 源行一并删除（避免复活）；
    插件抓取的邮件源行保持只读保留。
    """
    data = requirement_service.delete_requirement(db, req_id)
    return success(data=data)


# ---------------------------------------------------------------------------
# 需求直挂交付物（kc4-4）：JSON 交付物的增删查
# ---------------------------------------------------------------------------


@router.get("/{req_id}/deliverables")
def list_requirement_deliverables(req_id: str, db: Session = Depends(get_db)):
    """列举需求直挂交付物。"""
    return success(data=get_requirement_deliverables(db, req_id))


@router.post("/{req_id}/deliverables")
def create_requirement_deliverable(
    req_id: str, payload: RequirementDeliverableCreate, db: Session = Depends(get_db)
):
    """新增一条需求直挂交付物。"""
    entry = add_requirement_deliverable(
        db, req_id, file_name=payload.file_name, local_path=payload.local_path, note=payload.note
    )
    return success(data=entry)


@router.delete("/{req_id}/deliverables/{index}")
def delete_requirement_deliverable(req_id: str, index: int, db: Session = Depends(get_db)):
    """按索引删除一条需求直挂交付物。"""
    ok = remove_requirement_deliverable(db, req_id, index)
    return success(data={"deleted": ok})


# ---------------------------------------------------------------------------
# 厂家开发状态（2026-10-16 新增，生产部署环节）
#
# 口径铁律：厂家清单 = 「团队评估」中工作量 > 0 人天的系统，
# 唯一实现 services/vendor_dev.py::active_team_systems，本路由不做第二份判定。
# ---------------------------------------------------------------------------


@router.get("/{req_id}/vendor-devs")
def get_vendor_devs(req_id: str, db: Session = Depends(get_db)):
    """需求下各厂家的开发状态（实时按团队评估重算，缺失的活跃厂家自动补行）。"""
    return success(data=vendor_dev_service.list_vendor_devs(db, req_id))


@router.post("/{req_id}/vendor-devs")
def add_vendor_dev(req_id: str, obj_in: VendorDevCreate, db: Session = Depends(get_db)):
    """手工新增一个厂家行。"""
    try:
        data = vendor_dev_service.create_vendor_dev(
            db, req_id, obj_in.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(data=data, message=f"厂家「{data.get('system_name')}」已新增")


@router.put("/{req_id}/vendor-devs/{vendor_dev_id}")
def modify_vendor_dev(
    req_id: str, vendor_dev_id: int, obj_in: VendorDevUpdate, db: Session = Depends(get_db)
):
    """更新厂家行（改状态走状态注册表流转校验）。

    置「已完成」时：若该需求**所有活跃厂家**都已完成，自动触发上线联动
    （跟踪状态 → 已上线；实际上线日 → 当周周四，**仅当为空时写入**）。
    """
    try:
        data = vendor_dev_service.update_vendor_dev(
            db, vendor_dev_id, obj_in.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not data:
        raise HTTPException(status_code=404, detail="厂家行不存在")

    message = "已更新"
    fz = data.get("finalized") or {}
    if fz.get("finalized"):
        message = "该厂家已完成，需求已联动置为「已上线」"
        if fz.get("delivered_date"):
            message += f"，实际上线日写入 {fz['delivered_date']}"
    elif fz.get("skipped"):
        message = f"{message}（{fz.get('reason', '')}）"
    return success(data=data, message=message)


@router.delete("/{req_id}/vendor-devs/{vendor_dev_id}")
def remove_vendor_dev(req_id: str, vendor_dev_id: int, db: Session = Depends(get_db)):
    """删除一个厂家行（不存在的 id 返回 deleted=False，保持既有删除契约）。"""
    ok = vendor_dev_service.delete_vendor_dev(db, vendor_dev_id)
    return success(data={"deleted": ok})


@router.post("/{req_id}/vendor-devs/{vendor_dev_id}/manual")
def upload_vendor_manual(
    req_id: str,
    vendor_dev_id: int,
    obj_in: VendorManualUpload,
    db: Session = Depends(get_db),
):
    """上传某厂家的操作手册（插件抓到手册后回传，JSON body 传 base64）。

    注意：厂家手册**不落 PmwbReqManual**（那张表是「按系统的操作手册」卡片在用，
    unique(req_id, system_name) 会互相覆盖），而是记在该厂家行自己的字段上。
    """
    import base64

    try:
        content = base64.b64decode(obj_in.content_base64)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="content_base64 解码失败")

    folder = init_folder(db, req_id)["folder"]
    data = vendor_dev_service.save_vendor_manual(db, vendor_dev_id, obj_in.filename, content, folder)
    if not data:
        raise HTTPException(status_code=404, detail="厂家行不存在")
    return success(data=data, message=f"厂家手册「{obj_in.filename}」已上传")
