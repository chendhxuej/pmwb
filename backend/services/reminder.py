from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.exceptions import ValidationException
from db.models import EmailRecord
from schemas.reminder import ReminderSendRequest
from utils.email import EmailCenterClient
from utils.validators import split_and_validate_emails


class ReminderService:
    """统一邮件催办 Service。"""

    def __init__(self):
        self.email_client = EmailCenterClient()

    def resolve_contacts(self, names: List[str]) -> Dict[str, Optional[str]]:
        """按 SA 姓名列表解析真实邮箱（委托统一邮件中心通讯录）。"""
        return self.email_client.resolve_contact_emails(names)

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

        record = EmailRecord(
            req_id=obj_in.req_id,
            req_name=obj_in.req_name,
            email_type=obj_in.template_id or "pmwb_reminder",
            recipient=obj_in.to,
            recipient_name=obj_in.recipient_name,
            subject=obj_in.subject,
            content=obj_in.body,
            send_status="pending",
            source="pmwb",
            sender=obj_in.operator or "pmwb",
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        try:
            result = self.email_client.send_email(
                to=obj_in.to,
                subject=obj_in.subject,
                body=obj_in.body,
                template_id=obj_in.template_id,
                template_data=obj_in.template_data,
            )
            record.send_status = "success"
            record.error_msg = str(result) if result else None
            message = "邮件发送成功"
            success = True
        except Exception as exc:
            record.send_status = "failed"
            record.error_msg = str(exc)
            message = f"邮件发送失败：{exc}"
            success = False

        db.commit()
        db.refresh(record)
        return {
            "success": success,
            "record_id": record.id,
            "message": message,
        }

    def list_by_req_id(self, db: Session, req_id: str) -> List[EmailRecord]:
        """按需求编号查询催办记录。"""
        return (
            db.query(EmailRecord)
            .filter(EmailRecord.req_id == req_id)
            .order_by(EmailRecord.created_at.desc())
            .all()
        )


reminder_service = ReminderService()
