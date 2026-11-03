"""会议类型字典 Service（会议管理「会议类型」子模块）。

唯一真相源铁律：
  会议（pmwb_meeting.meeting_type）以本字典表 name 为准，随本表增删改而变化。
  改名必须级联 UPDATE pmwb_meeting（保证按类型统计不分裂）；删除前必须校验无会议引用。

类型值直接落中文名，无 code 列，分析与展示零转译（沿需求分类字典表先例）。
"""
from typing import Any, Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import PmwbMeeting, PmwbMeetingAttendeeTemplate, PmwbMeetingType

# 展示色板（与前端 tag 语义类对齐：amber/red/blue/green/purple/gray）
ALLOWED_COLORS = {"amber", "red", "blue", "green", "purple", "gray"}


def _to_dict(t: PmwbMeetingType, ref_count: int = 0) -> Dict[str, Any]:
    return {
        "id": t.id,
        "name": t.name,
        "sort_order": t.sort_order or 0,
        "enabled": bool(t.enabled),
        "color": t.color or "blue",
        "remark": t.remark,
        "ref_count": ref_count,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
    }


def _ref_count_map(db: Session) -> Dict[str, int]:
    """统计每个类型名被会议引用的次数。"""
    rows = (
        db.query(PmwbMeeting.meeting_type, func.count(PmwbMeeting.id))
        .filter(PmwbMeeting.meeting_type.isnot(None), PmwbMeeting.meeting_type != "")
        .group_by(PmwbMeeting.meeting_type)
        .all()
    )
    return {row[0]: row[1] for row in rows}


def type_exists(db: Session, name: str, *, enabled_only: bool = False) -> bool:
    """校验类型是否在字典中（默认含停用项：存量会议允许保留展示）。"""
    if not name:
        return False
    query = db.query(PmwbMeetingType).filter(PmwbMeetingType.name == name)
    if enabled_only:
        query = query.filter(PmwbMeetingType.enabled.is_(True))
    return query.first() is not None


def list_types(db: Session) -> List[Dict[str, Any]]:
    """管理视图：全量类型（含停用），按 sort_order,id 排序，带引用计数。"""
    ref_map = _ref_count_map(db)
    rows = (
        db.query(PmwbMeetingType)
        .order_by(PmwbMeetingType.sort_order.asc(), PmwbMeetingType.id.asc())
        .all()
    )
    return [_to_dict(t, ref_map.get(t.name, 0)) for t in rows]


def list_options(db: Session) -> List[Dict[str, Any]]:
    """下拉选项：仅启用类型，按 sort_order,id 排序（含 color 供前端 tag 渲染）。"""
    rows = (
        db.query(PmwbMeetingType)
        .filter(PmwbMeetingType.enabled.is_(True))
        .order_by(PmwbMeetingType.sort_order.asc(), PmwbMeetingType.id.asc())
        .all()
    )
    return [{"id": t.id, "name": t.name, "color": t.color or "blue"} for t in rows]


def _normalize_color(value: Any) -> str:
    c = (value or "").strip() or "blue"
    return c if c in ALLOWED_COLORS else "blue"


def create_type(db: Session, data: Dict[str, Any]) -> Dict[str, Any]:
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("类型名称不能为空")
    if len(name) > 64:
        raise ValueError("类型名称不能超过 64 字")
    exists = db.query(PmwbMeetingType).filter(PmwbMeetingType.name == name).first()
    if exists:
        raise ValueError(f"类型「{name}」已存在")
    t = PmwbMeetingType(
        name=name,
        sort_order=data.get("sort_order") or 0,
        enabled=True,
        color=_normalize_color(data.get("color")),
        remark=(data.get("remark") or "").strip() or None,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _to_dict(t)


def update_type(db: Session, type_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    t = db.query(PmwbMeetingType).filter(PmwbMeetingType.id == type_id).first()
    if not t:
        raise ValueError("类型不存在")
    new_name = data.get("name")
    if new_name is not None:
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("类型名称不能为空")
        if new_name != t.name:
            dup = (
                db.query(PmwbMeetingType)
                .filter(PmwbMeetingType.name == new_name, PmwbMeetingType.id != type_id)
                .first()
            )
            if dup:
                raise ValueError(f"类型「{new_name}」已存在")
            old_name = t.name
            t.name = new_name
            # 改名级联：会议落的是类型中文名，必须同步，否则按类型统计分裂
            if data.get("cascade", True):
                db.query(PmwbMeeting).filter(
                    PmwbMeeting.meeting_type == old_name
                ).update({"meeting_type": new_name}, synchronize_session=False)
                # 参会人模板同样按类型名挂载，必须同步改名，否则模板从下拉消失
                db.query(PmwbMeetingAttendeeTemplate).filter(
                    PmwbMeetingAttendeeTemplate.meeting_type == old_name
                ).update({"meeting_type": new_name}, synchronize_session=False)
    if data.get("sort_order") is not None:
        t.sort_order = data["sort_order"]
    if data.get("enabled") is not None:
        t.enabled = bool(data["enabled"])
    if data.get("color") is not None:
        t.color = _normalize_color(data["color"])
    if data.get("remark") is not None:
        t.remark = (data.get("remark") or "").strip() or None
    db.commit()
    db.refresh(t)
    ref_map = _ref_count_map(db)
    return _to_dict(t, ref_map.get(t.name, 0))


def delete_type(db: Session, type_id: int) -> Dict[str, Any]:
    """删除类型：被会议引用时禁止删除（提示改用停用，保留统计口径）。"""
    t = db.query(PmwbMeetingType).filter(PmwbMeetingType.id == type_id).first()
    if not t:
        raise ValueError("类型不存在")
    ref_count = (
        db.query(PmwbMeeting).filter(PmwbMeeting.meeting_type == t.name).count()
    )
    if ref_count > 0:
        raise ValueError(
            f"类型「{t.name}」已被 {ref_count} 场会议引用，删除会导致统计口径断裂，请改用「停用」"
        )
    # 模板是该类型的附属配置（无历史统计价值），随类型一并清理
    db.query(PmwbMeetingAttendeeTemplate).filter(
        PmwbMeetingAttendeeTemplate.meeting_type == t.name
    ).delete(synchronize_session=False)
    db.delete(t)
    db.commit()
    return {"deleted": True, "name": t.name}


class _MeetingTypeService:
    """调用入口命名空间（与 meeting_service 等风格对齐；实现为上方模块函数）。"""

    type_exists = staticmethod(type_exists)
    list_types = staticmethod(list_types)
    list_options = staticmethod(list_options)
    create_type = staticmethod(create_type)
    update_type = staticmethod(update_type)
    delete_type = staticmethod(delete_type)


meeting_type_service = _MeetingTypeService()
