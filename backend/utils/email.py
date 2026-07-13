import httpx

from core.config import settings


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
    ) -> dict:
        payload = {
            "to": to if isinstance(to, list) else [to],
            "subject": subject,
            "body": body,
        }
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


email_client = EmailCenterClient()
