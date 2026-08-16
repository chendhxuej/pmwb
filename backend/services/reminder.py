from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.exceptions import ValidationException
from db.models import EmailRecord
from schemas.reminder import ReminderSendRequest
from services.mail_dispatch import dispatch_email
from utils.master_service import master_service_client
from utils.validators import split_and_validate_emails


class ReminderService:
    """统一邮件催办 Service。"""

    def resolve_contacts(self, names: List[str]) -> Dict[str, Optional[str]]:
        """按姓名解析收件人邮箱：优先人员中台(8001)，邮件中心通讯录兜底。

        之前只查邮件中心旧通讯录，导致邮箱与人员中台不一致。
        现改为以人员中台为唯一权威来源，邮件中心仅作查不到时的兜底。
        """
        result = master_service_client.resolve_staff_emails(names)
        missing = [n for n, e in result.items() if not e]
        if missing:
            from utils.email import EmailCenterClient

            fallback = EmailCenterClient().resolve_contact_emails(missing)
            for n in missing:
                if fallback.get(n):
                    result[n] = fallback[n]
        return result

    def send_reminder(self, db: Session, obj_in: ReminderSendRequest) -> Dict[str, Any]:
        """发送催办邮件并记录到 email_records。"""
        # 发送前严格校验收件人/抄送邮箱，避免非法地址（如 中文名@chinamobile.com）
        # 被邮件中心以 500 拒绝；改为清晰的 400 提示。
        bad_addresses: List[str] = []
        _, invalid_to = split_and_validate_emails(obj_in.to or "")
        bad_addresses.extend(invalid_to)
        if obj_in.cc:
            _, invalid_cc = split_and_validate_emails(obj_in.cc)
            bad_addresses.extend(invalid_cc)
        if bad_addresses:
            raise ValidationException(
                "收件人邮箱格式不正确："
                + "、".join(bad_addresses)
                + "。请填写真实邮箱（可在统一邮件中心通讯录按姓名查询）。"
            )

        # 统一走邮件治理门面：统一渲染、签名、落库、发信
        result = dispatch_email(
            db=db,
            to=obj_in.to,
            cc=obj_in.cc,
            subject=obj_in.subject,
            scene="requirement_reminder",
            raw_content=obj_in.body,
            req_id=obj_in.req_id,
            req_name=obj_in.req_name,
            recipient_name=obj_in.recipient_name,
            raise_on_error=False,
        )
        return result

    def list_by_req_id(self, db: Session, req_id: str) -> List[EmailRecord]:
        """按需求编号查询催办记录。"""
        return (
            db.query(EmailRecord)
            .filter(EmailRecord.req_id == req_id)
            .order_by(EmailRecord.created_at.desc())
            .all()
        )

    def list_all(self, db: Session, limit: int = 50) -> List[EmailRecord]:
        """全局邮件发送记录（最近 limit 条，倒序）。"""
        return (
            db.query(EmailRecord)
            .order_by(EmailRecord.created_at.desc())
            .limit(max(1, min(limit, 200)))
            .all()
        )


reminder_service = ReminderService()
