import logging

import httpx

from core.config import settings

logger = logging.getLogger("pmwb.email")


class EmailCenterClient:
    """统一邮件中心 HTTP 客户端。"""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.EMAIL_CENTER_URL
        self.client = httpx.Client(base_url=self.base_url, timeout=30.0)

    def send_email(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        template_id: str = None,
        template_data: dict = None,
        body_format: str = "text",
        cc: str | list[str] = None,
        email_type: str = None,
        attachments: list[dict] = None,
    ) -> dict:
        # 默认按纯文本(text/plain)发送：邮件客户端会忠实保留换行符，
        # 预览(textarea / white-space: pre-wrap)与收到邮件的段落排版完全一致。
        # 若改为 html，正文里的 \n 会被折叠成空格，导致"发出去变成一整段"。
        payload = {
            "to": to if isinstance(to, list) else [to],
            "subject": subject,
            "body": body,
            "bodyFormat": body_format,
        }
        if cc:
            payload["cc"] = cc if isinstance(cc, list) else [cc]
        if email_type:
            payload["type"] = email_type
        if attachments:
            payload["attachments"] = attachments
        if template_id:
            payload["template_id"] = template_id
        if template_data:
            payload["template_data"] = template_data

        response = self.client.post("/api/send", json=payload)
        response.raise_for_status()
        return response.json()

    def render_template(self, template_id: str, data: dict) -> dict:
        response = self.client.post(f"/api/templates/{template_id}/render", json=data)
        response.raise_for_status()
        return response.json()


    def search_contacts(self, keyword: str) -> list:
        """在统一邮件中心通讯录中搜索联系人（按姓名/邮箱/部门模糊匹配）。"""
        try:
            response = self.client.get(
                "/api/contacts",
                params={"search": keyword},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("items", []) if isinstance(data, dict) else []
        except Exception as exc:  # noqa: BLE001
            logger.warning("查询邮件中心通讯录失败: %s", exc)
            return []

    def resolve_contact_emails(self, names: list) -> dict:
        """按 SA 姓名列表解析真实邮箱，返回 {姓名: 邮箱|None}。

        通过邮件中心通讯录按姓名精确匹配；查不到或通讯录不可用时返回 None。
        """
        result: dict = {}
        for name in names or []:
            if not name:
                continue
            target = str(name).strip()
            result[target] = None
            items = self.search_contacts(target)
            for item in items:
                item_name = (item.get("name") or "").strip()
                email = (item.get("email") or "").strip()
                if item_name and item_name == target and email:
                    result[target] = email
                    break
        return result

    def health_check(self) -> dict:
        """检查统一邮件中心健康状态（对齐 email-manager 的 mailCenter.healthCheck）。"""
        try:
            response = self.client.get("/api/health", timeout=10.0)
            data = response.json() if response.content else None
            return {"ok": response.status_code == 200, "status": response.status_code, "detail": data}
        except Exception as exc:  # noqa: BLE001
            logger.warning("邮件中心健康检查失败: %s", exc)
            return {"ok": False, "error": str(exc)}


email_client = EmailCenterClient()
