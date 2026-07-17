"""插件接入 Service：承接原 2525 本地中继的能力，由 PMWB 统一托管。

原链路：Chrome 插件 → 2525(local-smtp-server) → 3210(统一邮件中心) / MySQL(sa_info, sent_emails)
新链路：Chrome 插件 → PMWB 后端(/api/v1/plugins/*) → 3210 / MySQL(yxtyg_db)

插件是原生 fetch 调用（不经过前端拦截器），因此这些端点返回**扁平 JSON**
（如 {"success": true, "messageId": ...}），不套用 core.response.success 的 code/data 包装。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import text
from sqlalchemy.orm import Session

from db.models import SaInfo, SentEmail
from utils.email import EmailCenterClient

# 与 2525 中继 ensureSaInfoTable 对齐（create_all 已建表，这里仅作兜底）
SA_INFO_DDL = """CREATE TABLE IF NOT EXISTS sa_info (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sa_name VARCHAR(255) NOT NULL COMMENT 'SA姓名',
    system_name VARCHAR(255) DEFAULT NULL COMMENT '系统名称',
    email VARCHAR(255) NOT NULL COMMENT '邮箱',
    wechat_nickname VARCHAR(255) DEFAULT NULL COMMENT '微信昵称',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_sa_system (sa_name, system_name),
    UNIQUE KEY uk_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='SA信息表'"""


class PluginService:
    """插件接入 Service。"""

    def __init__(self):
        self.email_client = EmailCenterClient()

    # ---------------- 统一邮件中心发信 ----------------
    def send_email(
        self,
        to: Union[str, List[str]],
        subject: str,
        body: str,
        cc: Union[str, List[str], None] = None,
        body_format: str = "text",
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """通过统一邮件中心发送邮件（对齐 2525 /send）。"""
        result = self.email_client.send_email(
            to=to,
            cc=cc,
            subject=subject,
            body=body,
            body_format=body_format,
            email_type="xqemail_plugin",
            attachments=attachments,
        )
        return {
            "success": True,
            "messageId": result.get("messageId", ""),
            "fromEmail": result.get("fromEmail", ""),
            "accountId": result.get("accountId", ""),
        }

    # ---------------- sent_emails 写入（数据接入）----------------
    def ingest(self, db: Session, raw: Dict[str, Any]) -> int:
        """写入一条 sent_emails 记录（对齐 2525 /write-db）。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = SentEmail(
            req_id=raw.get("reqId") or "",
            req_name=raw.get("reqName") or "",
            proposer=raw.get("proposer") or "",
            propose_time=raw.get("proposeTime") or "",
            is_involved=1,
            involve_dev=raw.get("involveDev") or "是",
            background=raw.get("background") or "",
            description=raw.get("description") or "",
            clarification=raw.get("clarification") or "",
            system_name=raw.get("system") or "",
            sa_name=raw.get("sa") or "",
            send_datetime=raw.get("sendDateTime") or now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id

    # ---------------- sa_info 收件人管理 ----------------
    def ensure_sa_info(self, db: Session):
        """兜底建表（生产/测试均已由 Base.metadata.create_all 建好，这里仅作安全网）。

        注意：DDL 含 MySQL 专有语法（ENGINE/CHARSET），在 SQLite 测试库会报错，
        因此 best-effort 吞掉异常——表已由 create_all 保证存在，无需因方言差异中断业务。
        """
        try:
            db.execute(text(SA_INFO_DDL))
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()

    def list_contacts(self, db: Session) -> List[Dict[str, Any]]:
        self.ensure_sa_info(db)
        rows = (
            db.query(SaInfo)
            .order_by(SaInfo.system_name, SaInfo.sa_name)
            .all()
        )
        return [
            {
                "name": r.sa_name or "",
                "email": r.email or "",
                "system": r.system_name or "",
                "wechatNickname": r.wechat_nickname or "",
            }
            for r in rows
            if r.email and "@" in r.email
        ]

    def check_duplicate(self, db: Session, sa_name: str, system_name: str) -> bool:
        self.ensure_sa_info(db)
        return (
            db.query(SaInfo)
            .filter(SaInfo.sa_name == sa_name, SaInfo.system_name == system_name)
            .first()
            is not None
        )

    def add_contact(self, db: Session, sa_name: str, system_name: str,
                    email: str, wechat_nickname: str = "") -> int:
        self.ensure_sa_info(db)
        dup = (
            db.query(SaInfo)
            .filter(
                ((SaInfo.sa_name == sa_name) & (SaInfo.system_name == system_name))
                | (SaInfo.email == email)
            )
            .first()
        )
        if dup:
            raise ValueError("同一系统下已存在该姓名，或该邮箱已被使用")
        obj = SaInfo(
            sa_name=sa_name,
            system_name=system_name or None,
            email=email,
            wechat_nickname=wechat_nickname or None,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj.id

    def update_contact(self, db: Session, old_name: str, old_system: str, old_email: str,
                       sa_name: str, system_name: str, email: str,
                       wechat_nickname: str = "") -> int:
        self.ensure_sa_info(db)
        obj = (
            db.query(SaInfo)
            .filter(
                SaInfo.sa_name == old_name,
                SaInfo.system_name == old_system,
                SaInfo.email == old_email,
            )
            .first()
        )
        if not obj:
            raise ValueError("未找到匹配的收件人记录")
        dup = (
            db.query(SaInfo)
            .filter(
                (SaInfo.sa_name == sa_name) & (SaInfo.system_name == system_name)
                & ~(
                    (SaInfo.sa_name == old_name)
                    & (SaInfo.system_name == old_system)
                    & (SaInfo.email == old_email)
                )
            )
            .first()
        )
        if dup:
            raise ValueError("同一系统下已存在该姓名")
        obj.sa_name = sa_name
        obj.system_name = system_name or None
        obj.email = email
        obj.wechat_nickname = wechat_nickname or None
        db.commit()
        return 1

    def delete_contact(self, db: Session, sa_name: str, system_name: str, email: str) -> int:
        self.ensure_sa_info(db)
        n = (
            db.query(SaInfo)
            .filter(
                SaInfo.sa_name == sa_name,
                SaInfo.system_name == system_name,
                SaInfo.email == email,
            )
            .delete()
        )
        db.commit()
        return n


plugin_service = PluginService()
