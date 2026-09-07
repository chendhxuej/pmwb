"""业务资料库 - 请求/响应 Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from schemas.common import PaginationResponse

# ----------------------------------------------------------------- 分类
class MaterialCategoryCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=64, description="分类编码，全局唯一")
    name: str = Field(..., min_length=1, max_length=128, description="分类名称")
    parent_id: Optional[int] = Field(None, description="父分类ID，空=一级分类")
    sort_order: int = 0
    enabled: bool = True


class MaterialCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    parent_id: Optional[int] = Field(None, description="可改父级；不可指向自身或自己的子孙")
    sort_order: Optional[int] = None
    enabled: Optional[bool] = None


class MaterialCategoryOut(BaseModel):
    id: int
    code: str
    name: str
    parent_id: Optional[int]
    sort_order: int
    enabled: bool
    created_at: Optional[datetime]
    children_count: int = 0
    material_count: int = 0

    model_config = {"from_attributes": True}


# ----------------------------------------------------------------- 材料
class MaterialListItem(BaseModel):
    id: int
    category_id: Optional[int]
    category_name: Optional[str]
    domain_code: Optional[str]
    source_type: str
    source_label: str
    source_id: str
    source_no: str
    source_title: str
    file_name: str
    file_size: Optional[int]
    file_size_human: str
    file_ext: str
    file_type: Optional[str]
    origin: str
    note: Optional[str]
    tags: Optional[str]
    download_count: int
    can_preview: bool
    created_at: Optional[datetime]

    model_config = {"from_attributes": True}


class MaterialListResponse(BaseModel):
    items: List[MaterialListItem]
    total: int
    page: int
    page_size: int
    pages: int
    source_stats: List[dict] = []


class MaterialOut(MaterialListItem):
    stored_name: str
    storage_root: str
    rel_path: str


class MaterialReassign(BaseModel):
    category_id: Optional[int] = Field(None, description="置空则取消分类")


class MaterialDeleteOptions(BaseModel):
    remove_physical: bool = Field(False, description="是否同时删除物理文件（仅手工上传且为 uploads 根时生效）")


class MaterialUploadResult(BaseModel):
    id: int
    file_name: str
    file_size: int
    file_ext: str
    category_id: Optional[int]


# ----------------------------------------------------------------- 汇聚
class MaterialSyncResponse(BaseModel):
    added: int
    total: int
    sources: List[dict]
