"""客诉专题 Pydantic 模型（白名单显式声明，防字段静默丢失）。"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class CategoryCorrectIn(BaseModel):
    """人工校正分类（classify_by 置 manual，reclassify 不覆盖）。"""
    category_l1: str = Field(..., max_length=64, description="一级性质")
    category_l2: str = Field("", max_length=64, description="二级场景（可为空）")
    remark: Optional[str] = Field(None, description="校正备注")


class CategoryEnabledIn(BaseModel):
    enabled: int = Field(..., ge=0, le=1, description="1 启用 / 0 停用")


class ActionCreateIn(BaseModel):
    """登记改进措施。"""
    l2: str = Field(..., max_length=64, description="二级问题场景（须在字典中）")
    title: str = Field(..., max_length=255)
    owner: str = Field(..., max_length=255, description="责任人（多负责人逗号分隔）")
    due_date: Optional[date] = Field(None, description="要求完成日期")
    acceptance: str = Field(..., description="验收标准（可验证）")
    desc: str = Field("", description="情况说明")
    create_issue: bool = Field(False, description="是否同步创建运营工单父子关联")
    problem_nos: list[str] = Field(default_factory=list, description="所属共性问题编号（多选）")


class ActionUpdateIn(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    owner: Optional[str] = Field(None, max_length=255)
    due_date: Optional[date] = None
    acceptance: Optional[str] = None
    note: Optional[str] = None
    target_drop_pct: Optional[float] = Field(None, ge=0, le=100)
    verify_weeks: Optional[int] = Field(None, ge=1, le=26)


class GoLiveIn(BaseModel):
    go_live_date: date = Field(..., description="措施生效日")


class ReportGenIn(BaseModel):
    week: Optional[str] = Field(None, description="周次（默认库内最新周）")
    with_pdf: bool = Field(True, description="是否导出 PDF（失败自动降级仅 HTML）")


class UrgePreviewIn(BaseModel):
    """客诉措施督办邮件（默认 dry_run；真发须前端显式 confirm_send=True）。"""
    owner: Optional[str] = Field(None, description="仅督办指定责任人（空=全部超期措施）")
    subject: Optional[str] = Field(None, description="自定义主题（默认场景主题）")
    confirm_send: bool = Field(False, description="确认真发（False 仅 dry_run 落库验证）")


# ── 共性问题台账（闭环管理） ──────────────────────────────────
class ProblemCreateIn(BaseModel):
    """手工立问题（source_type=manual）。"""
    category_l2: str = Field(..., max_length=64, description="二级问题场景（须在字典中）")
    title: str = Field(..., max_length=255)
    owner: str = Field("", max_length=255, description="责任人（带则直接入账 open）")
    note: Optional[str] = Field(None, description="备注")


class ProblemUpdateIn(BaseModel):
    """编辑基础字段（不含 status）。"""
    title: Optional[str] = Field(None, max_length=255)
    category_l1: Optional[str] = Field(None, max_length=64)
    owner: Optional[str] = Field(None, max_length=255)
    note: Optional[str] = None


class ProblemStatusIn(BaseModel):
    """问题状态流转（status_registry complaint_problem 域校验）。"""
    status: str = Field(..., max_length=32)
    owner: Optional[str] = Field(None, max_length=255)
    conclusion: Optional[str] = Field(None, max_length=500, description="闭环结论（closed 必填）")
    closed_week: Optional[str] = Field(None, max_length=16)
    note: Optional[str] = None


class ProblemConfirmIn(BaseModel):
    """候选确认：open（入账）/ merge（合并）/ ignore（忽略）。"""
    decision: str = Field(..., pattern="^(open|merge|ignore)$")
    owner: str = Field("", max_length=255, description="decision=open 必填")
    merged_into: str = Field("", max_length=64, description="decision=merge 必填")
    note: Optional[str] = None
    confirm_by: str = Field("", max_length=64, description="确认人")


class ProblemActionLinkIn(BaseModel):
    action_no: str = Field(..., max_length=64)
    is_primary: bool = Field(False, description="主措施标记（同问题至多一条）")
    note: Optional[str] = None


class ProblemUrgeIn(BaseModel):
    """问题级督办（复用 complaint_action_urge 场景，dry_run 默认）。"""
    confirm_send: bool = Field(False, description="确认真发（False 仅 dry_run）")
