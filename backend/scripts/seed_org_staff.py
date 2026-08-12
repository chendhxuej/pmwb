# -*- coding: utf-8 -*-
"""基础数据 seed：组织 + 人员主数据一次性导入。

数据来源（按优先级合并，姓名+组织去重，幂等可重复执行）：
1. 组织分工表（原 frontend/src/constants/staff.js 的 HANDLER_GROUPS）
2. services/requirement_delivery.PROPOSER_DEPT_MAP（补充未覆盖的人）
3. sa_info 表（按姓名补 email，不新建人员）

用法：cd backend && venv/Scripts/python.exe scripts/seed_org_staff.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.base import SessionLocal  # noqa: E402
from db.models import PmwbOrg, PmwbStaff, SaInfo  # noqa: E402

# 组织分工表（组织顺序即 sort 顺序）
ORG_GROUPS = [
    ("政企客户部", ["邵建", "顾宏明", "张舒明", "张振", "戴燕", "黄何", "金韡", "李能禾", "方舟", "秦新"]),
    ("CRM", ["郑文东", "吴雨霜", "张茜"]),
    ("BOSS", ["陈增明", "叶振宇", "李蕊"]),
    ("订单中心", ["王辅松", "陈山"]),
    ("生产运营平台", ["戴晓飞"]),
    ("系统维护(CRM)", ["毛天羿", "陈靖坤", "王宏伟", "李培龙"]),
    ("系统维护(BOSS)", ["凌玉祥", "吕凤云"]),
    ("系统维护(订单)", ["孟华"]),
    ("系统维护(生产运营)", ["李瑞"]),
]

# 组织 -> 默认身份
ORG_ROLE_HINTS = {
    "政企客户部": "产品经理",
    "CRM": "业务维护",
    "BOSS": "业务维护",
    "订单中心": "业务维护",
    "生产运营平台": "业务维护",
    "系统维护(CRM)": "系统维护",
    "系统维护(BOSS)": "系统维护",
    "系统维护(订单)": "系统维护",
    "系统维护(生产运营)": "系统维护",
}

def default_role_hint(org_name: str) -> str:
    return ORG_ROLE_HINTS.get(org_name, "业务维护")


def main():
    db = SessionLocal()
    created_orgs = created_staffs = filled_emails = 0
    try:
        # 1) 组织 + 人员（幂等：存在则跳过）
        orgs = {}
        for idx, (org_name, members) in enumerate(ORG_GROUPS):
            org = db.query(PmwbOrg).filter(PmwbOrg.name == org_name).first()
            if not org:
                org = PmwbOrg(name=org_name, sort=idx * 10, enabled=True)
                db.add(org)
                db.flush()
                created_orgs += 1
            orgs[org_name] = org
            existing = {s.name for s in db.query(PmwbStaff).filter(PmwbStaff.org_id == org.id).all()}
            for midx, name in enumerate(members):
                if name in existing:
                    continue
                db.add(
                    PmwbStaff(
                        name=name,
                        org_id=org.id,
                        sort=midx * 10,
                        enabled=True,
                        role_hint=default_role_hint(org_name),
                    )
                )
                created_staffs += 1
        db.flush()

        # 2) PROPOSER_DEPT_MAP 补充未覆盖的人（组织不存在则新建）
        try:
            from services.requirement_delivery import PROPOSER_DEPT_MAP
        except Exception:
            PROPOSER_DEPT_MAP = {}
        all_names = {s.name for s in db.query(PmwbStaff).all()}
        for name, dept in PROPOSER_DEPT_MAP.items():
            if name in all_names:
                continue
            org = orgs.get(dept) or db.query(PmwbOrg).filter(PmwbOrg.name == dept).first()
            if not org:
                org = PmwbOrg(name=dept, sort=900, enabled=True)
                db.add(org)
                db.flush()
                orgs[dept] = org
                created_orgs += 1
            db.add(
                PmwbStaff(
                    name=name,
                    org_id=org.id,
                    sort=500,
                    enabled=True,
                    role_hint=default_role_hint(dept),
                )
            )
            all_names.add(name)
            created_staffs += 1
        db.flush()

        # 3) sa_info 补 email（同名多条取第一条非空邮箱；不覆盖已有邮箱）
        email_map = {}
        for row in db.query(SaInfo).order_by(SaInfo.id).all():
            if row.sa_name and row.email and row.sa_name not in email_map:
                email_map[row.sa_name] = row.email
        for staff in db.query(PmwbStaff).all():
            if not staff.email and staff.name in email_map:
                staff.email = email_map[staff.name]
                filled_emails += 1

        # 4) 现有人员的身份字段兜底回填（幂等）
        filled_roles = 0
        for staff in db.query(PmwbStaff).all():
            if not staff.role_hint and staff.org:
                staff.role_hint = default_role_hint(staff.org.name)
                filled_roles += 1

        db.commit()
        print(
            f"seed done: orgs+{created_orgs}, staffs+{created_staffs}, "
            f"roles filled {filled_roles}, emails filled {filled_emails}"
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"seed failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
