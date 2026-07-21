"""重点工作 KeyWork 路由：主 CRUD + 子表单条增删 + 交付物 + 看板统计。

挂在 /api/v1/key-works 下。
"""
import os
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from core.exceptions import NotFoundException
from core.response import success
from db.base import get_db
from db.models import (
    PmwbKeyWorkDeliverable,
    PmwbKeyWorkMember,
    PmwbKeyWorkMemberTask,
    PmwbKeyWorkMilestone,
    PmwbKeyWorkMonthlyPlan,
    PmwbKeyWorkProgress,
    PmwbKeyWorkWeeklyPlan,
)
from schemas.keywork import (
    KeyWorkCreate,
    KeyWorkListResponse,
    KeyWorkMemberCreate,
    KeyWorkMemberTaskCreate,
    KeyWorkMemberTaskUpdate,
    KeyWorkMilestoneCreate,
    KeyWorkMilestoneUpdate,
    KeyWorkMonthlyPlanCreate,
    KeyWorkOut,
    KeyWorkProgressCreate,
    KeyWorkUpdate,
    KeyWorkWeeklyPlanCreate,
)
from services import keywork_deliverable as deliverable_svc
from services.keywork import keywork_service

router = APIRouter(prefix="/key-works", tags=["重点工作"])


# ---------------------------------------------------------------------------
# 列表 / 统计 / 详情 / 主 CRUD
# ---------------------------------------------------------------------------
@router.get("")
def list_key_works(
    keyword: Optional[str] = Query(None, description="关键字搜索"),
    category: Optional[str] = Query(None, description="分类：hq_pilot/annual_task/special_topic"),
    status: Optional[str] = Query(None, description="状态"),
    owner: Optional[str] = Query(None, description="负责人"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=1000, description="每页条数"),
    db: Session = Depends(get_db),
):
    """查询重点工作列表。"""
    result = keywork_service.list_with_filters(
        db=db,
        keyword=keyword,
        category=category,
        status=status,
        owner=owner,
        page=page,
        page_size=page_size,
    )
    return success(data=KeyWorkListResponse(**result).model_dump())


@router.get("/stats")
def key_works_stats(db: Session = Depends(get_db)):
    """看板聚合统计（按分类/状态计数、超期成员待办、未来30天里程碑等）。"""
    return success(data=keywork_service.stats(db))


@router.get("/{kw_id}")
def get_key_work(kw_id: int, db: Session = Depends(get_db)):
    """获取重点工作详情（含全部子表）。"""
    obj = keywork_service.get(db, kw_id)
    if not obj:
        raise NotFoundException(f"重点工作不存在：id={kw_id}")
    return success(data=KeyWorkOut.model_validate(obj))


@router.post("")
def create_key_work(obj_in: KeyWorkCreate, db: Session = Depends(get_db)):
    """创建重点工作（含子表）。"""
    obj = keywork_service.create_with_relations(db, obj_in.model_dump())
    return success(data=KeyWorkOut.model_validate(obj))


@router.put("/{kw_id}")
def update_key_work(kw_id: int, obj_in: KeyWorkUpdate, db: Session = Depends(get_db)):
    """更新重点工作（标量 + 提供的子表全量替换）。"""
    obj = keywork_service.update(db, kw_id, obj_in.model_dump(exclude_unset=True))
    if not obj:
        raise NotFoundException(f"重点工作不存在：id={kw_id}")
    return success(data=KeyWorkOut.model_validate(obj))


@router.delete("/{kw_id}")
def delete_key_work(kw_id: int, db: Session = Depends(get_db)):
    """删除重点工作（级联子表）。"""
    ok = keywork_service.delete(db, kw_id)
    return success(data={"deleted": ok})


# ---------------------------------------------------------------------------
# 进展日志
# ---------------------------------------------------------------------------
@router.post("/{kw_id}/progress")
def add_progress(kw_id: int, payload: KeyWorkProgressCreate, db: Session = Depends(get_db)):
    """追加一条进展日志。"""
    if not keywork_service.get(db, kw_id):
        raise NotFoundException(f"重点工作不存在：id={kw_id}")
    row = PmwbKeyWorkProgress(key_work_id=kw_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return success(data=row)


@router.delete("/{kw_id}/progress/{pid}")
def delete_progress(kw_id: int, pid: int, db: Session = Depends(get_db)):
    """删除一条进展日志。"""
    row = db.query(PmwbKeyWorkProgress).filter(
        PmwbKeyWorkProgress.id == pid,
        PmwbKeyWorkProgress.key_work_id == kw_id,
    ).first()
    if not row:
        raise NotFoundException("进展日志不存在")
    db.delete(row)
    db.commit()
    return success(data={"deleted": True})


# ---------------------------------------------------------------------------
# 成员待办
# ---------------------------------------------------------------------------
@router.post("/{kw_id}/member-tasks")
def add_member_task(kw_id: int, payload: KeyWorkMemberTaskCreate, db: Session = Depends(get_db)):
    """追加一条成员待办。"""
    if not keywork_service.get(db, kw_id):
        raise NotFoundException(f"重点工作不存在：id={kw_id}")
    row = PmwbKeyWorkMemberTask(key_work_id=kw_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return success(data=row)


@router.put("/{kw_id}/member-tasks/{tid}")
def update_member_task(kw_id: int, tid: int, payload: KeyWorkMemberTaskUpdate, db: Session = Depends(get_db)):
    """更新一条成员待办（部分字段）。"""
    row = db.query(PmwbKeyWorkMemberTask).filter(
        PmwbKeyWorkMemberTask.id == tid,
        PmwbKeyWorkMemberTask.key_work_id == kw_id,
    ).first()
    if not row:
        raise NotFoundException("成员待办不存在")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return success(data=row)


@router.delete("/{kw_id}/member-tasks/{tid}")
def delete_member_task(kw_id: int, tid: int, db: Session = Depends(get_db)):
    """删除一条成员待办。"""
    row = db.query(PmwbKeyWorkMemberTask).filter(
        PmwbKeyWorkMemberTask.id == tid,
        PmwbKeyWorkMemberTask.key_work_id == kw_id,
    ).first()
    if not row:
        raise NotFoundException("成员待办不存在")
    db.delete(row)
    db.commit()
    return success(data={"deleted": True})


# ---------------------------------------------------------------------------
# 里程碑
# ---------------------------------------------------------------------------
@router.post("/{kw_id}/milestones")
def add_milestone(kw_id: int, payload: KeyWorkMilestoneCreate, db: Session = Depends(get_db)):
    """追加一个里程碑。"""
    if not keywork_service.get(db, kw_id):
        raise NotFoundException(f"重点工作不存在：id={kw_id}")
    row = PmwbKeyWorkMilestone(key_work_id=kw_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return success(data=row)


@router.put("/{kw_id}/milestones/{mid}")
def update_milestone(kw_id: int, mid: int, payload: KeyWorkMilestoneUpdate, db: Session = Depends(get_db)):
    """更新一个里程碑（部分字段）。"""
    row = db.query(PmwbKeyWorkMilestone).filter(
        PmwbKeyWorkMilestone.id == mid,
        PmwbKeyWorkMilestone.key_work_id == kw_id,
    ).first()
    if not row:
        raise NotFoundException("里程碑不存在")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return success(data=row)


@router.delete("/{kw_id}/milestones/{mid}")
def delete_milestone(kw_id: int, mid: int, db: Session = Depends(get_db)):
    """删除一个里程碑。"""
    row = db.query(PmwbKeyWorkMilestone).filter(
        PmwbKeyWorkMilestone.id == mid,
        PmwbKeyWorkMilestone.key_work_id == kw_id,
    ).first()
    if not row:
        raise NotFoundException("里程碑不存在")
    db.delete(row)
    db.commit()
    return success(data={"deleted": True})


# ---------------------------------------------------------------------------
# 团队成员
# ---------------------------------------------------------------------------
@router.post("/{kw_id}/members")
def add_member(kw_id: int, payload: KeyWorkMemberCreate, db: Session = Depends(get_db)):
    """追加一名团队成员。"""
    if not keywork_service.get(db, kw_id):
        raise NotFoundException(f"重点工作不存在：id={kw_id}")
    row = PmwbKeyWorkMember(key_work_id=kw_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return success(data=row)


@router.delete("/{kw_id}/members/{mid}")
def delete_member(kw_id: int, mid: int, db: Session = Depends(get_db)):
    """删除一名团队成员。"""
    row = db.query(PmwbKeyWorkMember).filter(
        PmwbKeyWorkMember.id == mid,
        PmwbKeyWorkMember.key_work_id == kw_id,
    ).first()
    if not row:
        raise NotFoundException("成员不存在")
    db.delete(row)
    db.commit()
    return success(data={"deleted": True})


# ---------------------------------------------------------------------------
# 月度计划
# ---------------------------------------------------------------------------
@router.post("/{kw_id}/monthly-plans")
def add_monthly_plan(kw_id: int, payload: KeyWorkMonthlyPlanCreate, db: Session = Depends(get_db)):
    """追加一条月度计划。"""
    if not keywork_service.get(db, kw_id):
        raise NotFoundException(f"重点工作不存在：id={kw_id}")
    row = PmwbKeyWorkMonthlyPlan(key_work_id=kw_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return success(data=row)


@router.delete("/{kw_id}/monthly-plans/{pid}")
def delete_monthly_plan(kw_id: int, pid: int, db: Session = Depends(get_db)):
    """删除一条月度计划。"""
    row = db.query(PmwbKeyWorkMonthlyPlan).filter(
        PmwbKeyWorkMonthlyPlan.id == pid,
        PmwbKeyWorkMonthlyPlan.key_work_id == kw_id,
    ).first()
    if not row:
        raise NotFoundException("月度计划不存在")
    db.delete(row)
    db.commit()
    return success(data={"deleted": True})


# ---------------------------------------------------------------------------
# 周计划
# ---------------------------------------------------------------------------
@router.post("/{kw_id}/weekly-plans")
def add_weekly_plan(kw_id: int, payload: KeyWorkWeeklyPlanCreate, db: Session = Depends(get_db)):
    """追加一条周计划。"""
    if not keywork_service.get(db, kw_id):
        raise NotFoundException(f"重点工作不存在：id={kw_id}")
    row = PmwbKeyWorkWeeklyPlan(key_work_id=kw_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return success(data=row)


@router.delete("/{kw_id}/weekly-plans/{pid}")
def delete_weekly_plan(kw_id: int, pid: int, db: Session = Depends(get_db)):
    """删除一条周计划。"""
    row = db.query(PmwbKeyWorkWeeklyPlan).filter(
        PmwbKeyWorkWeeklyPlan.id == pid,
        PmwbKeyWorkWeeklyPlan.key_work_id == kw_id,
    ).first()
    if not row:
        raise NotFoundException("周计划不存在")
    db.delete(row)
    db.commit()
    return success(data={"deleted": True})


# ---------------------------------------------------------------------------
# 交付物
# ---------------------------------------------------------------------------
@router.post("/{kw_id}/deliverables/upload")
def upload_deliverable(
    kw_id: int,
    file: UploadFile = File(...),
    deliverable_type: Optional[str] = Form("other"),
    note: Optional[str] = Form(None),
    uploaded_by: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """上传一个交付物到 Obsidian vault 并记元数据。"""
    content = file.file.read()
    data = deliverable_svc.upload_deliverable(
        db,
        kw_id,
        file.filename or "未命名文件",
        content,
        uploaded_by=uploaded_by,
        deliverable_type=deliverable_type or "other",
        note=note,
    )
    return success(data=data, message="上传成功")


@router.get("/{kw_id}/deliverables")
def list_deliverables(kw_id: int, db: Session = Depends(get_db)):
    """列出重点工作交付物元数据。"""
    items = deliverable_svc.list_deliverables(db, kw_id)
    return success(data={"total": len(items), "items": items})


@router.get("/{kw_id}/deliverables/{did}/download")
def download_deliverable(kw_id: int, did: int, db: Session = Depends(get_db)):
    """下载交付物文件。"""
    fp = deliverable_svc.get_deliverable_path(db, kw_id, did)
    folder = os.path.dirname(fp)
    if not os.path.abspath(fp).startswith(os.path.abspath(folder)):
        raise HTTPException(status_code=403, detail="非法路径")
    if not os.path.isfile(fp):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(fp, filename=os.path.basename(fp))


@router.delete("/{kw_id}/deliverables/{did}")
def delete_deliverable(kw_id: int, did: int, db: Session = Depends(get_db)):
    """删除交付物（文件 + 元数据）。"""
    ok = deliverable_svc.delete_deliverable(db, kw_id, did)
    return success(data={"deleted": ok})
