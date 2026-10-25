"""敏感需求跟踪路由（需求与交付子模块，2026-10-25）。

职责：P0/P1 敏感需求自动入池 + 5 阶段倒排（需求×团队×阶段）+ 团队调度督办。

只读：GET /sensitive-reqs、GET /sensitive-reqs/stats、
      GET /sensitive-reqs/{req_id}/detail、GET /sensitive-reqs/{req_id}/plan-suggestion
可写：POST /sensitive-reqs/sync（幂等全量重算跟踪表）
      PATCH /sensitive-reqs/track/{req_id}（人工跟踪态/锁定/移出）
      PUT /sensitive-reqs/{req_id}/milestones（倒排全量保存）
      PATCH /sensitive-reqs/milestone/{milestone_id}（单里程碑修正）
      POST /sensitive-reqs/draft（草稿预览）、POST /sensitive-reqs/send（真实发信，须 confirm_send=true）

督办历史查询复用统一入口：GET /mail-dispatch/records?ref_type=sensitive_req&ref_id=<req_id>
"""

from typing import Optional

from fastapi import APIRouter, Depends

from core.response import success
from db.base import get_db
from schemas.sensitive_req import (
    SensitiveReqMilestoneSaveRequest,
    SensitiveReqMilestoneUpdateRequest,
    SensitiveReqQuery,
    SensitiveReqSendRequest,
    SensitiveReqTrackUpdateRequest,
)
from services.sensitive_req import sensitive_req_service

router = APIRouter(prefix="/sensitive-reqs", tags=["敏感需求跟踪"])


@router.get("")
def list_reqs(
    track_status: Optional[str] = None,
    team: Optional[str] = None,
    keyword: Optional[str] = None,
    only_overdue: bool = False,
    include_closed: bool = False,
    page: int = 1,
    page_size: int = 20,
    db=Depends(get_db),
):
    """敏感需求列表（跟踪态/团队/超期/关键字筛选 + 分页）。

    默认仅返回「在跟池」（active/delayed/escalated）；
    include_closed=true 或显式传 track_status 时放开历史态。
    """
    query = SensitiveReqQuery(
        track_status=track_status, team=team, keyword=keyword,
        only_overdue=only_overdue, include_closed=include_closed,
        page=page, page_size=page_size,
    )
    return success(data=sensitive_req_service.list_reqs(db, query))


@router.get("/stats")
def get_stats(db=Depends(get_db)):
    """在跟池统计：跟踪态 / 级别 / 团队 / 超期 / 临期 / 逾期未上线。"""
    return success(data=sensitive_req_service.get_stats(db))


@router.post("/sync")
def sync(db=Depends(get_db)):
    """同步敏感需求池（幂等）：扫描 ext → 敏感判定 → upsert → 逾期回写跟踪态。"""
    return success(data=sensitive_req_service.sync(db))


@router.patch("/track/{req_id}")
def update_track(req_id: str, payload: SensitiveReqTrackUpdateRequest, db=Depends(get_db)):
    """人工更新跟踪态 / 设置人工覆盖（lock 锁定 / dismiss 移出）。"""
    return success(data=sensitive_req_service.update_track(db, req_id, payload))


@router.get("/{req_id}/detail")
def get_detail(req_id: str, db=Depends(get_db)):
    """单个敏感需求详情：跟踪态 + 需求本体 + 全量里程碑（含团队泳道分组）。"""
    return success(data=sensitive_req_service.get_detail(db, req_id))


@router.get("/{req_id}/plan-suggestion")
def plan_suggestion(req_id: str, db=Depends(get_db)):
    """按模板缓冲生成 5 阶段倒排建议（不落库），供前端确认调整后保存。"""
    return success(data=sensitive_req_service.plan_suggestion(db, req_id))


@router.put("/{req_id}/milestones")
def save_milestones(req_id: str, payload: SensitiveReqMilestoneSaveRequest, db=Depends(get_db)):
    """全量覆盖保存倒排里程碑（PUT 语义，未提交的旧行删除）。"""
    return success(data=sensitive_req_service.save_milestones(db, req_id, payload))


@router.patch("/milestone/{milestone_id}")
def update_milestone(
    milestone_id: int, payload: SensitiveReqMilestoneUpdateRequest, db=Depends(get_db)
):
    """人工修正单个里程碑；触发跟踪态自动联动（全完成→闭环/有超期→delayed）。"""
    return success(data=sensitive_req_service.update_milestone(db, milestone_id, payload))


@router.post("/draft")
def draft(payload: SensitiveReqSendRequest, db=Depends(get_db)):
    """生成邮件 Markdown 草稿（主题 + 正文 + 结构化清单），供前端编辑区默认值。"""
    return success(data=sensitive_req_service.draft(
        db,
        [{"source": r.source, "source_id": r.source_id} for r in payload.tasks],
        payload.send_type, payload.body, payload.template_data.get("recipient_name")
        if payload.template_data else None,
    ))


@router.post("/send")
def send(payload: SensitiveReqSendRequest, db=Depends(get_db)):
    """发送敏感需求督办/同步邮件。

    dry_run=true 仅返回装配正文（预览）；真实发信需 confirm_send=true
    （AI 自测一律 dry_run，真发只由页面显式点击触发）。
    """
    return success(data=sensitive_req_service.send(db, payload))
