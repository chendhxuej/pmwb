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
