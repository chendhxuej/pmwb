"""基础数据（组织+人员+角色）Pydantic Schema。"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


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
    sort: Optional[int] = 0
    enabled: Optional[bool] = True


class OrgUpdate(BaseModel):
    name: Optional[str] = None
    sort: Optional[int] = None
    enabled: Optional[bool] = None


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
