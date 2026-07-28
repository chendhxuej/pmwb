"""邮件中心代理路由。

将统一邮件中心(3210)的管理 API 透传给 PMWB 前端，同时提供合并日志端点
（邮件中心 SendLog + PMWB 本地 email_records）。
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from core.config import settings
from core.response import error, success
from db.base import get_db
from db.models import EmailRecord
from utils.email import EmailCenterClient, MailCenterProxyClient

logger = logging.getLogger("pmwb.mail_center")

router = APIRouter(prefix="/mail-center", tags=["邮件中心"])

client = EmailCenterClient()
proxy = MailCenterProxyClient()

# ---------------------------------------------------------------------------
# 健康检查
# ---------------------------------------------------------------------------


@router.get("/health")
def mail_center_health():
    """检查统一邮件中心(3210)健康状态。"""
    data = client.health_check()
    return success(data=data)


# ---------------------------------------------------------------------------
# 邮件账号管理
# ---------------------------------------------------------------------------


@router.get("/accounts")
def list_accounts():
    try:
        data = proxy.request("GET", "/api/accounts")
        return success(data=data)
    except Exception as exc:
        logger.warning("代理获取邮件账号列表失败: %s", exc)
        return error(f"获取邮件账号失败: {exc}", code=502)


@router.get("/accounts/{account_id}")
def get_account(account_id: str):
    try:
        data = proxy.request("GET", f"/api/accounts/{account_id}")
        return success(data=data)
    except Exception as exc:
        logger.warning("代理获取邮件账号详情失败: %s", exc)
        return error(f"获取邮件账号详情失败: {exc}", code=502)


@router.post("/accounts")
def create_account(body: dict):
    try:
        data = proxy.request("POST", "/api/accounts", json=body)
        return success(data=data)
    except Exception as exc:
        logger.warning("代理创建邮件账号失败: %s", exc)
        return error(f"创建邮件账号失败: {exc}", code=502)


@router.put("/accounts/{account_id}")
def update_account(account_id: str, body: dict):
    try:
        data = proxy.request("PUT", f"/api/accounts/{account_id}", json=body)
        return success(data=data)
    except Exception as exc:
        logger.warning("代理更新邮件账号失败: %s", exc)
        return error(f"更新邮件账号失败: {exc}", code=502)


@router.delete("/accounts/{account_id}")
def delete_account(account_id: str):
    try:
        proxy.request("DELETE", f"/api/accounts/{account_id}")
        return success(data={"deleted": True})
    except Exception as exc:
        logger.warning("代理删除邮件账号失败: %s", exc)
        return error(f"删除邮件账号失败: {exc}", code=502)


@router.post("/accounts/{account_id}/set-default")
def set_default_account(account_id: str):
    try:
        data = proxy.request("POST", f"/api/accounts/{account_id}/set-default")
        return success(data=data)
    except Exception as exc:
        logger.warning("代理设置默认账号失败: %s", exc)
        return error(f"设置默认账号失败: {exc}", code=502)


@router.post("/accounts/{account_id}/test")
def test_account(account_id: str):
    try:
        data = proxy.request("POST", f"/api/send/test-account/{account_id}")
        return success(data=data)
    except Exception as exc:
        logger.warning("代理测试邮件账号失败: %s", exc)
        return error(f"测试邮件账号失败: {exc}", code=502)


# ---------------------------------------------------------------------------
# 通讯录管理
# ---------------------------------------------------------------------------


@router.get("/contacts")
def list_contacts(search: str = Query(default=None), group_id: str = Query(default=None)):
    try:
        params: dict = {}
        if search:
            params["search"] = search
        if group_id:
            params["groupId"] = group_id
        data = proxy.request("GET", "/api/contacts", params=params or None)
        return success(data=data)
    except Exception as exc:
        logger.warning("代理获取通讯录失败: %s", exc)
        return error(f"获取通讯录失败: {exc}", code=502)


@router.post("/contacts")
def create_contact(body: dict):
    try:
        data = proxy.request("POST", "/api/contacts", json=body)
        return success(data=data)
    except Exception as exc:
        logger.warning("代理创建联系人失败: %s", exc)
        return error(f"创建联系人失败: {exc}", code=502)


@router.put("/contacts/{contact_id}")
def update_contact(contact_id: str, body: dict):
    try:
        data = proxy.request("PUT", f"/api/contacts/{contact_id}", json=body)
        return success(data=data)
    except Exception as exc:
        logger.warning("代理更新联系人失败: %s", exc)
        return error(f"更新联系人失败: {exc}", code=502)


@router.delete("/contacts/{contact_id}")
def delete_contact(contact_id: str):
    try:
        proxy.request("DELETE", f"/api/contacts/{contact_id}")
        return success(data={"deleted": True})
    except Exception as exc:
        logger.warning("代理删除联系人失败: %s", exc)
        return error(f"删除联系人失败: {exc}", code=502)


# ---------------------------------------------------------------------------
# 联系人分组管理
# ---------------------------------------------------------------------------


@router.get("/contact-groups")
def list_contact_groups():
    try:
        data = proxy.request("GET", "/api/contact-groups")
        return success(data=data)
    except Exception as exc:
        logger.warning("代理获取联系人分组失败: %s", exc)
        return error(f"获取联系人分组失败: {exc}", code=502)


@router.post("/contact-groups")
def create_contact_group(body: dict):
    try:
        data = proxy.request("POST", "/api/contact-groups", json=body)
        return success(data=data)
    except Exception as exc:
        logger.warning("代理创建联系人分组失败: %s", exc)
        return error(f"创建联系人分组失败: {exc}", code=502)


@router.put("/contact-groups/{group_id}")
def update_contact_group(group_id: str, body: dict):
    try:
        data = proxy.request("PUT", f"/api/contact-groups/{group_id}", json=body)
        return success(data=data)
    except Exception as exc:
        logger.warning("代理更新联系人分组失败: %s", exc)
        return error(f"更新联系人分组失败: {exc}", code=502)


@router.delete("/contact-groups/{group_id}")
def delete_contact_group(group_id: str):
    try:
        proxy.request("DELETE", f"/api/contact-groups/{group_id}")
        return success(data={"deleted": True})
    except Exception as exc:
        logger.warning("代理删除联系人分组失败: %s", exc)
        return error(f"删除联系人分组失败: {exc}", code=502)


# ---------------------------------------------------------------------------
# 邮件模板管理
# ---------------------------------------------------------------------------


@router.get("/templates")
def list_templates(template_type: str = Query(default=None)):
    try:
        params = {"type": template_type} if template_type else None
        data = proxy.request("GET", "/api/templates", params=params)
        return success(data=data)
    except Exception as exc:
        logger.warning("代理获取邮件模板失败: %s", exc)
        return error(f"获取邮件模板失败: {exc}", code=502)


@router.get("/templates/{template_id}")
def get_template(template_id: str):
    try:
        data = proxy.request("GET", f"/api/templates/{template_id}")
        return success(data=data)
    except Exception as exc:
        logger.warning("代理获取邮件模板详情失败: %s", exc)
        return error(f"获取邮件模板详情失败: {exc}", code=502)


@router.post("/templates")
def create_template(body: dict):
    try:
        data = proxy.request("POST", "/api/templates", json=body)
        return success(data=data)
    except Exception as exc:
        logger.warning("代理创建邮件模板失败: %s", exc)
        return error(f"创建邮件模板失败: {exc}", code=502)


@router.put("/templates/{template_id}")
def update_template(template_id: str, body: dict):
    try:
        data = proxy.request("PUT", f"/api/templates/{template_id}", json=body)
        return success(data=data)
    except Exception as exc:
        logger.warning("代理更新邮件模板失败: %s", exc)
        return error(f"更新邮件模板失败: {exc}", code=502)


@router.delete("/templates/{template_id}")
def delete_template(template_id: str):
    try:
        proxy.request("DELETE", f"/api/templates/{template_id}")
        return success(data={"deleted": True})
    except Exception as exc:
        logger.warning("代理删除邮件模板失败: %s", exc)
        return error(f"删除邮件模板失败: {exc}", code=502)


@router.post("/templates/{template_id}/render")
def render_template(template_id: str, body: dict):
    try:
        data = proxy.request("POST", f"/api/templates/{template_id}/render", json=body)
        return success(data=data)
    except Exception as exc:
        logger.warning("代理渲染邮件模板失败: %s", exc)
        return error(f"渲染邮件模板失败: {exc}", code=502)


# ---------------------------------------------------------------------------
# 发送日志（直接代理邮件中心 SendLog）
# ---------------------------------------------------------------------------


@router.get("/logs")
def list_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    log_type: str = Query(default=None),
    status: str = Query(default=None),
    search: str = Query(default=None),
    start_date: str = Query(default=None),
    end_date: str = Query(default=None),
):
    try:
        params: dict = {"page": page, "pageSize": page_size}
        if log_type:
            params["type"] = log_type
        if status:
            params["status"] = status
        if search:
            params["search"] = search
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        data = proxy.request("GET", "/api/logs", params=params)
        return success(data=data)
    except Exception as exc:
        logger.warning("代理获取发送日志失败: %s", exc)
        return error(f"获取发送日志失败: {exc}", code=502)


# ---------------------------------------------------------------------------
# 合并发送日志辅助函数
# ---------------------------------------------------------------------------

CST = timezone(timedelta(hours=8))


def _normalize_mc_log(raw: dict) -> dict:
    """将邮件中心 SendLog 归一化为统一日志格式。"""
    sent_at = raw.get("sentAt") or raw.get("createdAt") or ""
    return {
        "id": f"mc_{raw.get('id', '')}",
        "source": "mail-center",
        "sentAt": sent_at,
        "type": raw.get("type") or "",
        "fromEmail": raw.get("fromEmail") or "",
        "to": raw.get("to") or "",
        "cc": raw.get("cc") or "",
        "subject": raw.get("subject") or "",
        "body": raw.get("body") or "",
        "bodyFormat": raw.get("bodyFormat") or "html",
        "status": raw.get("status") or "",
        "error": raw.get("error") or "",
        "reqId": "",
        "reqName": "",
        "recipientName": "",
    }


def _normalize_pmwb_log(rec: EmailRecord) -> dict:
    """将 PMWB email_records 归一化为统一日志格式。"""
    created = rec.created_at
    sent_at = ""
    if created:
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        sent_at = created.astimezone(CST).strftime("%Y-%m-%d %H:%M:%S")
    raw_status = (rec.send_status or "").lower()
    status = "sent" if raw_status in ("success", "sent") else raw_status
    return {
        "id": f"pmwb_{rec.id}",
        "source": "pmwb",
        "sentAt": sent_at,
        "type": rec.email_type or "",
        "fromEmail": rec.sender or "",
        "to": rec.recipient or "",
        "cc": "",
        "subject": rec.subject or "",
        "body": rec.content or "",
        "bodyFormat": "text",
        "status": status,
        "error": rec.error_msg or "",
        "reqId": rec.req_id or "",
        "reqName": rec.req_name or "",
        "recipientName": rec.recipient_name or "",
    }


@router.get("/logs/merged")
def list_merged_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    log_type: str = Query(default=None),
    status: str = Query(default=None),
    search: str = Query(default=None),
    start_date: str = Query(default=None),
    end_date: str = Query(default=None),
    db: Session = Depends(get_db),
):
    """合并展示邮件中心 SendLog 和 PMWB email_records 的发送日志。

    策略：分别从两边拉取数据（各拉最多 500 条），统一字段后按时间倒序归并，
    再做内存分页。通过 source 字段区分来源。
    """
    # 1. 从邮件中心拉取日志
    mc_items: list[dict] = []
    mc_error: str = ""
    try:
        params: dict = {"page": 1, "pageSize": 500}
        if log_type:
            params["type"] = log_type
        if status:
            params["status"] = status
        if search:
            params["search"] = search
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        mc_resp = proxy.request("GET", "/api/logs", params=params)
        if isinstance(mc_resp, dict):
            mc_items = mc_resp.get("items") or mc_resp.get("data") or []
        elif isinstance(mc_resp, list):
            mc_items = mc_resp
    except Exception as exc:
        logger.warning("合并日志：拉取邮件中心日志失败: %s", exc)
        mc_error = str(exc)

    mc_normalized = [_normalize_mc_log(item) for item in mc_items if isinstance(item, dict)]

    # 2. 从 PMWB email_records 拉取
    pmwb_normalized: list[dict] = []
    try:
        q = db.query(EmailRecord)
        if status:
            if status == "sent":
                q = q.filter(EmailRecord.send_status.in_(["success", "sent"]))
            elif status == "failed":
                q = q.filter(EmailRecord.send_status == "failed")
        if log_type:
            q = q.filter(EmailRecord.email_type == log_type)
        if search:
            kw = f"%{search}%"
            q = q.filter(
                or_(
                    EmailRecord.subject.like(kw),
                    EmailRecord.recipient.like(kw),
                    EmailRecord.req_id.like(kw),
                    EmailRecord.req_name.like(kw),
                )
            )
        if start_date:
            try:
                sd = datetime.fromisoformat(start_date)
                q = q.filter(EmailRecord.created_at >= sd)
            except ValueError:
                pass
        if end_date:
            try:
                ed = datetime.fromisoformat(end_date)
                q = q.filter(EmailRecord.created_at <= ed)
            except ValueError:
                pass
        records = q.order_by(desc(EmailRecord.created_at)).limit(500).all()
        pmwb_normalized = [_normalize_pmwb_log(r) for r in records]
    except SQLAlchemyError as exc:
        logger.warning("合并日志：查询 email_records 失败: %s", exc)

    # 3. 合并 + 排序（按 sentAt 倒序）
    all_items = mc_normalized + pmwb_normalized
    all_items.sort(key=lambda x: x.get("sentAt") or "", reverse=True)

    # 4. 内存分页
    total = len(all_items)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_items = all_items[start_idx:end_idx]

    return success(data={
        "items": page_items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": (total + page_size - 1) // page_size if page_size > 0 else 0,
        "mcError": mc_error or None,
    })


@router.get("/logs/{log_id}")
def get_log(log_id: str):
    try:
        data = proxy.request("GET", f"/api/logs/{log_id}")
        return success(data=data)
    except Exception as exc:
        logger.warning("代理获取日志详情失败: %s", exc)
        return error(f"获取日志详情失败: {exc}", code=502)
