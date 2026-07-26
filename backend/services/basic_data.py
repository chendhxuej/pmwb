"""基础数据 Service：组织 + 人员 CRUD 与选人选项。"""
from __future__ import annotations

import io
from collections import defaultdict
from typing import Dict, List, Optional

from openpyxl import Workbook, load_workbook
from sqlalchemy.orm import Session

from db.models import PmwbOrg, PmwbStaff


# Excel 导入列名与顺序
TEMPLATE_COLUMNS = [
    ("组织名称", True),
    ("成员姓名", True),
    ("邮箱", False),
    ("电话", False),
    ("身份", False),
    ("排序号", False),
    ("是否启用", False),
]


def _cell_str(value) -> str:
    """把 openpyxl 单元格值转字符串；空值/None 返回空字符串。"""
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    return str(value).strip()


def _parse_enabled(value):
    """把文本/数字解析为布尔值。"""
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in ("1", "true", "是", "yes", "y", "启用"):
        return True
    if s in ("0", "false", "否", "no", "n", "停用", "禁用"):
        return False
    return True


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
    # 批量导入
    # ------------------------------------------------------------------
    def import_orgs_staffs(self, db: Session, rows: List[dict]) -> dict:
        """从 Excel 解析后的行批量 upsert 组织与人员。

        rows 每项为 dict，至少含 org_name；若含 name 则 upsert 成员。
        返回统计信息及错误列表。
        """
        stats = {
            "created_orgs": 0,
            "updated_orgs": 0,
            "created_staffs": 0,
            "updated_staffs": 0,
            "errors": [],
        }

        # 1. 按组织名称聚类
        org_rows: Dict[str, List[dict]] = defaultdict(list)
        for idx, row in enumerate(rows, start=2):
            org_name = _cell_str(row.get("组织名称", ""))
            if not org_name:
                stats["errors"].append(f"第 {idx} 行：组织名称不能为空")
                continue
            org_rows[org_name].append({"idx": idx, "row": row})

        # 2. 组织 upsert
        org_cache: Dict[str, PmwbOrg] = {}
        for org_name, entries in org_rows.items():
            representative = entries[0]["row"]
            org = db.query(PmwbOrg).filter(PmwbOrg.name == org_name).first()
            sort = int(_cell_str(representative.get("排序号", "")) or 0)
            enabled = _parse_enabled(representative.get("是否启用", True))
            if org:
                org.sort = sort
                org.enabled = enabled
                stats["updated_orgs"] += 1
            else:
                org = PmwbOrg(
                    name=org_name,
                    sort=sort,
                    enabled=enabled,
                )
                db.add(org)
                db.flush()
                stats["created_orgs"] += 1
            org_cache[org_name] = org

        # 3. 人员 upsert
        for org_name, entries in org_rows.items():
            org = org_cache[org_name]
            for item in entries:
                idx = item["idx"]
                row = item["row"]
                name = _cell_str(row.get("成员姓名", ""))
                if not name:
                    # 只有组织没有成员，不报错
                    continue

                email = _cell_str(row.get("邮箱", "")) or None
                phone = _cell_str(row.get("电话", "")) or None
                role_hint = _cell_str(row.get("身份", "")) or None
                sort = int(_cell_str(row.get("排序号", "")) or 0)
                enabled = _parse_enabled(row.get("是否启用", True))

                staff = (
                    db.query(PmwbStaff)
                    .filter(PmwbStaff.name == name, PmwbStaff.org_id == org.id)
                    .first()
                )
                if staff:
                    staff.email = email
                    staff.phone = phone
                    staff.role_hint = role_hint
                    staff.sort = sort
                    staff.enabled = enabled
                    stats["updated_staffs"] += 1
                else:
                    staff = PmwbStaff(
                        name=name,
                        org_id=org.id,
                        email=email,
                        phone=phone,
                        role_hint=role_hint,
                        sort=sort,
                        enabled=enabled,
                    )
                    db.add(staff)
                    stats["created_staffs"] += 1

        db.commit()
        return stats

    def build_template_bytes(self) -> bytes:
        """生成 Excel 导入模板字节流。"""
        wb = Workbook()
        ws = wb.active
        ws.title = "团队信息导入"

        headers = [c[0] for c in TEMPLATE_COLUMNS]
        ws.append(headers)

        # 示例数据
        ws.append(["政企业务部", "张三", "zhangsan@example.com", "13800138000", "产品经理", 0, "是"])
        ws.append(["CRM维护", "李四", "lisi@example.com", "", "系统维护", 1, "是"])
        ws.append(["BOSS维护", "", "", "", "", "", ""])

        # 必填列加批注
        for col_idx, (name, required) in enumerate(TEMPLATE_COLUMNS, start=1):
            cell = ws.cell(row=1, column=col_idx)
            if required:
                cell.comment = None
            # 自适应列宽
            ws.column_dimensions[cell.column_letter].width = max(14, len(name) + 4)

        bio = io.BytesIO()
        wb.save(bio)
        bio.seek(0)
        return bio.getvalue()

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
