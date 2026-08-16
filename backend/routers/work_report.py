"""AI 工作总结报告路由。"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from services import work_report as svc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/work-reports", tags=["AI总结报告"])


class GenerateRequest(BaseModel):
    report_type: str = "daily"
    date_start: Optional[str] = None
    date_end: Optional[str] = None


class UpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    report_type: Optional[str] = None


class SendRequest(BaseModel):
    to: list[str]
    cc: list[str] = []
    subject: str
    body: str


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:  # noqa: BLE001
        return None


@router.post("/generate")
def generate(req: GenerateRequest, db: Session = Depends(get_db)):
    params = {
        "report_type": req.report_type,
        "date_start": _parse_date(req.date_start),
        "date_end": _parse_date(req.date_end),
    }
    return success(data=svc.generate_report(db, params))


@router.get("")
def list_all(status: Optional[str] = None, db: Session = Depends(get_db)):
    return success(data=svc.list_reports(db, status))


@router.get("/{report_id}")
def get_one(report_id: int, db: Session = Depends(get_db)):
    return success(data=svc.get_report(db, report_id))


@router.put("/{report_id}")
def update(report_id: int, req: UpdateRequest, db: Session = Depends(get_db)):
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    if "date_start" in data:
        data["date_start"] = _parse_date(data["date_start"])
    if "date_end" in data:
        data["date_end"] = _parse_date(data["date_end"])
    return success(data=svc.update_report(db, report_id, data))


@router.delete("/{report_id}")
def delete(report_id: int, db: Session = Depends(get_db)):
    svc.delete_report(db, report_id)
    return success(message="已删除")


@router.post("/{report_id}/finalize")
def finalize(report_id: int, db: Session = Depends(get_db)):
    return success(data=svc.finalize_report(db, report_id))


@router.post("/{report_id}/send")
def send(report_id: int, req: SendRequest, db: Session = Depends(get_db)):
    return success(data=svc.send_report(db, report_id, req.model_dump()))
