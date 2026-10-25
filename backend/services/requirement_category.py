"""需求分类字典 Service（需求与交付「需求分类」子模块）。

唯一真相源铁律：
  需求工单（pmwb_requirement_ext.category）以本字典表 name 为准，随本表增删改而变化。
  改名必须级联 UPDATE ext（保证按分类统计不分裂）；删除前必须校验无工单引用（建议改用停用）。

分类值直接落中文名，无 code 列，分析与展示零转译（2026-10-25 老大拍板）。
"""
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import PmwbRequirementCategory, PmwbRequirementExt


def _to_dict(cat: PmwbRequirementCategory, ref_count: int = 0) -> Dict[str, Any]:
    return {
        "id": cat.id,
        "name": cat.name,
        "sort_order": cat.sort_order or 0,
        "enabled": bool(cat.enabled),
        "remark": cat.remark,
        "ref_count": ref_count,
        "created_at": cat.created_at,
        "updated_at": cat.updated_at,
    }


def _ref_count_map(db: Session) -> Dict[str, int]:
    """统计每个分类名被需求工单引用的次数（ext.category 直接落中文名）。"""
    rows = (
        db.query(PmwbRequirementExt.category, func.count(PmwbRequirementExt.id))
        .filter(PmwbRequirementExt.category.isnot(None), PmwbRequirementExt.category != "")
        .group_by(PmwbRequirementExt.category)
        .all()
    )
    return {row[0]: row[1] for row in rows}


def list_categories(db: Session) -> List[Dict[str, Any]]:
    """管理视图：全量分类（含停用），按 sort_order,name 排序，带引用计数。"""
    ref_map = _ref_count_map(db)
    cats = (
        db.query(PmwbRequirementCategory)
        .order_by(PmwbRequirementCategory.sort_order.asc(), PmwbRequirementCategory.name.asc())
        .all()
    )
    return [_to_dict(c, ref_map.get(c.name, 0)) for c in cats]


def list_options(db: Session) -> List[Dict[str, Any]]:
    """下拉选项：仅启用分类，按 sort_order,name 排序。"""
    cats = (
        db.query(PmwbRequirementCategory)
        .filter(PmwbRequirementCategory.enabled.is_(True))
        .order_by(PmwbRequirementCategory.sort_order.asc(), PmwbRequirementCategory.name.asc())
        .all()
    )
    return [{"id": c.id, "name": c.name} for c in cats]


def create_category(db: Session, data: Dict[str, Any]) -> Dict[str, Any]:
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("分类名称不能为空")
    if len(name) > 64:
        raise ValueError("分类名称不能超过 64 字")
    exists = db.query(PmwbRequirementCategory).filter(PmwbRequirementCategory.name == name).first()
    if exists:
        raise ValueError(f"分类「{name}」已存在")
    cat = PmwbRequirementCategory(
        name=name,
        sort_order=data.get("sort_order") or 0,
        enabled=True,
        remark=(data.get("remark") or "").strip() or None,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return _to_dict(cat)


def update_category(db: Session, cat_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    cat = db.query(PmwbRequirementCategory).filter(PmwbRequirementCategory.id == cat_id).first()
    if not cat:
        raise ValueError("分类不存在")
    new_name = data.get("name")
    if new_name is not None:
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("分类名称不能为空")
        if new_name != cat.name:
            dup = (
                db.query(PmwbRequirementCategory)
                .filter(PmwbRequirementCategory.name == new_name, PmwbRequirementCategory.id != cat_id)
                .first()
            )
            if dup:
                raise ValueError(f"分类「{new_name}」已存在")
            old_name = cat.name
            cat.name = new_name
            # 改名级联：工单落的是中文名，必须同步，否则按分类统计分裂
            if data.get("cascade", True):
                db.query(PmwbRequirementExt).filter(
                    PmwbRequirementExt.category == old_name
                ).update({"category": new_name}, synchronize_session=False)
    if data.get("sort_order") is not None:
        cat.sort_order = data["sort_order"]
    if data.get("enabled") is not None:
        cat.enabled = bool(data["enabled"])
    if data.get("remark") is not None:
        cat.remark = (data.get("remark") or "").strip() or None
    db.commit()
    db.refresh(cat)
    ref_map = _ref_count_map(db)
    return _to_dict(cat, ref_map.get(cat.name, 0))


def delete_category(db: Session, cat_id: int) -> Dict[str, Any]:
    """删除分类：被工单引用时禁止删除（提示改用停用，保留统计口径）。"""
    cat = db.query(PmwbRequirementCategory).filter(PmwbRequirementCategory.id == cat_id).first()
    if not cat:
        raise ValueError("分类不存在")
    ref_count = (
        db.query(PmwbRequirementExt)
        .filter(PmwbRequirementExt.category == cat.name)
        .count()
    )
    if ref_count > 0:
        raise ValueError(
            f"分类「{cat.name}」已被 {ref_count} 张需求工单引用，删除会导致统计口径断裂，请改用「停用」"
        )
    db.delete(cat)
    db.commit()
    return {"deleted": True, "name": cat.name}
