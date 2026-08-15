"""AI 问答端点：基于项目数据库 + Obsidian 笔记的智能查询。"""
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from schemas.ai_qa import AiQaAskIn, AiQaAskOut, AiQaMessage, AiQaSource
from services import ai_qa as svc

router = APIRouter(prefix="/ai-qa", tags=["AI问答"])


@router.post("/ask", response_model=None)
def ask(payload: AiQaAskIn, db: Session = Depends(get_db)):
    """基于项目数据库与 Obsidian 笔记智能回答用户问题。"""
    history = None
    if payload.history:
        history = [m.model_dump() for m in payload.history]
    data = svc.ask(db, payload.question, history=history)
    # 转换为带 Schema 校验的字典，便于前端约定
    out = AiQaAskOut(
        answer=data["answer"],
        sources=[AiQaSource(**s) for s in data["sources"]],
        used_llm=data["used_llm"],
        provider_name=data["provider_name"],
        notice=data["notice"],
        semantic_rewrite=data.get("semantic_rewrite"),
        retrieval=data.get("retrieval"),
    )
    return success(data=out.model_dump())


@router.get("/status")
def status(db: Session = Depends(get_db)):
    """查询 AI 问答可用的大模型状态（统一取自「大模型管理」注册表）。"""
    from services.llm_provider import get_status
    return success(data=get_status(db))
