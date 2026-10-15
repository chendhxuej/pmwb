"""高级别工单路由（任务中心子模块，2026-10-15）。

职责：自动汇总各类工单中的高级别对象 + 汇聚跟踪 + 批量邮件督办。

只读：GET /high-level/tasks、GET /high-level/stats（列表/详情实时回读源，跟踪表只供跟踪态）
可写：POST /high-level/sync（幂等全量重算跟踪表）
      PATCH /high-level/track/{source}/{source_id}、POST /high-level/track/batch（人工跟踪态/锁定/提级/移出）
      POST /high-level/send（真实发信；须前端显式 confirm_send=true）

督办历史查询复用统一入口：GET /mail-dispatch/records?ref_type=high_level&ref_id=<source>:<source_id>
"""

from typing import Optional

from fastapi import APIRouter, Depends

from core.response import success
from db.base import get_db
from schemas.high_level import (
    HighLevelSendRequest,
    HighLevelTaskQuery,
    HighLevelTrackBatchRequest,
    HighLevelTrackUpdateRequest,
)
from schemas.task_center import TaskDraftRequest
from services.high_level import high_level_service

router = APIRouter(prefix="/high-level", tags=["高级别工单"])


@router.get("/tasks")
def list_tasks(
    source: Optional[str] = None,
    status: Optional[str] = None,
    track_status: Optional[str] = None,
    level: Optional[str] = None,
    owner: Optional[str] = None,
    keyword: Optional[str] = None,
    only_overdue: bool = False,
    include_closed: bool = False,
    page: int = 1,
    page_size: int = 20,
    db=Depends(get_db),
):
    """高级别工单列表（跟踪态/来源/级别/责任人/统一态/超期/关键字筛选 + 分页）。

    默认仅返回「在跟池」（track_status ∈ open/tracking/escalated）；
    include_closed=true 或显式传 track_status 时放开历史态。
    """
    query = HighLevelTaskQuery(
        source=source,
        status=status,
        track_status=track_status,
        level=level,
        owner=owner,
        keyword=keyword,
        only_overdue=only_overdue,
        include_closed=include_closed,
        page=page,
        page_size=page_size,
    )
    data = high_level_service.list_tasks(db, query)
    return success(data=data)


@router.get("/stats")
def get_stats(db=Depends(get_db)):
    """在跟池统计：来源 / 级别 / 跟踪态 / 超期 / 已升级 / 未分配责任人。"""
    return success(data=high_level_service.get_stats(db))


@router.post("/sync")
def sync(db=Depends(get_db)):
    """同步高级别工单池（幂等）。

    采集全部来源 → 规则判定 → upsert 跟踪表 → 源消失检测。
    采集失败的来源会回报在 failed_sources，且**不参与源消失判定**。
    """
    return success(data=high_level_service.sync(db))


@router.patch("/track/{source}/{source_id}")
def update_track(
    source: str,
    source_id: str,
    payload: HighLevelTrackUpdateRequest,
    db=Depends(get_db),
):
    """人工更新跟踪态 / 设置人工覆盖（lock 锁定 / escalate 提级 / dismiss 移出）。"""
    return success(data=high_level_service.update_track(db, source, source_id, payload))


@router.post("/track/batch")
def batch_update_track(payload: HighLevelTrackBatchRequest, db=Depends(get_db)):
    """批量更新跟踪态；逐项容错，失败项在 errors 回报。"""
    return success(data=high_level_service.batch_update_track(db, payload))


@router.post("/draft")
def draft(payload: TaskDraftRequest, db=Depends(get_db)):
    """生成邮件 Markdown 草稿（主题 + 正文），供前端编辑区默认值。"""
    return success(data=high_level_service.draft(
        db, payload.tasks, payload.send_type, payload.body, payload.recipient_name
    ))


@router.post("/send")
def send(payload: HighLevelSendRequest, db=Depends(get_db)):
    """发送高级别工单督办/同步邮件。

    dry_run=true 仅返回装配正文（预览）；真实发信需 confirm_send=true
    （AI 自测一律 dry_run，真发只由页面显式点击触发）。
    """
    return success(data=high_level_service.send(db, payload))
