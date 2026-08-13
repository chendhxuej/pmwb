"""AI 问答模块请求/响应 Schema。"""
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class AiQaMessage(BaseModel):
    """单条对话历史（多轮问答时使用）。"""
    role: str = Field(..., description="角色：user / assistant")
    content: str = Field(..., description="消息内容")


class AiQaAskIn(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    history: Optional[List[AiQaMessage]] = Field(
        default=None, description="可选的历史对话（最近若干轮），用于多轮上下文"
    )


class AiQaSource(BaseModel):
    idx: int = Field(..., description="来源序号（回答中可引用）")
    type: str = Field(..., description="来源类型：db / obsidian")
    title: str = Field(..., description="来源标题")
    ref: str = Field(..., description="来源引用（需求编号 / 工单号 / 笔记路径）")
    snippet: str = Field(..., description="命中的片段摘要")


class AiQaAskOut(BaseModel):
    answer: str = Field(..., description="AI 生成的回答")
    sources: List[AiQaSource] = Field(default_factory=list, description="引用的检索来源")
    used_llm: bool = Field(..., description="是否实际调用了大模型")
    provider_name: Optional[str] = Field(None, description="实际使用的模型提供方名称")
    notice: Optional[str] = Field(None, description="未使用大模型时的提示信息")
    semantic_rewrite: Optional[bool] = Field(
        None, description="是否启用了 LLM 查询改写（语义扩展检索词）"
    )
    retrieval: Optional[Dict] = Field(
        None, description="检索透明度元数据：db_hits/ob_hits/used/semantic_rewrite/top_score"
    )
