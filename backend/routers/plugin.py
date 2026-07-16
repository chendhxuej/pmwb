"""插件接入路由：承接原 2525 本地中继，由 PMWB 统一托管。

注意：这些端点是 Chrome 插件（原生 fetch，不经过前端拦截器）直连调用的，
因此返回**扁平 JSON**（{"success": ...}），不套用 core.response.success 的 code/data 包装。
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.base import get_db
from services.plugin import plugin_service

router = APIRouter(prefix="/plugins", tags=["插件接入"])


# ---------------- 请求模型 ----------------
class PluginSendRequest(BaseModel):
    to: str
    cc: Optional[str] = None
    subject: str
    body: Optional[str] = None
    html: Optional[str] = None
    # attachments / smtp 由插件传入但 PMWB 统一邮件中心暂不支持附件，忽略
    attachments: Optional[List[Any]] = None


class PluginIngestRequest(BaseModel):
    # 扁平字段（插件直接发送），亦兼容 {dbConfig, data} 嵌套
    reqId: str = ""
    reqName: str = ""
    proposer: str = ""
    proposeTime: str = ""
    involveDev: str = "是"
    background: str = ""
    description: str = ""
    clarification: str = ""
    system: str = ""
    sa: str = ""
    sendDateTime: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class SaInfoCreate(BaseModel):
    sa_name: str
    system_name: str = ""
    email: str
    wechat_nickname: str = ""


class SaInfoUpdate(BaseModel):
    old_name: str
    old_system: str = ""
    old_email: str
    sa_name: str
    system_name: str = ""
    email: str
    wechat_nickname: str = ""


# ---------------- 健康检查（对齐 2525 /health，插件检查 status==='ok'）----------------
@router.get("/health")
def plugin_health():
    return {"status": "ok"}


# ---------------- 发信（对齐 2525 /send）----------------
@router.post("/send")
def plugin_send(req: PluginSendRequest):
    body = req.html or req.body or ""
    body_format = "html" if req.html else "text"
    try:
        result = plugin_service.send_email(
            to=req.to,
            subject=req.subject,
            body=body,
            cc=req.cc,
            body_format=body_format,
        )
        return result
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}


# ---------------- 写入 sent_emails（对齐 2525 /write-db）----------------
@router.post("/ingest")
def plugin_ingest(req: PluginIngestRequest, db: Session = Depends(get_db)):
    try:
        # 兼容 {dbConfig, data} 嵌套与扁平两种传法
        raw = req.data if req.data else req.model_dump(exclude={"data"})
        insert_id = plugin_service.ingest(db, raw)
        return {"success": True, "affectedRows": 1, "insertId": insert_id}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}


# ---------------- 收件人列表（对齐 2525 /query-sa-info）----------------
@router.get("/contacts")
def list_contacts(db: Session = Depends(get_db)):
    try:
        contacts = plugin_service.list_contacts(db)
        return {"success": True, "contacts": contacts}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}


@router.get("/contacts/check")
def check_contact_duplicate(
    sa_name: str = Query(..., description="SA姓名"),
    system_name: str = Query("", description="系统名称"),
    db: Session = Depends(get_db),
):
    try:
        exists = plugin_service.check_duplicate(db, sa_name, system_name)
        return {"success": True, "exists": exists}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}


@router.post("/contacts")
def add_contact(req: SaInfoCreate, db: Session = Depends(get_db)):
    try:
        insert_id = plugin_service.add_contact(
            db, req.sa_name, req.system_name, req.email, req.wechat_nickname
        )
        return {"success": True, "insertId": insert_id}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}


@router.put("/contacts")
def update_contact(req: SaInfoUpdate, db: Session = Depends(get_db)):
    try:
        affected = plugin_service.update_contact(
            db,
            req.old_name,
            req.old_system,
            req.old_email,
            req.sa_name,
            req.system_name,
            req.email,
            req.wechat_nickname,
        )
        return {"success": True, "affectedRows": affected}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}


@router.delete("/contacts")
def delete_contact(
    sa_name: str = Query(..., description="SA姓名"),
    system_name: str = Query("", description="系统名称"),
    email: str = Query(..., description="邮箱"),
    db: Session = Depends(get_db),
):
    try:
        affected = plugin_service.delete_contact(db, sa_name, system_name, email)
        return {"success": True, "affectedRows": affected}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}
