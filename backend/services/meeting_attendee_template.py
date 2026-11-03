"""会议参会人预制模板 Service。

唯一真相源：模板挂在会议类型字典（pmwb_meeting_type.name）上，
会议室（pmwb_meeting）只存最终选中的参会人，不反向依赖模板。

成员口径：members 为姓名数组，与 pmwb_meeting_attendee.name 一致，
前端 StaffSelect 直接消费（全站选人组件值 = 姓名）。
"""
import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from db.models import PmwbMeetingAttendeeTemplate, PmwbMeetingType


def _parse_members(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    out: List[str] = []
    seen = set()
    for item in data:
        name = str(item or "").strip()
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def _dump_members(members: Any) -> str:
    if isinstance(members, str):
        # 允许传 "张三,李四" / "张三、李四"
        parts = members.replace("、", ",").replace("，", ",").split(",")
        names = [p.strip() for p in parts if p.strip()]
    elif isinstance(members, (list, tuple)):
        names = [str(m or "").strip() for m in members if str(m or "").strip()]
    else:
        names = []
    deduped: List[str] = []
    seen = set()
    for n in names:
        if n not in seen:
            seen.add(n)
            deduped.append(n)
    return json.dumps(deduped, ensure_ascii=False)


def _to_dict(t: PmwbMeetingAttendeeTemplate) -> Dict[str, Any]:
    members = _parse_members(t.members)
    return {
        "id": t.id,
        "meeting_type": t.meeting_type,
        "name": t.name,
        "members": members,
        "member_count": len(members),
        "sort_order": t.sort_order or 0,
        "enabled": bool(t.enabled),
        "remark": t.remark,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
    }


def _assert_type_exists(db: Session, meeting_type: str) -> None:
    exists = (
        db.query(PmwbMeetingType).filter(PmwbMeetingType.name == meeting_type).first()
    )
    if not exists:
        raise ValueError(f"会议类型「{meeting_type}」不存在，请先在类型管理中新增")


def list_templates(
    db: Session, meeting_type: Optional[str] = None, enabled_only: bool = False
) -> List[Dict[str, Any]]:
    query = db.query(PmwbMeetingAttendeeTemplate)
    if meeting_type:
        query = query.filter(PmwbMeetingAttendeeTemplate.meeting_type == meeting_type)
    if enabled_only:
        query = query.filter(PmwbMeetingAttendeeTemplate.enabled.is_(True))
    rows = query.order_by(
        PmwbMeetingAttendeeTemplate.sort_order.asc(),
        PmwbMeetingAttendeeTemplate.id.asc(),
    ).all()
    return [_to_dict(t) for t in rows]


def create_template(db: Session, data: Dict[str, Any]) -> Dict[str, Any]:
    meeting_type = (data.get("meeting_type") or "").strip()
    name = (data.get("name") or "").strip()
    if not meeting_type:
        raise ValueError("请选择关联的会议类型")
    if not name:
        raise ValueError("模板名称不能为空")
    if len(name) > 64:
        raise ValueError("模板名称不能超过 64 字")
    _assert_type_exists(db, meeting_type)
    dup = (
        db.query(PmwbMeetingAttendeeTemplate)
        .filter(
            PmwbMeetingAttendeeTemplate.meeting_type == meeting_type,
            PmwbMeetingAttendeeTemplate.name == name,
        )
        .first()
    )
    if dup:
        raise ValueError(f"类型「{meeting_type}」下已存在模板「{name}」")

    t = PmwbMeetingAttendeeTemplate(
        meeting_type=meeting_type,
        name=name,
        members=_dump_members(data.get("members")),
        sort_order=data.get("sort_order") or 0,
        enabled=True,
        remark=(data.get("remark") or "").strip() or None,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _to_dict(t)


def update_template(db: Session, template_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    t = (
        db.query(PmwbMeetingAttendeeTemplate)
        .filter(PmwbMeetingAttendeeTemplate.id == template_id)
        .first()
    )
    if not t:
        raise ValueError("模板不存在")

    if data.get("meeting_type") is not None:
        new_type = (data.get("meeting_type") or "").strip()
        if not new_type:
            raise ValueError("请选择关联的会议类型")
        _assert_type_exists(db, new_type)
        t.meeting_type = new_type

    if data.get("name") is not None:
        new_name = (data.get("name") or "").strip()
        if not new_name:
            raise ValueError("模板名称不能为空")
        if new_name != t.name:
            dup = (
                db.query(PmwbMeetingAttendeeTemplate)
                .filter(
                    PmwbMeetingAttendeeTemplate.meeting_type == t.meeting_type,
                    PmwbMeetingAttendeeTemplate.name == new_name,
                    PmwbMeetingAttendeeTemplate.id != template_id,
                )
                .first()
            )
            if dup:
                raise ValueError(f"类型「{t.meeting_type}」下已存在模板「{new_name}」")
            t.name = new_name

    if data.get("members") is not None:
        t.members = _dump_members(data.get("members"))
    if data.get("sort_order") is not None:
        t.sort_order = data["sort_order"]
    if data.get("enabled") is not None:
        t.enabled = bool(data["enabled"])
    if data.get("remark") is not None:
        t.remark = (data.get("remark") or "").strip() or None

    db.commit()
    db.refresh(t)
    return _to_dict(t)


def delete_template(db: Session, template_id: int) -> Dict[str, Any]:
    t = (
        db.query(PmwbMeetingAttendeeTemplate)
        .filter(PmwbMeetingAttendeeTemplate.id == template_id)
        .first()
    )
    if not t:
        raise ValueError("模板不存在")
    db.delete(t)
    db.commit()
    return {"deleted": True, "id": template_id}


class _AttendeeTemplateService:
    """调用入口命名空间（与 meeting_type_service 风格对齐）。"""

    list_templates = staticmethod(list_templates)
    create_template = staticmethod(create_template)
    update_template = staticmethod(update_template)
    delete_template = staticmethod(delete_template)


meeting_attendee_template_service = _AttendeeTemplateService()
