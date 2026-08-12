from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class KnowledgeItemBase(BaseModel):
    item_id: str = Field(..., max_length=64, description="知识条目编号")
    title: str = Field(..., max_length=255, description="标题")
    category: str = Field(..., max_length=64, description="分类")
    sub_category: Optional[str] = Field(None, max_length=128, description="子分类")
    tags: Optional[str] = Field(None, max_length=512, description="标签，逗号分隔")
    obsidian_path: str = Field(..., max_length=512, description="Obsidian 文件路径")
    source_type: Optional[str] = Field(None, max_length=64, description="来源类型")
    source_id: Optional[str] = Field(None, max_length=64, description="来源对象ID")
    domain_code: Optional[str] = Field(None, max_length=64, description="关联业务领域编码")
    summary: Optional[str] = Field(None, description="摘要")


class KnowledgeItemCreate(KnowledgeItemBase):
    content: Optional[str] = Field(None, description="Markdown 正文内容")


class KnowledgeItemUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=64)
    sub_category: Optional[str] = Field(None, max_length=128)
    tags: Optional[str] = Field(None, max_length=512)
    obsidian_path: Optional[str] = Field(None, max_length=512)
    source_type: Optional[str] = Field(None, max_length=64)
    source_id: Optional[str] = Field(None, max_length=64)
    domain_code: Optional[str] = Field(None, max_length=64)
    summary: Optional[str] = None


class KnowledgeItemOut(KnowledgeItemBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KnowledgeListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int
    items: List[KnowledgeItemOut]


class KnowledgeContentResponse(BaseModel):
    item_id: str
    title: str
    obsidian_path: str
    content: str


class KnowledgeLinkCreate(BaseModel):
    """建立知识条目 ↔ 过程性对象的多对多关联。

    source_type: requirement/ticket/operation/meeting/deliverable/key_work
    source_id: 关联对象业务ID（req_id / 工单id / 会议id / 运营id 等）
    link_type: main(主笔记)/sub(子笔记)/deliverable(交付物)
    """

    source_type: str = Field(..., max_length=64, description="关联对象类型")
    source_id: str = Field(..., max_length=255, description="关联对象业务ID")
    link_type: str = Field("main", max_length=32, description="链接类型")
    domain_code: Optional[str] = Field(None, max_length=64, description="冗余领域编码")
    note: Optional[str] = Field(None, description="关联说明")


class KnowledgeLinkOut(BaseModel):
    """关联记录输出（含知识条目信息）。"""

    link_id: int
    knowledge_item_id: int
    item_id: str
    title: str
    obsidian_path: str
    domain_code: Optional[str] = None
    link_type: str = "main"
    note: Optional[str] = None
    source_type: str
    source_id: str


class KnowledgeLinkBatch(BaseModel):
    """批量关联请求：一个知识条目 ↔ 多个过程性对象。"""

    links: List[KnowledgeLinkCreate] = Field(default_factory=list, description="待建立关联列表")
