"""基础数据 Service：组织 + 人员 CRUD 与选人选项。

现在代理到 pmwb-master-service（HTTP API），前端/router 接口不变。
"""
from __future__ import annotations

import io
from typing import Dict, List, Optional

from openpyxl import Workbook
from sqlalchemy.orm import Session

from utils.master_service import master_service_client

# Excel 导入列名与顺序（保留用于模板生成）
TEMPLATE_COLUMNS = [
    ("组织名称", True),
    ("成员姓名", True),
    ("邮箱", False),
    ("电话", False),
    ("身份", False),
    ("排序号", False),
    ("是否启用", False),
]


class BasicDataService:
    """组织+人员主数据服务（代理到人员中台）。"""

    # ------------------------------------------------------------------
    # 组织
    # ------------------------------------------------------------------
    def list_orgs(self, db: Session = None, include_disabled: bool = True) -> List[dict]:
        orgs = master_service_client.list_orgs()
        if not include_disabled:
            orgs = [o for o in orgs if o.get("enabled", True)]
        return sorted(orgs, key=lambda o: (o.get("sort", 0), o.get("id", 0)))

    def create_org(self, db: Session, data: dict) -> Optional[dict]:
        return master_service_client.create_org(data)

    def update_org(self, db: Session, org_id: int, data: dict) -> Optional[dict]:
        return master_service_client.update_org(org_id, data)

    def delete_org(self, db: Session, org_id: int) -> bool:
        return master_service_client.delete_org(org_id)

    # ------------------------------------------------------------------
    # 角色/身份定义
    # ------------------------------------------------------------------
    def list_roles(self, db: Session = None, include_disabled: bool = True) -> List[dict]:
        roles = master_service_client.list_roles()
        if not include_disabled:
            roles = [r for r in roles if r.get("enabled", True)]
        return sorted(roles, key=lambda r: (r.get("sort", 0), r.get("id", 0)))

    def create_role(self, db: Session, data: dict) -> Optional[dict]:
        return master_service_client.create_role(data)

    def update_role(self, db: Session, role_id: int, data: dict) -> Optional[dict]:
        return master_service_client.update_role(role_id, data)

    def delete_role(self, db: Session, role_id: int) -> bool:
        return master_service_client.delete_role(role_id)

    # ------------------------------------------------------------------
    # 轻量选项（选人组件下拉用）
    # ------------------------------------------------------------------
    def org_options(self, db: Session = None) -> List[dict]:
        """返回启用的组织名称列表（轻量，不加载人员明细）。"""
        return master_service_client.org_options()

    def role_options(self, db: Session = None) -> List[dict]:
        """返回启用的身份名称列表（轻量，不加载人员明细）。"""
        return master_service_client.role_options()

    # ------------------------------------------------------------------
    # 人员
    # ------------------------------------------------------------------
    def list_staffs(
        self,
        db: Session = None,
        org_id: Optional[int] = None,
        keyword: Optional[str] = None,
        include_disabled: bool = True,
    ) -> List[dict]:
        staffs = master_service_client.list_staffs(org_id=org_id, keyword=keyword)
        if not include_disabled:
            staffs = [s for s in staffs if s.get("enabled", True)]
        return staffs

    def create_staff(self, db: Session, data: dict) -> Optional[dict]:
        return master_service_client.create_staff(data)

    def update_staff(self, db: Session, staff_id: int, data: dict) -> Optional[dict]:
        return master_service_client.update_staff(staff_id, data)

    def delete_staff(self, db: Session, staff_id: int) -> bool:
        return master_service_client.delete_staff(staff_id)

    # ------------------------------------------------------------------
    # 选人组件
    # ------------------------------------------------------------------
    def staff_options(self, db: Session = None) -> List[dict]:
        return master_service_client.staff_options()

    # ------------------------------------------------------------------
    # 批量导入（文件上传到 master 服务）
    # ------------------------------------------------------------------
    def import_orgs_staffs(self, db: Session, rows: List[dict]) -> dict:
        """Excel 行数据导入：由 PMWB router 处理后调用文件上传。"""
        # 由于 master 服务接收文件，这里返回空结果，实际由 router 处理
        return {
            "created_orgs": 0,
            "updated_orgs": 0,
            "created_staffs": 0,
            "updated_staffs": 0,
            "errors": [],
        }

    def upload_and_import(self, file_content: bytes, filename: str) -> dict:
        """上传 Excel 文件到 master 服务并导入。"""
        result = master_service_client.upload_import_file(file_content, filename)
        if result["ok"]:
            data = result["data"] or {}
            return {
                "created_orgs": data.get("created_orgs", 0),
                "updated_orgs": data.get("updated_orgs", 0),
                "created_staffs": data.get("created_staffs", 0),
                "updated_staffs": data.get("updated_staffs", 0),
                "errors": data.get("errors", []),
            }
        return {
            "created_orgs": 0,
            "updated_orgs": 0,
            "created_staffs": 0,
            "updated_staffs": 0,
            "errors": [result.get("error", "导入失败")],
        }

    def build_template_bytes(self) -> bytes:
        """生成 Excel 导入模板字节流（本地生成，不调 master）。"""
        wb = Workbook()
        ws = wb.active
        ws.title = "团队信息导入"

        headers = [c[0] for c in TEMPLATE_COLUMNS]
        ws.append(headers)
        ws.append(["政企业务部", "张三", "zhangsan@example.com", "13800138000", "产品经理", 0, "是"])
        ws.append(["CRM维护", "李四", "lisi@example.com", "", "系统维护", 1, "是"])
        ws.append(["BOSS维护", "", "", "", "", "", ""])

        for col_idx, (name, _required) in enumerate(TEMPLATE_COLUMNS, start=1):
            cell = ws.cell(row=1, column=col_idx)
            ws.column_dimensions[cell.column_letter].width = max(14, len(name) + 4)

        bio = io.BytesIO()
        wb.save(bio)
        bio.seek(0)
        return bio.getvalue()

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------
    def dept_of(self, db: Session = None, name: str = "") -> Optional[str]:
        """按姓名查找所属组织名称。"""
        if not name:
            return None
        staffs = master_service_client.list_staffs(keyword=name)
        for s in staffs:
            if s.get("name") == name and s.get("enabled", True):
                return s.get("org_name")
        return None


basic_data_service = BasicDataService()
