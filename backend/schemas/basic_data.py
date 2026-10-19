"""基础数据（组织+人员+角色）Pydantic Schema。"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# 角色/身份定义
# ---------------------------------------------------------------------------
class RoleCreate(BaseModel):
    name: str
    sort: Optional[int] = 0
    enabled: Optional[bool] = True


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    sort: Optional[int] = None
    enabled: Optional[bool] = None


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort: Optional[int] = 0
    enabled: bool = True
    created_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# 组织
# ---------------------------------------------------------------------------
class OrgCreate(BaseModel):
    name: str
    description: Optional[str] = None
    sort: Optional[int] = 0
    enabled: Optional[bool] = True
    # ── 系统别名映射（2026-10-19 修复）────────────────────────
    # 前端经本服务代理保存组织；此处若缺字段，Pydantic 会**静默丢弃**，
    # 导致映射配置"保存成功但没生效"（org_type 回落 department）。
    # 长度与中台 schemas 及库表 String(n) 对齐，超长在 422 层拦截。
    org_type: Optional[str] = Field(default=None, max_length=32)
    target_system_name: Optional[str] = Field(default=None, max_length=128)
    aliases: Optional[str] = Field(default=None, max_length=512)


class OrgUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sort: Optional[int] = None
    enabled: Optional[bool] = None
    org_type: Optional[str] = Field(default=None, max_length=32)
    target_system_name: Optional[str] = Field(default=None, max_length=128)
    aliases: Optional[str] = Field(default=None, max_length=512)


class OrgOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort: Optional[int] = 0
    enabled: bool = True
    created_at: Optional[datetime] = None
    staff_count: Optional[int] = 0


# ---------------------------------------------------------------------------
# 人员
# ---------------------------------------------------------------------------
class StaffCreate(BaseModel):
    name: str
    org_id: int
    email: Optional[str] = None
    phone: Optional[str] = None
    role_hint: Optional[str] = None
    sort: Optional[int] = 0
    enabled: Optional[bool] = True


class StaffUpdate(BaseModel):
    name: Optional[str] = None
    org_id: Optional[int] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role_hint: Optional[str] = None
    sort: Optional[int] = None
    enabled: Optional[bool] = None


class StaffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    org_id: int
    org_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role_hint: Optional[str] = None
    sort: Optional[int] = 0
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# 批量导入
# ---------------------------------------------------------------------------
class StaffImportRow(BaseModel):
    """Excel 导入单行结构。"""

    org_name: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role_hint: Optional[str] = None
    sort: Optional[int] = 0
    enabled: Optional[bool] = True


class OrgStaffImportOut(BaseModel):
    """批量导入结果。"""

    created_orgs: int = 0
    updated_orgs: int = 0
    created_staffs: int = 0
    updated_staffs: int = 0
    errors: List[str] = []

class StaffOption(BaseModel):
    value: str
    label: str
    email: Optional[str] = None
    role_hint: Optional[str] = None


class StaffOptionGroup(BaseModel):
    org_id: int
    org_name: str
    options: List[StaffOption]


# ---------------------------------------------------------------------------
# 轻量选项（下拉用）
# ---------------------------------------------------------------------------
class OrgOption(BaseModel):
    """组织下拉选项（仅 id+name）。"""
    id: int
    name: str


class RoleOption(BaseModel):
    """身份下拉选项（仅 id+name）。"""
    id: int
    name: str
