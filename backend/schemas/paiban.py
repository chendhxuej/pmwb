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
