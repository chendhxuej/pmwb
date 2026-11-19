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

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends

from core.response import success
from db.base import get_db
from schemas.paiban import (
    CandidateIncludeRequest, DeadlinePreviewRequest, FeedbackBatchRequest,
    FeedbackMailPullRequest, FeedbackReviewRequest, FeedbackRollbackRequest,
    FeedbackSubmitRequest, InlineIncludeRequest, ManualHandleRequest,
    RemoveRequest, ResultRequest, RiskCreateRequest, RiskResolveRequest,
    SupervisePreviewRequest, SuperviseSendRequest, SyncRequest, TeamStageBatchRequest,
    TeamStageRequest, VersionPlanCreate, VersionPlanUpdate,
)
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
    future_only: bool = False,
    db=Depends(get_db),
):
    """版本计划列表；派生四环节截止与准入判定时点随读随算，不落副本。
    future_only=true 只列发布日≥今天的有效计划（版本计划页默认口径）。"""
    return success(data=svc.list_plans(
        db, scope_type=scope_type, system_name=system_name,
        status=status, include_cancelled=include_cancelled,
        future_only=future_only,
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


# ── pb-2 候选池 / 纳入 ───────────────────────────────────────────
from services import paiban_candidate as CS


@router.get("/candidates")
def candidates(keyword: str = "", limit: int = 200, ticket_type: str = "",
               db=Depends(get_db)):
    return success(data=CS.scan(db, keyword=keyword, limit=limit, ticket_type=ticket_type))


@router.post("/candidates/include")
def include_candidates(payload: "CandidateIncludeRequest", db=Depends(get_db)):
    return success(data=CS.include_batch(db, payload.items,
                                         operator=payload.operator or "",
                                         source=payload.source), message="已纳入")


@router.post("/tracks/inline-include")
def inline_include(payload: "InlineIncludeRequest", db=Depends(get_db)):
    return success(data=CS.include_once(db, payload.ticket_type, payload.ticket_no,
                                        operator=payload.operator or "", source="inline"),
                   message="已纳入")


@router.post("/tracks/sync")
def sync_tracks(payload: "SyncRequest", db=Depends(get_db)):
    return success(data=CS.sync(db, operator=payload.operator or "",
                                mark_missing=payload.mark_missing), message="同步完成")


# ── pb-3/4 跟踪主行与团队 ───────────────────────────────────────
from services import paiban_track as TS
from services import paiban_team as TEAM


@router.get("/tracks")
def list_tracks(plan_id: Optional[int] = None, ticket_type: str = "", stage: str = "",
                admit_status: str = "", result: str = "", keyword: str = "",
                include_inactive: bool = False, db=Depends(get_db)):
    return success(data=TS.list_tracks(
        db, plan_id=plan_id, ticket_type=ticket_type, stage=stage,
        admit_status=admit_status, result=result, keyword=keyword,
        include_inactive=include_inactive))


@router.get("/tracks/missing-plans")
def missing_plans(db=Depends(get_db)):
    from services import paiban_overview as OV
    return success(data=OV.missing_plans(db))


@router.get("/team-matrix")
def team_matrix(plan_id: Optional[int] = None, team_name: str = "", stage: str = "",
                overdue: str = "", db=Depends(get_db)):
    return success(data=TEAM.matrix(db, plan_id, team_name, stage, overdue))


@router.post("/tracks/{track_id}/remove")
def remove_track(track_id: int, payload: "RemoveRequest", db=Depends(get_db)):
    return success(data=CS.remove(db, track_id, reason=payload.reason,
                                  operator=payload.operator or ""), message="已移出")


@router.post("/tracks/{track_id}/result")
def set_result(track_id: int, payload: "ResultRequest", db=Depends(get_db)):
    return success(data=TS.set_result(db, track_id, payload.model_dump()), message="结果已登记")


@router.post("/tracks/{track_id}/manual")
def manual_handle(track_id: int, payload: "ManualHandleRequest", db=Depends(get_db)):
    return success(data=TS.manual_handle(db, track_id, payload.model_dump()), message="已处理")


@router.get("/tracks/{track_id}/timeline")
def timeline(track_id: int, db=Depends(get_db)):
    return success(data=TS.timeline(db, track_id))


@router.post("/teams/stage/batch")
def set_team_stage_batch(payload: "TeamStageBatchRequest", db=Depends(get_db)):
    return success(data=TEAM.batch_set_stage(
        db, payload.items, operator=payload.operator or "", source=payload.source),
        message="批量环节更新完成")


@router.post("/teams/{team_id}/stage")
def set_team_stage(team_id: int, payload: "TeamStageRequest", db=Depends(get_db)):
    return success(data=TEAM.set_team_stage(
        db, team_id, payload.stage, reason=payload.reason or "",
        operator=payload.operator or "", source=payload.source,
        done=payload.done, feedback_id=payload.feedback_id), message="环节已更新")


@router.post("/admission/simulate")
def simulate_admission(release_date: date, lead_days: int,
                       wait_release_date: Optional[date] = None, db=Depends(get_db)):
    return success(data=TS.simulate_admission(release_date, lead_days, wait_release_date))


# ── pb-5 风险 ────────────────────────────────────────────────────
from services import paiban_risk as RS


@router.get("/risks")
def list_risks(plan_id: Optional[int] = None, only_blocking: bool = False,
               track_id: Optional[int] = None, db=Depends(get_db)):
    return success(data=RS.list_risks(db, plan_id, only_blocking=only_blocking,
                                      track_id=track_id))


@router.post("/tracks/{track_id}/risks")
def create_risk(track_id: int, payload: "RiskCreateRequest", db=Depends(get_db)):
    return success(data=RS.create(db, track_id, payload.model_dump()), message="风险已登记")


@router.post("/risks/{risk_id}/resolve")
def resolve_risk(risk_id: int, payload: "RiskResolveRequest", db=Depends(get_db)):
    return success(data=RS.resolve(db, risk_id, resolution=payload.resolution,
                                   operator=payload.operator or ""), message="风险已消除")


# ── pb-6 督办 ────────────────────────────────────────────────────
from services import paiban_supervise as SUP


@router.post("/supervise/preview")
def supervise_preview(payload: "SupervisePreviewRequest", db=Depends(get_db)):
    return success(data=SUP.build_preview(
        db, plan_id=payload.plan_id, team_name=payload.team_name or "",
        ticket_type=payload.ticket_type or "",
        ignore_cooldown=payload.ignore_cooldown,
        exception_reason=payload.exception_reason or ""))


@router.post("/supervise/send")
def supervise_send(payload: "SuperviseSendRequest", db=Depends(get_db)):
    return success(data=SUP.send(db, payload.model_dump()), message="督办已执行")


@router.get("/supervise/batches")
def supervise_batches(plan_id: Optional[int] = None, db=Depends(get_db)):
    return success(data=SUP.batches(db, plan_id))


@router.get("/supervise/batches/{batch_no}")
def supervise_batch_detail(batch_no: str, db=Depends(get_db)):
    return success(data=SUP.batch_detail(db, batch_no))


# ── pb-7 反馈同步 ────────────────────────────────────────────────
from services import paiban_feedback as FB


@router.post("/feedback/submit")
def feedback_submit(payload: "FeedbackSubmitRequest", db=Depends(get_db)):
    ch = payload.channel if payload.channel in ("batch", "proxy") else "inline"
    return success(data=FB.submit(db, payload.model_dump(), channel=ch), message="反馈已记录")


@router.post("/feedback/batch")
def feedback_batch(payload: "FeedbackBatchRequest", db=Depends(get_db)):
    return success(data=FB.batch_submit(db, payload.model_dump()), message="批量反馈已记录")


@router.post("/feedback/mail/pull")
def feedback_mail_pull(payload: "FeedbackMailPullRequest", db=Depends(get_db)):
    return success(data=FB.pull_mail(db, since=payload.since or "", until=payload.until or ""))


@router.get("/feedback/pending")
def feedback_pending(status: str = "", db=Depends(get_db)):
    return success(data=FB.pending_list(db, status=status))


@router.post("/feedback/{feedback_id}/review")
def feedback_review(feedback_id: int, payload: "FeedbackReviewRequest", db=Depends(get_db)):
    return success(data=FB.review(db, feedback_id, payload.model_dump()), message="核对完成")


@router.post("/feedback/{feedback_id}/rollback")
def feedback_rollback(feedback_id: int, payload: "FeedbackRollbackRequest", db=Depends(get_db)):
    return success(data=FB.rollback(db, feedback_id, operator=payload.operator), message="已回滚")


# ── pb-8 概览 ────────────────────────────────────────────────────
from services import paiban_overview as OV


@router.get("/overview")
def overview(plan_id: int, db=Depends(get_db)):
    return success(data=OV.overview(db, plan_id))
