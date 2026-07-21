import json
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# 输出字段样例（结构化清单）
# ---------------------------------------------------------------------------
class SqlScriptField(BaseModel):
    name: str = Field(..., description="字段名")
    type: Optional[str] = Field(None, description="字段类型")
    desc: Optional[str] = Field(None, description="字段说明")


# ---------------------------------------------------------------------------
# 创建 / 更新
# ---------------------------------------------------------------------------
class SqlScriptCreate(BaseModel):
    title: str = Field(..., max_length=500, description="脚本说明/名称")
    category: Optional[str] = Field(None, max_length=64, description="业务线/分类")
    description: Optional[str] = Field(None, description="补充说明")
    sql_text: str = Field(..., description="SQL 文本")
    output_fields: Optional[List[SqlScriptField]] = Field(
        None, description="输出字段样例清单"
    )


class SqlScriptUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500, description="脚本说明/名称")
    category: Optional[str] = Field(None, max_length=64, description="业务线/分类")
    description: Optional[str] = Field(None, description="补充说明")
    sql_text: Optional[str] = Field(None, description="SQL 文本")
    output_fields: Optional[List[SqlScriptField]] = Field(
        None, description="输出字段样例清单"
    )


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------
class SqlScriptOut(BaseModel):
    id: int
    script_no: str
    title: str
    category: Optional[str] = None
    description: Optional[str] = None
    sql_text: str
    output_fields: List[SqlScriptField] = []

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_validator("output_fields", mode="before")
    @classmethod
    def _parse_output_fields(cls, v):
        """DB 中以 JSON 字符串存储，输出时解析为列表。"""
        if v is None or v == "":
            return []
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
                return []
            except Exception:
                return []
        if isinstance(v, list):
            return v
        return []


class SqlScriptListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int
    items: List[SqlScriptOut]
