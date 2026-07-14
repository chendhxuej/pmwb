from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from db.models import EmailRecord
from schemas.reminder import ReminderSendRequest
from utils.email import EmailCenterClient


class ReminderService:
    """统一邮件催办 Service。"""

    def __init__(self):
        self.email_client = EmailCenterClient()

    def send_reminder(self, db: Session, obj_in: ReminderSendRequest) -> Dict[str, Any]:
        """发送催办邮件并记录到 email_records。"""
        record = EmailRecord(
            req_id=obj_in.req_id,
            req_name=obj_in.req_name,
            email_type=obj_in.template_id or "pmwb_reminder",
            recipient=obj_in.to,
            recipient_name=None,
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
