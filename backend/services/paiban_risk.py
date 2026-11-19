"""风险事件（pb-5 / L5）—— 按工单维度，唯一实现。

- 类型闭集 constants/paiban.py::RISK_TYPES，禁自由建类；
- 自动仅三类来源：环节回退 / 截止超期 / 上线失败与顺延（由 paiban_track 触发）；
- 同 (工单, 风险类型) 且未消除 → **合并更新不新建**，原文追加不覆盖；
- 硬门禁：任一「影响上线且未消除」风险 → 拒绝登记「已上线」。
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from constants import paiban as C
from core.exceptions import NotFoundException, ValidationException
from db.models import PmwbPbRisk, PmwbPbTrack, now_cn
from services import paiban_common as K

RISK_KEYS = [k for k, _ in C.RISK_TYPES]


def _check_type(risk_type: str) -> None:
    if risk_type not in RISK_KEYS:
        raise ValidationException(f"风险类型 {risk_type} 不在闭集字典内，禁止自由建类")


def upsert(db: Session, track: PmwbPbTrack, risk_type: str, description: str, *,
           affect_release: int = 0, source: str = "page", raw_ref: str = "",
           reporter: str = "", level: str = "P2") -> PmwbPbRisk:
    """同 (工单, 类型) 未消除风险合并更新，不新建重复风险。"""
    _check_type(risk_type)
    plan_id = track.current_plan_id
    row = db.query(PmwbPbRisk).filter(
        PmwbPbRisk.track_id == track.id,
        PmwbPbRisk.risk_type == risk_type,
        PmwbPbRisk.status == "open",
    ).order_by(PmwbPbRisk.id.asc()).first()
    if row is None:
        row = PmwbPbRisk(
            track_id=track.id, plan_id=plan_id, risk_type=risk_type,
            description=description, affect_release=int(affect_release), level=level,
            source=source, raw_ref=raw_ref, reporter=reporter, status="open",
            merge_count=0, created_at=now_cn(),
        )
        db.add(row)
    else:
        row.merge_count = (row.merge_count or 0) + 1
        row.description = f"{row.description}\n[{K.dt_iso(now_cn())}] {description}".strip()
        if raw_ref:
            row.raw_ref = f"{row.raw_ref or ''}\n---\n{raw_ref}".strip()
        row.resolution = f"{row.resolution or ''}\n[{K.dt_iso(now_cn())}] 合并更新 #{row.merge_count}".strip()
        if int(affect_release):
            row.affect_release = 1
        if level:
            row.level = level
    db.flush()
    return row


def auto(db: Session, track: PmwbPbTrack, risk_type: str, description: str, *,
         raw_ref: str = "") -> PmwbPbRisk:
    if risk_type not in C.RISK_AUTO_TYPES:
        raise ValidationException("自动风险仅允许 环节回退/截止超期/上线失败/准入未通过")
    return upsert(db, track, risk_type, description, affect_release=1,
                  source="auto", raw_ref=raw_ref, reporter="系统")


def blocking(db: Session, track_id: int) -> List[Dict[str, Any]]:
    rows = db.query(PmwbPbRisk).filter(
        PmwbPbRisk.track_id == track_id,
        PmwbPbRisk.affect_release == 1,
        PmwbPbRisk.status == "open",
    ).order_by(PmwbPbRisk.id).all()
    return [serialize(x) for x in rows]


def gate_message(db: Session, track_id: int) -> str:
    rows = blocking(db, track_id)
    if not rows:
        return ""
    names = "、".join(f"{dict(C.RISK_TYPES).get(x['risk_type'], x['risk_type'])}" for x in rows)
    return f"存在 {len(rows)} 条「影响本版上线且未消除」风险（{names}），禁止登记已上线"


def serialize(r: PmwbPbRisk) -> Dict[str, Any]:
    return {
        "id": r.id, "track_id": r.track_id, "plan_id": r.plan_id,
        "risk_type": r.risk_type,
        "risk_type_label": dict(C.RISK_TYPES).get(r.risk_type, r.risk_type),
        "description": r.description, "affect_release": int(r.affect_release or 0),
        "level": r.level, "source": r.source, "raw_ref": r.raw_ref,
        "reporter": r.reporter, "status": r.status,
        "status_label": dict(C.RISK_STATUSES).get(r.status, r.status),
        "merge_count": r.merge_count or 0, "resolution": r.resolution,
        "created_at": K.dt_iso(r.created_at), "resolved_at": K.dt_iso(r.resolved_at),
    }


def create(db: Session, track_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    t = K.track_or_404(db, track_id)
    r = upsert(db, t, (payload.get("risk_type") or "").strip(),
               (payload.get("description") or "").strip(),
               affect_release=int(payload.get("affect_release") or 0),
               source=payload.get("source") or "page",
               raw_ref=payload.get("raw_ref") or "",
               reporter=payload.get("operator") or "",
               level=payload.get("level") or "P2")
    db.commit()
    return serialize(r)


def resolve(db: Session, risk_id: int, *, resolution: str, operator: str) -> Dict[str, Any]:
    r = db.query(PmwbPbRisk).filter(PmwbPbRisk.id == risk_id).first()
    if r is None:
        raise NotFoundException(f"风险 {risk_id} 不存在")
    r.status = "resolved"
    r.resolution = f"{r.resolution or ''}\n[{K.dt_iso(now_cn())}] {operator}：{resolution}".strip()
    r.resolved_at = now_cn()
    db.commit()
    return serialize(r)


def list_risks(db: Session, plan_id: Optional[int] = None, *,
               only_blocking: bool = False, track_id: Optional[int] = None) -> Dict[str, Any]:
    q = db.query(PmwbPbRisk)
    if plan_id:
        q = q.filter(PmwbPbRisk.plan_id == plan_id)
    if only_blocking:
        q = q.filter(PmwbPbRisk.affect_release == 1, PmwbPbRisk.status == "open")
    if track_id:
        q = q.filter(PmwbPbRisk.track_id == track_id)
    rows = q.order_by(PmwbPbRisk.id.desc()).all()
    return {
        "items": [serialize(x) for x in rows], "total": len(rows),
        "blocking_count": sum(1 for x in rows if x.affect_release == 1 and x.status == "open"),
        "scope_note": "风险按工单维度，顺延不重置",
    }
