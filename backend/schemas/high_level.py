"""高级别工单 Schema（任务中心「高级别工单」子模块，2026-10-15）。

数据二分：
  - HighLevelItem 的**工单本体字段**（title/owner/due_date/status...）实时取自各来源表
    （task_center 的 collector），不落库；
  - **跟踪态字段**（level_code/judge_reason/track_status/urge_count...）来自
    pmwb_high_level_track 表。

TaskRef 直接复用 schemas/task_center.TaskRef，保证与任务中心发信链路一致。
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from schemas.task_center import TaskRef  # noqa: F401  (对外再导出，路由层复用)


class HighLevelItem(BaseModel):
    """高级别工单条目 = 源工单实时快照 + 本地跟踪态。"""

    # ── 源工单本体（实时，不落库） ──────────────────────────────
    task_id: str = Field(..., description="复合键 source:source_id")
    source: str = Field(..., description="来源标识")
    source_id: str = Field(..., description="源表主键/复合键")
    source_label: str = Field("", description="来源中文名")
    title: str = Field("", description="工单标题")
    status: str = Field("pending", description="统一状态")
    status_label: str = Field("", description="统一状态中文名")
    raw_status: str = Field("", description="源表原始状态")
    owner: str = Field("", description="责任人（可能多人，逗号分隔）")
    owner_display: str = Field("", description="责任人展示串（顿号连接）")
    priority: Optional[str] = Field(None, description="源表级别原值")
    priority_label: str = Field("", description="级别中文标签")
    due_date: Optional[date] = Field(None, description="截止/计划完成日期")
    created_at: Optional[date] = Field(None, description="创建时间")
    is_overdue: bool = Field(False, description="是否超期")
    is_due_soon: bool = Field(False, description="是否临期(3天内)")
    source_url: str = Field("", description="前端跳转源模块路由")
    detail: Dict[str, Any] = Field(default_factory=dict, description="源模块关键字段摘要")
    source_gone: bool = Field(False, description="源工单已删除/采集不到")

    # ── 本地跟踪态（来自 pmwb_high_level_track） ────────────────
    level_code: Optional[str] = Field(None, description="命中级别码 P0/P1/P2")
    judge_reason: str = Field("", description="判定来源 R1:P0 / R2:overdue:.. / R3:inherit:.. / R4:lock")
    is_high: bool = Field(True, description="当前是否高级别")
    track_status: str = Field("open", description="跟踪态（见 status_registry: high_level_track）")
    track_label: str = Field("", description="跟踪态中文名")
    track_tone: str = Field("info", description="跟踪态色调")
    manual_override: Optional[str] = Field(None, description="lock/escalate/dismiss/NULL")
    urge_count: int = Field(0, description="累计督办次数")
    last_urged_at: Optional[datetime] = Field(None, description="最近督办时间")
    first_seen_at: Optional[datetime] = Field(None, description="首次纳入时间")
    last_seen_at: Optional[datetime] = Field(None, description="最近命中时间")
    first_overdue_at: Optional[date] = Field(None, description="首次超期日期")


class HighLevelTaskQuery(BaseModel):
    """高级别工单列表查询条件。"""

    source: Optional[str] = Field(None, description="来源过滤")
    status: Optional[str] = Field(None, description="统一态过滤 pending/in_progress/done/blocked")
    track_status: Optional[str] = Field(None, description="跟踪态过滤")
    level: Optional[str] = Field(None, description="级别码过滤 P0/P1/P2")
    owner: Optional[str] = Field(None, description="责任人过滤（多人用逗号分隔）")
    keyword: Optional[str] = Field(None, description="标题/责任人/详情模糊搜索")
    only_overdue: bool = Field(False, description="只看超期")
    include_closed: bool = Field(False, description="是否包含已闭环/已移除（默认只看在跟池）")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=500)


class HighLevelTrackUpdateRequest(BaseModel):
    """人工更新跟踪态 / 人工覆盖。"""

    track_status: Optional[str] = Field(None, description="目标跟踪态（原生态值，见注册表）")
    manual_override: Optional[str] = Field(
        None, description="lock 锁定 / escalate 提级 / dismiss 移出；传空串清除"
    )
    operator: Optional[str] = Field("pmwb", description="操作人（留痕）")


class HighLevelTrackBatchItem(BaseModel):
    """批量更新跟踪态单项。"""

    source: str
    source_id: str
    track_status: Optional[str] = None
    manual_override: Optional[str] = None
    operator: Optional[str] = None


class HighLevelTrackBatchRequest(BaseModel):
    """批量更新跟踪态请求。"""

    items: List[HighLevelTrackBatchItem] = Field(default_factory=list)


class HighLevelSendRequest(BaseModel):
    """高级别工单督办/同步邮件请求。

    dry_run=True 时仅返回后端装配的正文（预览，所见即所得），不校验收件人、不发送、不落库。
    confirm_send=True 才会真实发信（前端「发送」按钮固定带 true）。
    """

    tasks: List[TaskRef] = Field(default_factory=list, description="关联工单列表")
    to: Optional[str] = Field(None, description="收件人，支持姓名/邮箱混合，多个逗号分隔")
    cc: Optional[str] = Field(None, description="抄送")
    subject: Optional[str] = Field(None, description="邮件主题（dry_run 可省略）")
    body: Optional[str] = Field(None, description="邮件正文；留空由后端装配")
    send_type: str = Field("urge", description="urge=督办 / notify=同步")
    operator: Optional[str] = Field("pmwb", description="操作人")
    dry_run: bool = Field(False, description="仅预览正文，不发送不落库")
    confirm_send: bool = Field(False, description="显式确认真发")
    template_data: Optional[Dict[str, Any]] = Field(
        None, description="模板变量（tasks/sendType/recipient_name）"
    )
    ref_type: Optional[str] = Field("high_level", description="邮件记录关联模块类型")
    ref_id: Optional[str] = Field(None, description="关联业务主键")


class HighLevelSyncResult(BaseModel):
    """同步结果。"""

    scanned: int = Field(0, description="本轮采集到的工单总数")
    high: int = Field(0, description="判定为高级别的工单数")
    added: int = Field(0, description="新纳入跟踪数")
    updated: int = Field(0, description="刷新跟踪态数")
    removed: int = Field(0, description="源消失转已移除数")
    resolved: int = Field(0, description="源终态自动闭环数")
    restored: int = Field(0, description="复活数")
    dropped: int = Field(0, description="降级移出池数")
    failed_sources: List[str] = Field(default_factory=list, description="采集失败的来源（本轮未参与判定）")
