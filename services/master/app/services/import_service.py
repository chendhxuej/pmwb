"""联系人数据导入服务：合并邮件中心通讯录 + PMWB sa_info 到人员中台。

策略：一次性导入 + 可重复执行（幂等）。
去重规则：邮箱非空以邮箱为主键，邮箱为空以 name+org_id 为主键。
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from db.models import PmwbOrg, PmwbStaff

logger = logging.getLogger(__name__)


class ContactImportService:
    """将外部通讯录数据合并导入到 PmwbStaff/PmwbOrg。"""

    # ------------------------------------------------------------------
    # 邮件中心通讯录导入
    # ------------------------------------------------------------------
    def import_email_center_contacts(
        self,
        db: Session,
        contacts: List[dict],  # [{"name":..., "email":..., "group":..., "department":..., "contact_id":...}]
    ) -> dict:
        """从邮件中心 JSON 数据导入。"""
        stats = {
            "created_orgs": 0,
            "created_staffs": 0,
            "updated_staffs": 0,
            "conflicts": 0,
            "errors": [],
        }

        # 1. 收集所有组并创建组织
        org_cache: Dict[str, PmwbOrg] = {}
        unique_groups = set()
        for c in contacts:
            group = (c.get("group") or c.get("department") or "外部联系人").strip()
            unique_groups.add(group)

        for group in unique_groups:
            org = db.query(PmwbOrg).filter(PmwbOrg.name == group).first()
            if not org:
                org = PmwbOrg(name=group, source_trace="email_center")
                db.add(org)
                db.flush()
                stats["created_orgs"] += 1
            org_cache[group] = org

        # 2. 导入人员
        for c in contacts:
            name = (c.get("name") or "").strip()
            email = (c.get("email") or "").strip() or None
            group = (c.get("group") or c.get("department") or "外部联系人").strip()
            contact_id = str(c.get("contact_id", c.get("id", "")))

            if not name:
                stats["errors"].append(f"邮件中心联系人无姓名：{c}")
                continue

            org = org_cache.get(group)
            if not org:
                stats["errors"].append(f"组织 {group} 未找到（异常）")
                continue

            # 邮箱唯一匹配
            existing = None
            if email:
                existing = db.query(PmwbStaff).filter(PmwbStaff.email == email).first()

            if existing:
                # 更新数据
                existing.name = name
                existing.email = email
                existing.org_id = org.id
                existing.source_trace = "email_center"
                existing.legacy_id = contact_id
                existing.enabled = True
                stats["updated_staffs"] += 1
            else:
                # 按 name+org 查找
                dup = (
                    db.query(PmwbStaff)
                    .filter(PmwbStaff.name == name, PmwbStaff.org_id == org.id)
                    .first()
                )
                if dup:
                    dup.email = email
                    dup.source_trace = "email_center"
                    dup.legacy_id = contact_id
                    dup.enabled = True
                    stats["updated_staffs"] += 1
                else:
                    staff = PmwbStaff(
                        name=name,
                        org_id=org.id,
                        email=email,
                        source_trace="email_center",
                        legacy_id=contact_id,
                    )
                    db.add(staff)
                    stats["created_staffs"] += 1

        db.commit()
        logger.info(
            "邮件中心导入完成: orgs=%d/%d staffs=%d/%d conflicts=%d",
            stats["created_orgs"], 0,
            stats["created_staffs"], stats["updated_staffs"],
            stats["conflicts"],
        )
        return stats

    # ------------------------------------------------------------------
    # PMWB sa_info 导入
    # ------------------------------------------------------------------
    def import_sa_info(
        self,
        db: Session,
        sa_rows: List[dict],  # [{"sa_name":..., "system_name":...}]
    ) -> dict:
        """从 PMWB sa_info 表导入。"""
        stats = {
            "created_orgs": 0,
            "created_staffs": 0,
            "updated_staffs": 0,
            "conflicts": 0,
            "errors": [],
        }

        # sa_info 的人员归入 "SA信息" 组织（或按 system_name 分组）
        default_org = db.query(PmwbOrg).filter(PmwbOrg.name == "SA信息").first()
        if not default_org:
            default_org = PmwbOrg(name="SA信息", source_trace="sa_info")
            db.add(default_org)
            db.flush()
            stats["created_orgs"] += 1

        for row in sa_rows:
            name = (row.get("sa_name") or "").strip()
            system_name = (row.get("system_name") or "").strip()

            if not name:
                continue

            # 如果 system_name 不同，尝试用 system_name 作 role_hint
            role = system_name if system_name else None

            existing = (
                db.query(PmwbStaff)
                .filter(PmwbStaff.name == name, PmwbStaff.org_id == default_org.id)
                .first()
            )
            if existing:
                if role and not existing.role_hint:
                    existing.role_hint = role
                existing.source_trace = "sa_info"
                existing.enabled = True
                stats["updated_staffs"] += 1
            else:
                staff = PmwbStaff(
                    name=name,
                    org_id=default_org.id,
                    role_hint=role,
                    source_trace="sa_info",
                )
                db.add(staff)
                stats["created_staffs"] += 1

        db.commit()
        logger.info(
            "SA信息导入完成: staffs=%d/%d",
            stats["created_staffs"], stats["updated_staffs"],
        )
        return stats


contact_import_service = ContactImportService()
