"""排版管理 Schema（请求体）。

响应统一由 services/paiban_version.py 组装为 dict（含派生截止与口径标注），
避免 ORM 读模型与 pydantic 版本耦合；前端 request.js 已解 {code,message,data} 包络。
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class VersionPlanCreate(BaseModel):
    version_no: str = Field(..., min_length=1, max_length=64, description="版本标识")
    scope_type: str = Field("system", description="default=统一默认 / system=指定系统")
    system_name: Optional[str] = Field(None, description="指定系统名（scope=system 必填）")
    version_type: str = Field("regular", description="regular/emergency/ad_hoc")
    release_date: date = Field(..., description="计划发布日（全部倒排与准入判定的唯一基准）")
    status: str = Field("draft", description="draft/confirmed/published/closed/cancelled")
    admit_mode: str = Field("open", description="open / wait_release_n_days")
    admit_lead_days: int = Field(0, ge=0, le=365, description="提前准入天数（CRM=7）")
    allow_temp_merge: int = Field(1, ge=0, le=1, description="是否允许临时合入；0=未准入默认自动顺延")
    next_version_id: Optional[int] = Field(None, description="人工指定的顺延目标版本；空=按版本序列解析")
    remark: Optional[str] = Field(None, description="窗口说明")
    operator: Optional[str] = Field(None, description="操作人（留痕）")


class DeadlinePreviewRequest(BaseModel):
    release_date: date = Field(..., description="待预览的计划发布日")
    admit_mode: str = Field("open", description="open / wait_release_n_days")
    admit_lead_days: int = Field(0, ge=0, le=365)


class VersionPlanUpdate(BaseModel):
    version_no: Optional[str] = Field(None, max_length=64)
    release_date: Optional[date] = None
    status: Optional[str] = None
    version_type: Optional[str] = None
    admit_mode: Optional[str] = None
    admit_lead_days: Optional[int] = Field(None, ge=0, le=365)
    allow_temp_merge: Optional[int] = Field(None, ge=0, le=1)
    next_version_id: Optional[int] = None
    remark: Optional[str] = None
    operator: Optional[str] = None


# ── pb-2 ~ pb-9 请求体 ──────────────────────────────────────────
class CandidateIncludeRequest(BaseModel):
    items: list = Field(default_factory=list, description="[{ticket_type,ticket_no}]")
    operator: Optional[str] = None
    source: str = Field("pool", description="pool / inline / sync")


class InlineIncludeRequest(BaseModel):
    ticket_type: str
    ticket_no: str
    operator: Optional[str] = None


class SyncRequest(BaseModel):
    operator: Optional[str] = None
    mark_missing: bool = Field(True, description="源消失是否置墓碑")


class RemoveRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="移出原因必填")
    operator: Optional[str] = None


class TeamStageRequest(BaseModel):
    stage: str
    reason: Optional[str] = None
    operator: Optional[str] = None
    source: str = "page"
    done: Optional[bool] = None
    feedback_id: Optional[int] = None


class ResultRequest(BaseModel):
    result: str
    reason: Optional[str] = None
    result_date: Optional[date] = None
    operator: Optional[str] = None


class ManualHandleRequest(BaseModel):
    action: str = Field(..., description="defer / allow / revoke")
    reason: Optional[str] = Field(None, description="例外原因闭集")
    reason_note: Optional[str] = Field(None, description="选其他时必填说明")
    operator: Optional[str] = None


class RiskCreateRequest(BaseModel):
    risk_type: str
    description: str
    affect_release: int = Field(0, ge=0, le=1)
    level: str = "P2"
    source: str = "page"
    raw_ref: Optional[str] = None
    operator: Optional[str] = None


class RiskResolveRequest(BaseModel):
    resolution: str = Field(..., min_length=1)
    operator: Optional[str] = None


class SupervisePreviewRequest(BaseModel):
    plan_id: int
    team_name: Optional[str] = None
    ticket_type: Optional[str] = None
    ignore_cooldown: bool = False
    exception_reason: Optional[str] = None


class SuperviseSendRequest(SupervisePreviewRequest):
    groups: Optional[list] = Field(None, description="选中分组 [(team_name,ticket_type)]")
    dry_run: bool = Field(True, description="自测一律 true")
    confirm_send: bool = Field(False, description="真发须页面显式 true")
    operator: Optional[str] = None


class FeedbackSubmitRequest(BaseModel):
    channel: str = Field("inline", description="batch / inline / proxy")
    track_id: int
    team_id: Optional[int] = None
    stage: Optional[str] = None
    progress: Optional[str] = None
    risk: Optional[str] = None
    promise_date: Optional[str] = None
    risk_type: Optional[str] = None
    affect_release: int = 0
    reason: Optional[str] = None
    raw_text: Optional[str] = None
    batch_no: Optional[str] = None
    receipt_code: Optional[str] = None
    reporter: Optional[str] = None
    operator: Optional[str] = None


class FeedbackBatchRequest(BaseModel):
    items: list = Field(default_factory=list)
    batch_no: Optional[str] = None
    operator: Optional[str] = None


class FeedbackMailPullRequest(BaseModel):
    since: Optional[str] = None
    until: Optional[str] = None


class FeedbackReviewRequest(BaseModel):
    action: str = Field(..., description="adopt / reject")
    reviewer: str
    review_note: Optional[str] = None


class FeedbackRollbackRequest(BaseModel):
    operator: str
