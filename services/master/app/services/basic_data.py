"""人员主数据服务：组织 + 人员 CRUD、选人选项、批量导入。"""
from __future__ import annotations

import io
from collections import defaultdict
from typing import Dict, List, Optional

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from sqlalchemy.orm import Session

from core.exceptions import ValidationException
from db.models import PmwbOrg, PmwbRole, PmwbStaff

# Excel 导入模板列定义
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


# 组织类型取值域（系统别名映射的唯一真相源；数据归属本服务，主后端须经
# GET /basic-data/org-type-options 拉取，禁本地硬编码第二份）
#   system     = 真实系统，参与厂家映射与厂家清单
#   department = 部门（默认，保守：不填绝不会误进厂家清单）
#   branch     = 地市/分公司
ORG_TYPES = ("system", "department", "branch")
DEFAULT_ORG_TYPE = "department"


def _norm(value) -> str:
    """去首尾空白（含全角空格）后返回字符串；None 返回空串。"""
    if value is None:
        return ""
    return str(value).replace("\u3000", " ").strip()


def clean_aliases(raw, exclude_names=()) -> str:
    """别名清洗：拆逗号 → 去空项 → 去重（忽略大小写）→ 剔除与自身名/目标名相同的项。

    边界处理：
      · None / 空串 → ""
      · 连续逗号 "a,,b" → "a,b"（空项丢弃）
      · 大小写不同视为同一别名（保留首次出现的写法）
      · 与 exclude_names 相同的项剔除（避免与「组织名精确匹配」产生优先级歧义）
    """
    if not raw:
        return ""
    excluded = {_norm(n).lower() for n in exclude_names if _norm(n)}
    seen = set()
    out = []
    for part in _norm(raw).split(","):
        item = part.strip()
        if not item:
            continue
        key = item.lower()
        if key in excluded or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return ",".join(out)


def target_system_of(org) -> str:
    """读取某组织的「目标系统名」—— 全局唯一口径。

    空/NULL = 映射到自身 name。**任何读取处都必须走这里，禁止直接读列。**
    """
    return _norm(org.target_system_name) or _norm(org.name)


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
        from sqlalchemy.exc import IntegrityError

        payload = dict(data)
        payload.setdefault("org_type", DEFAULT_ORG_TYPE)
        self._apply_mapping_rules(db, payload, exclude_id=None)
        obj = PmwbOrg(**payload)
        db.add(obj)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ValidationException(f"组织名称重复：{payload.get('name', '')}")
        db.refresh(obj)
        return obj

    def update_org(self, db: Session, org_id: int, data: dict) -> Optional[PmwbOrg]:
        """更新组织。返回对象上可能挂有 `cascade_updated`（目标系统更名的级联行数）。"""
        from sqlalchemy.exc import IntegrityError

        obj = db.get(PmwbOrg, org_id)
        if not obj:
            return None
        old_name = _norm(obj.name)
        payload = dict(data)
        self._apply_mapping_rules(db, payload, exclude_id=org_id)
        for k, v in payload.items():
            setattr(obj, k, v)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ValidationException(f"组织名称重复：{payload.get('name', '')}")
        db.refresh(obj)
        # 目标系统更名 → 中台级联刷「引用了该旧名」的 target_system_name
        new_name = _norm(obj.name)
        if old_name and new_name and old_name != new_name:
            obj.cascade_updated = self._cascade_target_rename(db, old_name, new_name, exclude_id=org_id)
            db.commit()
        return obj

    def delete_org(self, db: Session, org_id: int, force: bool = False) -> bool:
        """删除组织。默认拒绝危险删除，force=True 才保留原有的「连同成员一起删」行为。"""
        obj = db.get(PmwbOrg, org_id)
        if not obj:
            return False
        if not force:
            staff_cnt = db.query(PmwbStaff).filter(PmwbStaff.org_id == org_id).count()
            if staff_cnt:
                raise ValidationException(
                    f"该组织下仍有 {staff_cnt} 名成员，拒绝删除；"
                    f"确认要连同成员一并删除请显式携带 force=true"
                )
            refs = (
                db.query(PmwbOrg)
                .filter(PmwbOrg.target_system_name == _norm(obj.name), PmwbOrg.id != org_id)
                .all()
            )
            if refs:
                names = "、".join(_norm(r.name) for r in refs[:5])
                raise ValidationException(
                    f"组织「{_norm(obj.name)}」正被以下组织映射为目标系统：{names}；请先解除映射再删除"
                )
        db.query(PmwbStaff).filter(PmwbStaff.org_id == org_id).delete()
        db.delete(obj)
        db.commit()
        return True

    # ------------------------------------------------------------------
    # 系统别名映射（组织 → 外部工单系统名）
    # ------------------------------------------------------------------
    def _system_orgs(self, db: Session) -> List[PmwbOrg]:
        """启用的 system 类组织，按 (sort, id) 升序 —— 决定「主组织」优先级。"""
        return (
            db.query(PmwbOrg)
            .filter(PmwbOrg.enabled.is_(True), PmwbOrg.org_type == "system")
            .order_by(PmwbOrg.sort, PmwbOrg.id)
            .all()
        )

    def _apply_mapping_rules(self, db: Session, payload: dict, exclude_id: Optional[int]) -> None:
        """按边界规则第 2/3/4/6/7 条归一化并校验映射字段（原地修改 payload）。

        抛 ValidationException 的情形：org_type 非法、目标系统名不在候选集、别名与其它组织冲突。
        """
        if "org_type" in payload:
            ot = _norm(payload.get("org_type")) or DEFAULT_ORG_TYPE
            if ot not in ORG_TYPES:
                raise ValidationException(
                    f"组织类型非法：{payload.get('org_type')}（可选：{'/'.join(ORG_TYPES)}）"
                )
            payload["org_type"] = ot

        # 更新时若没传 name，用现有值参与「别名 == 自身名」的剔除判断
        name = _norm(payload.get("name"))
        if not name and exclude_id:
            cur = db.get(PmwbOrg, exclude_id)
            name = _norm(cur.name) if cur else ""

        # 目标系统名必须落在候选集内（禁自由文本，杜绝再造第三种脏写法）
        cur_obj = db.get(PmwbOrg, exclude_id) if exclude_id else None
        target = _norm(payload.get("target_system_name"))
        if "target_system_name" not in payload and cur_obj is not None:
            target = _norm(cur_obj.target_system_name)
        if target:
            candidates = self.target_system_options(db)
            if target not in candidates:
                raise ValidationException(
                    f"目标系统名「{target}」不在候选集内，请从下拉中选择（候选 {len(candidates)} 项）"
                )
            payload["target_system_name"] = target
        elif "target_system_name" in payload:
            # 显式传空串 = 清除映射（回落到「映射到自身」）
            payload["target_system_name"] = None

        if "aliases" in payload:
            aliases = clean_aliases(payload.get("aliases"), exclude_names=(name, target or name))
            # 与其它组织的「组织名」或「别名」冲突 → 拒绝第二个，并提示占用方
            query = db.query(PmwbOrg)
            if exclude_id:
                query = query.filter(PmwbOrg.id != exclude_id)
            for item in [a for a in aliases.split(",") if a.strip()]:
                low = item.strip().lower()
                for other in query.all():
                    if _norm(other.name).lower() == low:
                        raise ValidationException(
                            f"别名「{item.strip()}」与组织「{_norm(other.name)}」同名，请更换"
                        )
                    other_alias = clean_aliases(other.aliases)
                    for oa in [x for x in other_alias.split(",") if x.strip()]:
                        if oa.strip().lower() == low:
                            raise ValidationException(
                                f"别名「{item.strip()}」已被组织「{_norm(other.name)}」占用"
                            )
            payload["aliases"] = aliases

    def _cascade_target_rename(
        self, db: Session, old_name: str, new_name: str, exclude_id: Optional[int]
    ) -> int:
        """组织改名时，把引用了旧名作为 target_system_name 的行一并刷新为新名。

        注意：只刷**映射配置**本身。PMWB 业务侧的历史表（评估表 / 厂家开发状态行）
        刻意不级联，否则会与工单标题、邮件原始记录对不上账。兼容靠旧名写入 aliases。
        """
        query = db.query(PmwbOrg).filter(PmwbOrg.target_system_name == old_name)
        if exclude_id:
            query = query.filter(PmwbOrg.id != exclude_id)
        rows = query.all()
        for r in rows:
            r.target_system_name = new_name
            # 旧名降级为别名，保证历史工单仍能归一过来
            existing = clean_aliases(r.aliases)
            parts = [x for x in existing.split(",") if x.strip()]
            if old_name.lower() not in {p.lower() for p in parts}:
                parts.append(old_name)
            r.aliases = ",".join(parts)
        db.flush()
        return len(rows)

    def target_system_options(self, db: Session) -> List[str]:
        """中台侧「目标系统名」候选集：system 类组织的有效目标名去重。

        注意这只是**中台那一份**。完整候选集（含 PMWB 历史表 distinct）在主后端
        GET /api/v1/meta/target-system-options 做三方合并 —— 历史表在 yxtyg_db，本服务读不到。
        """
        return sorted({target_system_of(o) for o in self._system_orgs(db) if _norm(o.name)})

    def org_mapping_index(self, db: Session) -> List[dict]:
        """全量映射索引，供主后端一次拉全做内存匹配（避免 N 次请求）。

        已按 (sort, id) 升序 —— 主组织 = 第一条命中的目标名对应的组织。
        """
        return [
            {
                "org_id": o.id,
                "org_name": _norm(o.name),
                "org_type": o.org_type,
                "target_system_name": _norm(o.target_system_name) or None,
                "aliases": clean_aliases(o.aliases),
                "sort": o.sort or 0,
            }
            for o in self._system_orgs(db)
        ]

    # ------------------------------------------------------------------
    # 角色/身份定义
    # ------------------------------------------------------------------
    def list_roles(self, db: Session, include_disabled: bool = True) -> List[PmwbRole]:
        query = db.query(PmwbRole)
        if not include_disabled:
            query = query.filter(PmwbRole.enabled.is_(True))
        return query.order_by(PmwbRole.sort, PmwbRole.id).all()

    def create_role(self, db: Session, data: dict) -> PmwbRole:
        obj = PmwbRole(**data)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def update_role(self, db: Session, role_id: int, data: dict) -> Optional[PmwbRole]:
        obj = db.get(PmwbRole, role_id)
        if not obj:
            return None
        for k, v in data.items():
            setattr(obj, k, v)
        db.commit()
        db.refresh(obj)
        return obj

    def delete_role(self, db: Session, role_id: int) -> bool:
        obj = db.get(PmwbRole, role_id)
        if not obj:
            return False
        db.delete(obj)
        db.commit()
        return True

    # ------------------------------------------------------------------
    # 轻量选项（下拉用，不加载人员明细）
    # ------------------------------------------------------------------
    def org_options(self, db: Session) -> List[dict]:
        """返回启用的组织名称列表（用于选人组件的组织下拉）。"""
        orgs = (
            db.query(PmwbOrg)
            .filter(PmwbOrg.enabled.is_(True))
            .order_by(PmwbOrg.sort, PmwbOrg.id)
            .all()
        )
        return [{"id": o.id, "name": o.name} for o in orgs]

    def role_options(self, db: Session) -> List[dict]:
        """返回启用的身份名称列表（用于选人组件的身份下拉）。"""
        roles = (
            db.query(PmwbRole)
            .filter(PmwbRole.enabled.is_(True))
            .order_by(PmwbRole.sort, PmwbRole.id)
            .all()
        )
        return [{"id": r.id, "name": r.name} for r in roles]

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
        from sqlalchemy.exc import IntegrityError

        obj = PmwbStaff(**data)
        db.add(obj)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ValidationException(f"人员已存在：{data.get('name', '')}")
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
    # 选人组件
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
        """从 Excel 解析后的行批量 upsert 组织与人员。"""
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
                org = PmwbOrg(name=org_name, sort=sort, enabled=enabled, source_trace="manual")
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
                        source_trace="manual",
                    )
                    db.add(staff)
                    stats["created_staffs"] += 1

        db.commit()
        return stats

    def build_template_bytes(self) -> bytes:
        """生成 Excel 导入模板字节流（含填写说明 + 数据页签）。"""
        wb = Workbook()
        wb.remove(wb.active)

        # 填写说明
        ws_help = wb.create_sheet("填写说明")
        ws_help.sheet_view.showGridLines = False
        ws_help.column_dimensions["A"].width = 18
        ws_help.column_dimensions["B"].width = 80

        header_fill = PatternFill("solid", fgColor="2F5496")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        sub_font = Font(bold=True, size=11, color="2F5496")
        wrap = Alignment(vertical="top", wrap_text=True)

        r = 1
        ws_help.cell(r, 1, "团队信息 Excel 导入模板 · 填写说明").font = Font(bold=True, size=14, color="2F5496")
        r += 2

        help_lines = [
            ("一、总体说明", ""),
            ("", "每一行 = 一名成员；相同组织+姓名的成员会被覆盖更新，不会重复创建。"),
            ("", "去重规则：优先按邮箱匹配；邮箱为空时按 组织名称+成员姓名 匹配。"),
            ("二、必填与选填", ""),
            ("组织名称*", "必填。若不存在则自动创建新组织。"),
            ("成员姓名*", "必填。"),
            ("邮箱", "可选但强烈建议填写，用于邮件中心、会议通知等场景。"),
            ("电话", "可选。"),
            ("身份", "可选，如产品经理、SA、开发等，用于角色筛选。"),
            ("排序号", "可选，数字越小排序越靠前，默认 0。"),
            ("是否启用", "可选，填“是/启用/1/true”表示启用，填“否/停用/0/false”表示停用，默认启用。"),
            ("三、注意事项", ""),
            ("", "• 请勿修改页签名称与各列表头文字。"),
            ("", "• 留空行会被自动忽略。"),
            ("", "• 导入前建议在人员中台页面查看现有人员，避免误覆盖。"),
        ]
        for title, body in help_lines:
            if title and not body:
                ws_help.cell(r, 1, title).font = sub_font
            elif title:
                ws_help.cell(r, 1, title).font = Font(bold=True)
                ws_help.cell(r, 2, body).alignment = wrap
            else:
                ws_help.cell(r, 2, body).alignment = wrap
            r += 1

        # 数据页签
        ws = wb.create_sheet("团队信息导入")
        headers = [c[0] for c in TEMPLATE_COLUMNS]
        ws.append(headers)
        for col_idx, (name, _required) in enumerate(TEMPLATE_COLUMNS, start=1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.column_dimensions[cell.column_letter].width = max(14, len(name) + 4)

        # 示例数据
        ws.append(["政企业务部", "张三", "zhangsan@example.com", "13800138000", "产品经理", 0, "是"])
        ws.append(["CRM维护", "李四", "lisi@example.com", "", "系统维护", 1, "是"])
        ws.append(["BOSS维护", "", "", "", "", "", ""])

        bio = io.BytesIO()
        wb.save(bio)
        bio.seek(0)
        return bio.getvalue()


basic_data_service = BasicDataService()
