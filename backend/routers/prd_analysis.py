"""PRD 需求分析端点。

独立前缀 /prd（避开 /requirements/{req_id} 通配，零路由冲突）。
业务语义仍挂在需求详情步骤 3，仅 URL 独立。
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy.orm import Session

from core.config import settings
from core.response import success
from db.base import get_db
from db.models import PmwbPrdAnalysis
from schemas.prd_analysis import (
    PrdAnalyzeIn,
    PrdAnalyzeOut,
    PrdMetaOut,
    PrdSourcesOut,
    PrdStatusOut,
)
from services import prd_analysis as svc

router = APIRouter(prefix="/prd", tags=["PRD需求分析"])


@router.get("/meta")
def get_meta(db: Session = Depends(get_db)):
    """一次性问卷元数据：十维（单一真相源）、系统、知识状态、LLM 可用性。"""
    return success(data=PrdMetaOut(**svc.meta(db)).model_dump())


@router.get("/knowledge-status")
def get_knowledge_status():
    """知识源状态（只读 manifest.json，不执行 Git）。"""
    return success(data=svc.knowledge_status())


@router.post("/analyze/{req_id}")
def analyze(req_id: str, payload: PrdAnalyzeIn, db: Session = Depends(get_db)):
    """提交需求分析：五步编排 → PRD 六章 + 冲突 + 引用（LLM 全失败降级规则模板）。"""
    try:
        data = svc.analyze(
            db, req_id,
            raw_requirement=payload.raw_requirement,
            systems=payload.systems,
            mode=payload.mode,
            profile=payload.profile,
            answers=payload.answers,
            req_name=payload.req_name,
            special_notes=payload.special_notes,
            prototype=payload.prototype,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(data=PrdAnalyzeOut(**data).model_dump())


@router.get("/status/{req_id}")
def get_status(req_id: str, db: Session = Depends(get_db)):
    """该需求最近一次分析状态（前端重开页面时溯源）。"""
    data = svc.latest_status(db, req_id)
    if not data:
        return success(data=None)
    return success(data=PrdStatusOut(**data).model_dump())


@router.get("/sources/{trace_id}")
def get_sources(trace_id: str, db: Session = Depends(get_db)):
    """引用来源 + 冲突清单 + 假设/待确认（MySQL 落库后可独立查询）。"""
    try:
        data = svc.get_result(db, trace_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return success(data=PrdSourcesOut(**data).model_dump())


@router.post("/finalize/{trace_id}")
def finalize(trace_id: str, db: Session = Depends(get_db)):
    """确认落库（老大显式点击，与邮件真发同纪律：AI 自测不触碰）。"""
    try:
        data = svc.finalize(db, trace_id)
    except (LookupError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(data=data, message="PRD 已确认落库")


@router.get("/download/{trace_id}")
def download(trace_id: str, db: Session = Depends(get_db)):
    """下载 PRD.md（FileResponse attachment + RFC5987 中文名）。"""
    try:
        data = svc.get_result(db, trace_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    row = db.query(PmwbPrdAnalysis).filter_by(trace_id=trace_id).first()
    if not row or not row.prd_file_path:
        raise HTTPException(status_code=404, detail="PRD 文件未落盘（可能受环境限制）")
    fp = Path(settings.OBSIDIAN_VAULT_PATH) / row.prd_file_path
    if not fp.is_file():
        raise HTTPException(status_code=404, detail="PRD 文件不存在")
    return FileResponse(str(fp), filename="PRD.md", media_type="text/markdown")
