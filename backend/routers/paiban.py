"""排版管理路由（PB 批次，2026-11-19 起逐子任务扩展）。

pb-1 / L1 已交付端点：
  只读：GET  /paiban/meta                     枚举 + 倒排偏移 + 系统字典
        GET  /paiban/resolve?system=         系统→计划回落解析（专属 / 默认 / 待补）
        GET  /paiban/versions                计划列表（含派生截止与准入时点）
        GET  /paiban/versions/{plan_id}      计划详情 + 变更日志 + 下一版
  可写：POST /paiban/versions               登记版本计划
        PATCH /paiban/versions/{plan_id}     改期 / 状态 / 准入规则（逐字段留痕）

纪律：本文件只做参数收口与包络，全部口径在 services/paiban_version.py；
      request.js 已解 {code,message,data}，前端 api/paiban.js 禁二次解包。
      pb-2~pb-9 的端点追加在本文件，**静态路径须注册在 /{id} 之前**。
"""

from typing import Optional

from fastapi import APIRouter, Depends

from core.response import success
from db.base import get_db
from schemas.paiban import DeadlinePreviewRequest, VersionPlanCreate, VersionPlanUpdate
from services import paiban_version as svc

router = APIRouter(prefix="/paiban", tags=["排版管理"])


@router.get("/meta")
def get_meta(db=Depends(get_db)):
    """枚举、倒排偏移、例外原因闭集、系统字典（唯一来源）。"""
    return success(data=svc.meta(db))


@router.post("/deadlines/preview")
def preview_deadlines(payload: DeadlinePreviewRequest, db=Depends(get_db)):
    """登记页实时预览：倒排公式仍在 constants/paiban.py，前端不另算一份。"""
    return success(data=svc.preview(payload.release_date, payload.admit_mode, payload.admit_lead_days))


@router.get("/resolve")
def resolve(system: str = "", db=Depends(get_db)):
    """回落预览：无专属计划 → 统一默认；无有效计划 → 待补版本计划。"""
    return success(data=svc.resolve_plan(db, system))


@router.get("/versions")
def list_versions(
    scope_type: Optional[str] = None,
    system_name: Optional[str] = None,
    status: Optional[str] = None,
    include_cancelled: bool = False,
    db=Depends(get_db),
):
    """版本计划列表；派生四环节截止与准入判定时点随读随算，不落副本。"""
    return success(data=svc.list_plans(
        db, scope_type=scope_type, system_name=system_name,
        status=status, include_cancelled=include_cancelled,
    ))


@router.post("/versions")
def create_version(payload: VersionPlanCreate, db=Depends(get_db)):
    """登记版本计划；发布日是唯一基准，四环节截止由 −15/−8/−3/−1 自动派生。"""
    return success(data=svc.create_plan(db, payload.model_dump()), message="已登记")


@router.get("/versions/{plan_id}")
def get_version(plan_id: int, db=Depends(get_db)):
    """计划详情：派生截止 + 变更日志 + 顺延目标版本。"""
    return success(data=svc.get_plan(db, plan_id))


@router.patch("/versions/{plan_id}")
def update_version(plan_id: int, payload: VersionPlanUpdate, db=Depends(get_db)):
    """改期 / 改状态 / 改准入规则：逐字段写变更日志，默认计划改期不产生副本。"""
    return success(data=svc.update_plan(db, plan_id, payload.model_dump()), message="已更新并留痕")
