"""敏感需求跟踪 Schema（需求与交付「敏感需求跟踪」子模块，2026-10-25）。

数据二分（与 schemas/high_level.py 同构）：
  - SensitiveReqItem 的**需求本体字段**（req_name/priority/version_required_date...）
    实时取自 sent_emails + pmwb_requirement_ext，不落库；
  - **跟踪态字段**（track_status/judge_reason/urge_count...）来自
    pmwb_sensitive_req_track 表；里程碑来自 pmwb_sensitive_req_milestone。
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from schemas.task_center import TaskRef  # noqa: F401  (对外再导出，路由层复用)


class SensitiveReqMilestoneView(BaseModel):
    """里程碑条目（读模型，红黄态实时计算不落库）。"""

    id: int
    req_id: str
    team_system_name: str = Field(..., description="团队标识=团队评估系统名")
    stage: str = Field(..., description="evaluate/plan/dev/test/deploy")
    stage_label: str = ""
    stage_order: int = 99
    owner: str = ""
    owner_list: List[str] = Field(default_factory=list)
    planned_start: Optional[date] = None
    planned_end: Optional[date] = None
    actual_end: Optional[date] = None
    actual_hint: Optional[date] = Field(
        None, description="可回填的事实完成日（stage_log left_at / ext.delivered_date，只读引用）"
    )
    status: str = "pending"
    status_label: str = ""
    tone: str = "info"
    risk_note: str = ""
    source: str = "manual"
    is_overdue: bool = False
    overdue_days: int = 0
    is_due_soon: bool = False
    urge_count: int = 0
    last_urged_at: Optional[datetime] = None


class SensitiveReqFocusMilestone(BaseModel):
    """最近关键里程碑（超期 > 临期 > 未来最早未完成）。"""

    id: int
    team_system_name: str = ""
    stage: str = ""
    stage_label: str = ""
    owner: str = ""
    planned_end: Optional[date] = None
    is_overdue: bool = False


class SensitiveReqItem(BaseModel):
    """敏感需求条目 = 需求本体实时快照 + 本地跟踪态 + 里程碑汇总。"""

    # ── 需求本体（实时回读，不落库） ────────────────────────────
    req_id: str
    req_name: str = ""
    priority: Optional[str] = None
    priority_label: str = ""
    req_status: str = Field("", description="源需求跟踪状态（requirement 域原值）")
    req_status_label: str = ""
    version_required_date: Optional[date] = Field(
        None, description="上线要求时间（倒排终点权威源，老大 2026-10-25 拍板）"
    )
    delivered_date: Optional[date] = None
    days_to_deadline: Optional[int] = Field(None, description="距上线要求天数（负=已过期）")
    deadline_missed: bool = Field(False, description="上线要求日已过且需求未上线")
    source_url: str = ""
    source_gone: bool = False

    # ── 里程碑汇总 ─────────────────────────────────────────────
    teams: List[str] = Field(default_factory=list, description="涉及团队（里程碑内去重）")
    milestone_total: int = 0
    milestone_done: int = 0
    overdue_count: int = 0
    due_soon_count: int = 0
    focus_milestone: Optional[SensitiveReqFocusMilestone] = None
    milestones: List[SensitiveReqMilestoneView] = Field(default_factory=list)

    # ── 本地跟踪态（pmwb_sensitive_req_track） ──────────────────
    is_sensitive: bool = True
    judge_reason: str = Field("", description="R1:P0 / R1:集团需求 / R4:lock")
    level_code: Optional[str] = None
    track_status: str = "active"
    track_label: str = ""
    track_tone: str = "info"
    manual_override: Optional[str] = None
    urge_count: int = 0
    last_urged_at: Optional[datetime] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    first_overdue_at: Optional[date] = None


class SensitiveReqQuery(BaseModel):
    """敏感需求列表查询条件。"""

    track_status: Optional[str] = Field(None, description="跟踪态过滤")
    team: Optional[str] = Field(None, description="团队过滤（里程碑涉及即命中）")
    keyword: Optional[str] = Field(None, description="需求名/编号模糊搜索")
    only_overdue: bool = Field(False, description="只看有里程碑超期的需求")
    include_closed: bool = Field(False, description="包含已闭环/已移除（默认只看在跟池）")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=500)


class SensitiveReqTrackUpdateRequest(BaseModel):
    """人工更新跟踪态 / 人工覆盖。"""

    track_status: Optional[str] = None
    manual_override: Optional[str] = Field(
        None, description="lock 锁定 / dismiss 移出；传空串清除"
    )
    operator: Optional[str] = "pmwb"


class SensitiveReqMilestoneItem(BaseModel):
    """里程碑保存单项（PUT 全量覆盖口径）。"""

    team_system_name: str
    stage: str
    owner: Optional[str] = None
    planned_start: Optional[date] = None
    planned_end: Optional[date] = None
    status: Optional[str] = None
    risk_note: Optional[str] = None
    source: Optional[str] = "manual"


class SensitiveReqMilestoneSaveRequest(BaseModel):
    """里程碑全量保存请求（未提交的既有行将被删除）。"""

    items: List[SensitiveReqMilestoneItem] = Field(default_factory=list)


class SensitiveReqMilestoneUpdateRequest(BaseModel):
    """单个里程碑人工修正（PATCH 语义，只改提交的字段）。"""

    owner: Optional[str] = None
    planned_start: Optional[date] = None
    planned_end: Optional[date] = None
    actual_end: Optional[date] = None
    status: Optional[str] = None
    risk_note: Optional[str] = None


class SensitiveReqRef(BaseModel):
    """督办引用（req 粒度）。"""

    source: str = "sensitive_req"
    source_id: str


class SensitiveReqSendRequest(BaseModel):
    """敏感需求督办/同步邮件请求。

    dry_run=True 时仅返回装配正文（预览）；confirm_send=True 才真实发信
    （前端「发送」按钮固定带 true；AI 自测一律 dry_run）。
    """

    tasks: List[SensitiveReqRef] = Field(default_factory=list)
    to: Optional[str] = None
    cc: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    send_type: str = Field("urge", description="urge=督办 / notify=同步")
    operator: Optional[str] = "pmwb"
    dry_run: bool = False
    confirm_send: bool = False
    template_data: Optional[Dict[str, Any]] = None
    ref_type: Optional[str] = "sensitive_req"
    ref_id: Optional[str] = None
