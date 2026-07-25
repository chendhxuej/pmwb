"""基础数据 Service：组织 + 人员 CRUD 与选人选项。"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from db.models import PmwbOrg, PmwbStaff


class BasicDataService:
    """组织+人员主数据服务。"""

    # ------------------------------------------------------------------
    # 组织
    # ------------------------------------------------------------------
    def list_orgs(self, db: Session, include_disabled: bool = True) -> List[PmwbOrg]:
        query = db.query(PmwbOrg)
        if not include_disabled:
            query = query.filter(PmwbOrg.enabled.is_(True))
        return query.order_by(PmwbOrg.sort, PmwbOrg.id).all()

    def create_org(self, db: Session, data: dict) -> PmwbOrg:
        obj = PmwbOrg(**data)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def update_org(self, db: Session, org_id: int, data: dict) -> Optional[PmwbOrg]:
        obj = db.get(PmwbOrg, org_id)
        if not obj:
            return None
        for k, v in data.items():
            setattr(obj, k, v)
        db.commit()
        db.refresh(obj)
        return obj

    def delete_org(self, db: Session, org_id: int) -> bool:
        obj = db.get(PmwbOrg, org_id)
        if not obj:
            return False
        db.delete(obj)  # cascade 删除组织下人员
        db.commit()
        return True

    # ------------------------------------------------------------------
    # 人员
    # ------------------------------------------------------------------
    def list_staffs(
        self,
        db: Session,
        org_id: Optional[int] = None,
        keyword: Optional[str] = None,
        include_disabled: bool = True,
    ) -> List[PmwbStaff]:
        query = db.query(PmwbStaff)
        if org_id:
            query = query.filter(PmwbStaff.org_id == org_id)
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(
                PmwbStaff.name.like(like)
                | PmwbStaff.email.like(like)
                | PmwbStaff.role_hint.like(like)
            )
        if not include_disabled:
            query = query.filter(PmwbStaff.enabled.is_(True))
        return query.order_by(PmwbStaff.org_id, PmwbStaff.sort, PmwbStaff.id).all()

    def create_staff(self, db: Session, data: dict) -> PmwbStaff:
        obj = PmwbStaff(**data)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def update_staff(self, db: Session, staff_id: int, data: dict) -> Optional[PmwbStaff]:
        obj = db.get(PmwbStaff, staff_id)
        if not obj:
            return None
        for k, v in data.items():
            setattr(obj, k, v)
        db.commit()
        db.refresh(obj)
        return obj

    def delete_staff(self, db: Session, staff_id: int) -> bool:
        obj = db.get(PmwbStaff, staff_id)
        if not obj:
            return False
        db.delete(obj)
        db.commit()
        return True

    # ------------------------------------------------------------------
    # 选人组件：按组织分组的全量选项（只含启用项）
    # ------------------------------------------------------------------
    def staff_options(self, db: Session) -> List[dict]:
        orgs = (
            db.query(PmwbOrg)
            .filter(PmwbOrg.enabled.is_(True))
            .order_by(PmwbOrg.sort, PmwbOrg.id)
            .all()
        )
        groups = []
        for org in orgs:
            options = [
                {
                    "value": s.name,
                    "label": s.name,
                    "email": s.email,
                    "role_hint": s.role_hint,
                }
                for s in sorted(org.staffs, key=lambda x: ((x.sort or 0), x.id))
                if s.enabled
            ]
            if options:
                groups.append({"org_id": org.id, "org_name": org.name, "options": options})
        return groups

    # ------------------------------------------------------------------
    # 姓名 → 部门（供文档生成等后端逻辑复用）
    # ------------------------------------------------------------------
    def dept_of(self, db: Session, name: str) -> Optional[str]:
        if not name:
            return None
        staff = (
            db.query(PmwbStaff)
            .filter(PmwbStaff.name == name, PmwbStaff.enabled.is_(True))
            .order_by(PmwbStaff.id)
            .first()
        )
        return staff.org.name if staff and staff.org else None


basic_data_service = BasicDataService()
