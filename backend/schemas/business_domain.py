"""业务领域管理 — Schema"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class BusinessDomainCreate(BaseModel):
    """新增业务领域（管理入口使用）。"""

    domain_code: str = Field(..., max_length=64, description="业务编码，如 ftto")
    domain_name: str = Field(..., max_length=128, description="中文名称，如 FTTO")
    domain_group: str = Field(default="政企业务", max_length=64, description="业务大类")
    vault_path: Optional[str] = Field(None, max_length=512, description="Obsidian vault 路径")
    match_keywords: Optional[str] = Field(None, max_length=512, description="分类关键词（逗号分隔），用于 vault 同步时归类扁平笔记")
    parent_domain_code: Optional[str] = Field(None, max_length=64, description="父领域编码（NULL=一级大类）")
    description: Optional[str] = Field(None, description="描述/说明")
    sort_order: int = Field(default=0, description="排序号")
    enabled: bool = Field(default=True, description="是否启用")


class BusinessDomainUpdate(BaseModel):
    """修改业务领域。"""

    domain_name: Optional[str] = Field(None, max_length=128)
    domain_group: Optional[str] = Field(None, max_length=64)
    vault_path: Optional[str] = Field(None, max_length=512)
    match_keywords: Optional[str] = Field(None, max_length=512)
    parent_domain_code: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = Field(None)
    sort_order: Optional[int] = None
    enabled: Optional[bool] = None


class BusinessDomainOut(BaseModel):
    """业务领域输出（扁平，树形由前端/API 组装）。"""

    id: int
    domain_code: str
    domain_name: str
    domain_group: str
    vault_path: Optional[str] = None
    match_keywords: Optional[str] = None
    parent_domain_code: Optional[str] = None
    description: Optional[str] = None
    sort_order: int = 0
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # 关联计数（按业务领域浏览时展示，后端聚合）
    knowledge_count: int = 0
    req_count: int = 0
    issue_count: int = 0
    meeting_count: int = 0

    model_config = {"from_attributes": True}


class BusinessDomainTreeNode(BusinessDomainOut):
    """树形节点（含子节点）。"""

    children: List["BusinessDomainTreeNode"] = []

    model_config = {"from_attributes": True}


class DomainRelatedItem(BaseModel):
    """关联内容条目（需求/会议/运营工单/知识）。"""

    id: Optional[int] = None
    code: str
    title: str
    sub_title: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    obsidian_path: Optional[str] = None


class DomainRelatedOut(BaseModel):
    """业务领域关联聚合（知识中心按领域浏览详情）。"""

    domain_code: str
    domain_name: str
    knowledge_items: List[DomainRelatedItem] = []
    requirements: List[DomainRelatedItem] = []
    meetings: List[DomainRelatedItem] = []
    issues: List[DomainRelatedItem] = []

    model_config = {"from_attributes": True}
