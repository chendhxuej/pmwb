"""底层大模型提供方管理 API。"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.exceptions import ValidationException
from core.response import success
from db.base import get_db
from services import llm_provider as svc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/llm-providers", tags=["大模型管理"])


class ProviderIn(BaseModel):
    name: str
    provider_type: str = "openai"
    base_url: str = ""
    model: str = ""
    api_key: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 120
    is_enabled: bool = True
    is_default: bool = False
    priority: int = 0


@router.get("")
def list_all(db: Session = Depends(get_db)):
    return success(data=svc.list_providers(db))


@router.get("/presets")
def presets():
    return success(data=svc.PROVIDER_PRESETS)


@router.post("")
def create(req: ProviderIn, db: Session = Depends(get_db)):
    return success(data=svc.create_provider(db, req.model_dump()))


@router.get("/{pid}")
def get_one(pid: int, db: Session = Depends(get_db)):
    p = svc.get_provider(db, pid)
    if not p:
        raise ValidationException("大模型提供方不存在")
    return success(data=p)


@router.put("/{pid}")
def update(pid: int, req: ProviderIn, db: Session = Depends(get_db)):
    return success(data=svc.update_provider(db, pid, req.model_dump()))


@router.delete("/{pid}")
def delete(pid: int, db: Session = Depends(get_db)):
    svc.delete_provider(db, pid)
    return success(message="已删除")


@router.post("/{pid}/set-default")
def set_default(pid: int, db: Session = Depends(get_db)):
    return success(data=svc.set_default(db, pid))


@router.post("/{pid}/test")
def test(pid: int, db: Session = Depends(get_db)):
    p = svc.get_provider_row(db, pid)
    if not p:
        raise ValidationException("大模型提供方不存在")
    return success(data=svc.test_provider(p))
