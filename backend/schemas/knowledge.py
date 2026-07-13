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
