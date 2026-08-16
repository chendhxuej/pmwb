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
from services.mail_dispatch import dispatch_email
from utils.master_service import master_service_client

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
        """通过统一邮件治理门面发送邮件（插件原始契约扁平 JSON 保持兼容）。"""
        result = dispatch_email(
            to=to,
            cc=cc,
            subject=subject,
            scene="plugin",
            raw_content=body,
            html_passthrough=body_format == "html",
            body_format="html",
            attachments=attachments,
            raise_on_error=True,
        )
        return {
            "success": result.get("success", False),
            "message": result.get("message", ""),
            "messageId": result.get("message_id") or result.get("record_id"),
            "fromEmail": "",
            "accountId": "",
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

    def sync_from_master(self, db: Session) -> Dict[str, Any]:
        """从人员中台(8001)拉取 role=SA 的人员，upsert 进 sa_info 收件人表。

        以 (姓名,系统) 或 邮箱 匹配：已存在则更新邮箱/系统，不存在则新建。
        系统(system_name) 取人员中台的 org_name。
        """
        self.ensure_sa_info(db)
        sa_staffs = master_service_client.list_sa_staffs()
        if not sa_staffs:
            return {"created": 0, "updated": 0, "skipped": 0, "errors": ["人员中台无 SA 人员"]}
        created = updated = skipped = 0
        errors: List[str] = []
        for s in sa_staffs:
            name = (s.get("name") or "").strip()
            email = (s.get("email") or "").strip()
            org = (s.get("org_name") or "").strip()
            if not name or not email:
                continue
            try:
                existing = (
                    db.query(SaInfo)
                    .filter(
                        ((SaInfo.sa_name == name) & (SaInfo.system_name == (org or None)))
                        | (SaInfo.email == email)
                    )
                    .first()
                )
                if existing:
                    changed = False
                    if existing.email != email:
                        existing.email = email
                        changed = True
                    if org and existing.system_name != org:
                        existing.system_name = org
                        changed = True
                    if changed:
                        db.commit()
                        updated += 1
                    else:
                        skipped += 1
                else:
                    db.add(SaInfo(
                        sa_name=name,
                        system_name=org or None,
                        email=email,
                        wechat_nickname="",
                    ))
                    db.commit()
                    created += 1
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                errors.append(f"{name}: {exc}")
                skipped += 1
        return {"created": created, "updated": updated, "skipped": skipped, "errors": errors}


plugin_service = PluginService()
