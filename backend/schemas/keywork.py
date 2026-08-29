import json
from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------
class KeyWorkCategory(str, Enum):
    hq_pilot = "hq_pilot"
    annual_task = "annual_task"
    special_topic = "special_topic"


class KeyWorkStatus(str, Enum):
    planning = "planning"
    in_progress = "in_progress"
    completed = "completed"
    paused = "paused"
    cancelled = "cancelled"


class KeyWorkPriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class MilestoneStatus(str, Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"
    delayed = "delayed"


class PlanStatus(str, Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"
    delayed = "delayed"


class MemberTaskStatus(str, Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"
    delayed = "delayed"


class MemberTaskLink(str, Enum):
    none = "none"
    milestone = "milestone"
    monthly_plan = "monthly_plan"
    weekly_plan = "weekly_plan"


class DeliverableType(str, Enum):
    doc = "doc"
    report = "report"
    data = "data"
    code = "code"
    other = "other"


# ---------------------------------------------------------------------------
# 子表 schema
# ---------------------------------------------------------------------------
class KeyWorkGoalBase(BaseModel):
    seq: int = Field(1, description="指标序号")
    indicator: Optional[str] = Field(None, max_length=255, description="指标名称")
    target_value: Optional[str] = Field(None, max_length=255, description="目标值")
    current_value: Optional[str] = Field(None, max_length=255, description="当前值")
    unit: Optional[str] = Field(None, max_length=32, description="单位")
    description: Optional[str] = Field(None, description="说明")


class KeyWorkGoalCreate(KeyWorkGoalBase):
    pass


class KeyWorkGoalOut(KeyWorkGoalBase):
    id: int
    key_work_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KeyWorkMilestoneBase(BaseModel):
    seq: int = Field(1, description="序号")
    name: str = Field(..., max_length=255, description="里程碑名称")
    due_date: Optional[date] = Field(None, description="计划完成日期")
    status: MilestoneStatus = Field(MilestoneStatus.not_started, description="状态")
    note: Optional[str] = Field(None, description="说明")

    @field_validator("due_date", mode="before")
    @classmethod
    def _empty_due_date_to_none(cls, v):
        return None if v in ("", None) else v


class KeyWorkMilestoneCreate(KeyWorkMilestoneBase):
    pass


class KeyWorkMilestoneOut(KeyWorkMilestoneBase):
    id: int
    key_work_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KeyWorkMilestoneUpdate(BaseModel):
    """里程碑部分更新（所有字段可选）。"""

    seq: Optional[int] = None
    name: Optional[str] = Field(None, max_length=255, description="里程碑名称")
    due_date: Optional[date] = Field(None, description="计划完成日期")
    status: Optional[MilestoneStatus] = None
    note: Optional[str] = None

    @field_validator("due_date", mode="before")
    @classmethod
    def _empty_due_date_to_none_update(cls, v):
        return None if v in ("", None) else v


class KeyWorkMemberBase(BaseModel):
    name: str = Field(..., max_length=64, description="成员姓名")
    role: Optional[str] = Field(None, max_length=128, description="角色")
    division_desc: Optional[str] = Field(None, description="分工说明")


class KeyWorkMemberCreate(KeyWorkMemberBase):
    pass


class KeyWorkMemberOut(KeyWorkMemberBase):
    id: int
    key_work_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KeyWorkMonthlyPlanBase(BaseModel):
    month: str = Field(..., max_length=7, description="月份 YYYY-MM")
    task_date: Optional[date] = Field(None, description="创建日期")
    title: Optional[str] = Field(None, max_length=500, description="任务标题")
    content: Optional[str] = Field(None, description="任务描述")
    assignee: Optional[str] = Field(None, max_length=64, description="责任人")
    due_date: Optional[date] = Field(None, description="计划完成日期")
    status: PlanStatus = Field(PlanStatus.not_started, description="状态")

    @field_validator("task_date", "due_date", mode="before")
    @classmethod
    def _empty_date_to_none(cls, v):
        return None if v in ("", None) else v


class KeyWorkMonthlyPlanCreate(KeyWorkMonthlyPlanBase):
    pass


class KeyWorkMonthlyPlanOut(KeyWorkMonthlyPlanBase):
    id: int
    key_work_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KeyWorkWeeklyPlanBase(BaseModel):
    week: str = Field(..., max_length=10, description="周次 YYYY-Www")
    task_date: Optional[date] = Field(None, description="创建日期")
    title: Optional[str] = Field(None, max_length=500, description="任务标题")
    content: Optional[str] = Field(None, description="任务描述")
    assignee: Optional[str] = Field(None, max_length=64, description="责任人")
    due_date: Optional[date] = Field(None, description="计划完成日期")
    status: PlanStatus = Field(PlanStatus.not_started, description="状态")

    @field_validator("task_date", "due_date", mode="before")
    @classmethod
    def _empty_weekly_date_to_none(cls, v):
        return None if v in ("", None) else v


class KeyWorkWeeklyPlanCreate(KeyWorkWeeklyPlanBase):
    pass


class KeyWorkWeeklyPlanOut(KeyWorkWeeklyPlanBase):
    id: int
    key_work_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KeyWorkMonthlyPlanUpdate(BaseModel):
    """月度计划部分更新（所有字段可选）。"""

    month: Optional[str] = Field(None, max_length=7, description="月份 YYYY-MM")
    task_date: Optional[date] = Field(None, description="创建日期")
    title: Optional[str] = Field(None, max_length=500, description="任务标题")
    content: Optional[str] = Field(None, description="任务描述")
    assignee: Optional[str] = Field(None, max_length=64, description="责任人")
    due_date: Optional[date] = Field(None, description="计划完成日期")
    status: Optional[PlanStatus] = None

    @field_validator("task_date", "due_date", mode="before")
    @classmethod
    def _empty_date_to_none_update(cls, v):
        return None if v in ("", None) else v


class KeyWorkWeeklyPlanUpdate(BaseModel):
    """周计划部分更新（所有字段可选）。"""

    week: Optional[str] = Field(None, max_length=10, description="周次 YYYY-Www")
    task_date: Optional[date] = Field(None, description="创建日期")
    title: Optional[str] = Field(None, max_length=500, description="任务标题")
    content: Optional[str] = Field(None, description="任务描述")
    assignee: Optional[str] = Field(None, max_length=64, description="责任人")
    due_date: Optional[date] = Field(None, description="计划完成日期")
    status: Optional[PlanStatus] = None

    @field_validator("task_date", "due_date", mode="before")
    @classmethod
    def _empty_weekly_date_to_none_update(cls, v):
        return None if v in ("", None) else v


class KeyWorkProgressBase(BaseModel):
    record_date: Optional[date] = Field(None, description="进展日期")
    reporter: Optional[str] = Field(None, max_length=64, description="汇报人")
    content: Optional[str] = Field(None, description="进展内容")

    @field_validator("record_date", mode="before")
    @classmethod
    def _empty_record_date_to_none(cls, v):
        return None if v in ("", None) else v


class KeyWorkProgressCreate(KeyWorkProgressBase):
    pass


class KeyWorkProgressOut(KeyWorkProgressBase):
    id: int
    key_work_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KeyWorkMemberTaskBase(BaseModel):
    title: str = Field(..., max_length=500, description="待办标题")
    assignee: Optional[str] = Field(None, max_length=64, description="负责人(成员姓名)")
    due_date: Optional[date] = Field(None, description="截止日期")
    status: MemberTaskStatus = Field(MemberTaskStatus.not_started, description="状态")
    link_type: MemberTaskLink = Field(MemberTaskLink.none, description="关联对象类型")
    link_id: Optional[int] = Field(None, description="关联对象ID")
    note: Optional[str] = Field(None, description="备注")

    @field_validator("due_date", mode="before")
    @classmethod
    def _empty_due_date_to_none(cls, v):
        return None if v in ("", None) else v


class KeyWorkMemberTaskCreate(KeyWorkMemberTaskBase):
    pass


class KeyWorkMemberTaskOut(KeyWorkMemberTaskBase):
    id: int
    key_work_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KeyWorkMemberTaskUpdate(BaseModel):
    """成员待办部分更新（所有字段可选）。"""

    title: Optional[str] = Field(None, max_length=500, description="待办标题")
    assignee: Optional[str] = Field(None, max_length=64, description="负责人(成员姓名)")
    due_date: Optional[date] = Field(None, description="截止日期")
    status: Optional[MemberTaskStatus] = None
    link_type: Optional[MemberTaskLink] = None
    link_id: Optional[int] = None
    note: Optional[str] = None

    @field_validator("due_date", mode="before")
    @classmethod
    def _empty_due_date_to_none_update(cls, v):
        return None if v in ("", None) else v


class KeyWorkDeliverableOut(BaseModel):
    id: int
    key_work_id: int
    deliverable_type: Optional[str] = None
    file_name: str
    original_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    obsidian_path: Optional[str] = None
    source: Optional[str] = None
    note: Optional[str] = None
    uploaded_by: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DeliverableListResponse(BaseModel):
    total: int
    items: List[KeyWorkDeliverableOut]


# ---------------------------------------------------------------------------
# 主表 schema
# ---------------------------------------------------------------------------
class KeyWorkCreate(BaseModel):
    title: str = Field(..., max_length=500, description="工作标题")
    category: KeyWorkCategory = Field(KeyWorkCategory.annual_task, description="分类")
    domain_code: Optional[str] = Field(None, max_length=64, description="关联业务领域编码")
    owner: Optional[str] = Field(None, max_length=128, description="牵头人/负责人")
    priority: KeyWorkPriority = Field(KeyWorkPriority.P2, description="优先级")
    status: KeyWorkStatus = Field(KeyWorkStatus.planning, description="生命周期状态")
    progress: int = Field(0, ge=0, le=100, description="进度百分比 0-100")
    planned_finish_date: Optional[date] = Field(None, description="计划完成时间")
    background: Optional[str] = Field(None, description="工作背景")
    current_status: Optional[str] = Field(None, description="现状说明")
    content: Optional[str] = Field(None, description="工作内容")
    work_value: Optional[str] = Field(None, description="工作价值/收益")
    acceptance_criteria: Optional[List[str]] = Field(None, description="验收标准(字符串数组)")
    goals: List[KeyWorkGoalCreate] = Field([], description="工作目标指标")
    milestones: List[KeyWorkMilestoneCreate] = Field([], description="里程碑")
    members: List[KeyWorkMemberCreate] = Field([], description="团队成员及分工")
    monthly_plans: List[KeyWorkMonthlyPlanCreate] = Field([], description="月度计划")
    weekly_plans: List[KeyWorkWeeklyPlanCreate] = Field([], description="周计划")
    progresses: List[KeyWorkProgressCreate] = Field([], description="进展日志")
    member_tasks: List[KeyWorkMemberTaskCreate] = Field([], description="成员待办")

    @field_validator("planned_finish_date", mode="before")
    @classmethod
    def _empty_finish_date_to_none(cls, v):
        return None if v in ("", None) else v


class KeyWorkUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    category: Optional[KeyWorkCategory] = None
    domain_code: Optional[str] = Field(None, max_length=64)
    owner: Optional[str] = Field(None, max_length=128)
    priority: Optional[KeyWorkPriority] = None
    status: Optional[KeyWorkStatus] = None
    planned_finish_date: Optional[date] = None
    progress: Optional[int] = Field(None, ge=0, le=100, description="进度百分比 0-100")
    background: Optional[str] = None
    current_status: Optional[str] = None
    content: Optional[str] = None
    work_value: Optional[str] = Field(None, description="工作价值/收益")
    acceptance_criteria: Optional[List[str]] = Field(None, description="验收标准(字符串数组)")
    goals: Optional[List[KeyWorkGoalCreate]] = None
    milestones: Optional[List[KeyWorkMilestoneCreate]] = None
    members: Optional[List[KeyWorkMemberCreate]] = None
    monthly_plans: Optional[List[KeyWorkMonthlyPlanCreate]] = None
    weekly_plans: Optional[List[KeyWorkWeeklyPlanCreate]] = None
    progresses: Optional[List[KeyWorkProgressCreate]] = None
    member_tasks: Optional[List[KeyWorkMemberTaskCreate]] = None

    @field_validator("planned_finish_date", mode="before")
    @classmethod
    def _empty_finish_date_to_none_update(cls, v):
        return None if v in ("", None) else v


class KeyWorkOut(BaseModel):
    id: int
    work_no: str
    category: KeyWorkCategory
    title: str
    background: Optional[str] = None
    current_status: Optional[str] = None
    content: Optional[str] = None
    work_value: Optional[str] = None
    owner: Optional[str] = None
    priority: KeyWorkPriority
    status: KeyWorkStatus
    progress: int = 0
    planned_finish_date: Optional[date] = None
    acceptance_criteria: Optional[List[str]] = []
    goals: List[KeyWorkGoalOut] = []

    @field_validator("acceptance_criteria", mode="before")
    @classmethod
    def _parse_acceptance(cls, v):
        """DB 中以 JSON 字符串存储，输出时解析为列表。"""
        if v is None or v == "":
            return []
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else [v]
            except Exception:
                return [v]
        if isinstance(v, list):
            return v
        return [v]
    milestones: List[KeyWorkMilestoneOut] = []
    members: List[KeyWorkMemberOut] = []
    monthly_plans: List[KeyWorkMonthlyPlanOut] = []
    weekly_plans: List[KeyWorkWeeklyPlanOut] = []
    progresses: List[KeyWorkProgressOut] = []
    member_tasks: List[KeyWorkMemberTaskOut] = []
    deliverables: List[KeyWorkDeliverableOut] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KeyWorkListItemOut(BaseModel):
    """列表项：仅主表字段，不携带子表（避免列表页触发 8 子表 selectin 全量加载）。

    列表页只展示主表列（编号/标题/分类/状态/优先级/负责人/进度等），
    子表数据由详情接口按需提供。
    """

    id: int
    work_no: str
    category: KeyWorkCategory
    title: str
    owner: Optional[str] = None
    priority: KeyWorkPriority
    status: KeyWorkStatus
    progress: int = 0
    planned_finish_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KeyWorkListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int
    items: List[KeyWorkListItemOut]


class KeyWorkStatsOut(BaseModel):
    by_category: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    overdue_member_tasks: int = 0
    upcoming_milestones: int = 0
    total_member_tasks: int = 0
    done_member_tasks: int = 0


# ---------------------------------------------------------------------------
# 周反馈（在途工单增量更新）
# ---------------------------------------------------------------------------
class WeeklyFeedbackItemUpdate(BaseModel):
    """周反馈中的子项状态更新（月/周计划、成员待办）。"""

    type: str = Field(..., description="monthly/weekly/task")
    id: int = Field(..., description="子表记录ID")
    status: str = Field(..., description="新状态")


class WeeklyFeedbackMemberTaskNote(BaseModel):
    """成员任务进展说明。"""

    task_id: int = Field(..., description="成员任务ID")
    note: Optional[str] = Field(None, description="进展说明")
    status: Optional[str] = Field(None, description="更新后的状态")


class WeeklyFeedbackNewTask(BaseModel):
    """在周反馈中顺手新增的成员任务。"""

    title: str = Field(..., max_length=500, description="待办标题")
    assignee: Optional[str] = Field(None, max_length=64, description="负责人")
    due_date: Optional[date] = Field(None, description="截止日期")
    note: Optional[str] = Field(None, description="备注")
    link_type: Optional[str] = Field("none", description="关联对象类型")
    link_id: Optional[int] = Field(None, description="关联对象ID")

    @field_validator("due_date", mode="before")
    @classmethod
    def _empty_due_date_to_none(cls, v):
        return None if v in ("", None) else v


class KeyWorkWeeklyFeedbackCreate(BaseModel):
    week: str = Field(..., max_length=10, description="周次 YYYY-Www")
    assignee: str = Field(..., max_length=64, description="责任人")
    source: str = Field("manual", max_length=16, description="来源 manual/email/link")
    feedback_date: Optional[date] = Field(None, description="反馈日期")
    done_summary: Optional[str] = Field(None, description="本周完成")
    next_summary: Optional[str] = Field(None, description="下周计划")
    monthly_summary: Optional[str] = Field(None, description="本月月总结（月底周）")
    next_month_summary: Optional[str] = Field(None, description="下月重点/下月月计划草案（月底周）")
    risk_note: Optional[str] = Field(None, description="风险/求助")
    progress: Optional[int] = Field(None, ge=0, le=100, description="该责任人进度%")
    item_updates: Optional[List[WeeklyFeedbackItemUpdate]] = Field(None, description="月/周计划子项状态更新明细")
    member_task_notes: Optional[List[WeeklyFeedbackMemberTaskNote]] = Field(None, description="成员任务进展说明")
    new_tasks: Optional[List[WeeklyFeedbackNewTask]] = Field(None, description="新增成员任务")
    deliverable_ids: Optional[List[int]] = Field(None, description="本次反馈关联交付物ID列表")
    raw_text: Optional[str] = Field(None, description="原始反馈全文")

    @field_validator("feedback_date", mode="before")
    @classmethod
    def _empty_feedback_date_to_none(cls, v):
        return None if v in ("", None) else v


class KeyWorkWeeklyFeedbackOut(BaseModel):
    id: int
    key_work_id: int
    week: str
    assignee: str
    source: str = "manual"
    feedback_date: Optional[date] = None
    done_summary: Optional[str] = None
    next_summary: Optional[str] = None
    monthly_summary: Optional[str] = None
    next_month_summary: Optional[str] = None
    risk_note: Optional[str] = None
    progress: Optional[int] = None
    item_updates: List[dict] = []
    member_task_notes: List[dict] = []
    new_tasks: List[dict] = []
    deliverable_ids: List[int] = []
    status: str = "submitted"
    raw_text: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("item_updates", "member_task_notes", "deliverable_ids", mode="before")
    @classmethod
    def _parse_json_fields(cls, v):
        if v is None or v == "":
            return []
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else [parsed]
            except Exception:
                return []
        return v or []

    class Config:
        from_attributes = True


class KeyWorkFeedbackMailRequest(BaseModel):
    """周反馈请求邮件发送请求。"""

    week: str = Field(..., max_length=10, description="周次 YYYY-Www")
    assignees: Optional[List[str]] = Field(None, description="指定责任人（缺省=全部责任人）")
