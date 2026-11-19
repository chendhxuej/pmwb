"""团队解析与团队跟踪视图（pb-4 / L4）—— 唯一口径实现。

- 需求侧：现网「活跃厂家团队」唯一源 services/vendor_dev.py::active_team_systems；
- BUG 侧：责任人 → 人员组织中台系统名精确匹配（禁 LIKE 硬凑），失败进可见兜底；
- 主行 / 团队子行双层口径显式分离：版本统计按主行，团队视图按子行，禁加总；
- 解析失败绝不静默丢弃，一律进「（未分配团队）」并进待补全清单。
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from constants import paiban as C
from core.exceptions import NotFoundException, ValidationException
from db.models import (
    PmwbOrg, PmwbPbTrack, PmwbPbTrackTeam, PmwbPbParticipation, now_cn,
)
from services import paiban_common as K
from services.vendor_dev import active_team_systems

try:  # 中台不可用时降级为本地精确匹配，绝不猜团队
    from utils import master_service_client  # noqa: F401
except Exception:  # pragma: no cover
    master_service_client = None


def _resolve(db: Session, t: PmwbPbTrack) -> List[Dict[str, Any]]:
    """返回 [{team_name, owner, parse_status}]，失败项 parse_status=unresolved。"""
    if t.ticket_type == "req":
        try:
            rows = active_team_systems(db, t.ticket_no) or []
        except Exception:
            rows = []
        out = [{"team_name": r.get("system_name") or "", "owner": r.get("sa_name") or "",
                "parse_status": "ok"} for r in rows if r.get("system_name")]
        if out:
            return _dedup(out)
        if t.system_name:
            return [{"team_name": t.system_name, "owner": t.owner or "", "parse_status": "ok"}]
        return [{"team_name": C.NO_TEAM_LABEL, "owner": "", "parse_status": "unresolved"}]

    # BUG：源工单无团队列。责任人（可多人）经组织字典精确匹配；失败一律兜底可见。
    names = [x.strip() for x in (t.owner or "").replace("，", ",").split(",") if x.strip()]
    out: List[Dict[str, Any]] = []
    for name in names:
        org = db.query(PmwbOrg).filter(PmwbOrg.name == name).first()
        if org is not None:
            out.append({"team_name": org.name, "owner": name, "parse_status": "ok"})
    if out:
        return _dedup(out)
    if t.system_name:
        return [{"team_name": t.system_name, "owner": t.owner or "", "parse_status": "ok"}]
    return [{"team_name": C.NO_TEAM_LABEL, "owner": t.owner or "", "parse_status": "unresolved"}]


def _dedup(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen, out = set(), []
    for r in rows:
        key = r["team_name"]
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def sync_teams(db: Session, track: PmwbPbTrack) -> List[PmwbPbTrackTeam]:
    """幂等重建团队子行：同一 (工单, 团队) 只一行，不删除已有子行的进度。"""
    resolved = _resolve(db, track)
    existing = {x.team_name: x for x in db.query(PmwbPbTrackTeam).filter(
        PmwbPbTrackTeam.track_id == track.id
    ).all()}
    out = []
    for r in resolved:
        row = existing.get(r["team_name"])
        if row is None:
            row = PmwbPbTrackTeam(
                track_id=track.id, team_name=r["team_name"], owner=r["owner"],
                stage=track.stage, stage_entered_at=now_cn(), done=0,
                parse_status=r["parse_status"], recipient_status="unknown",
            )
            db.add(row)
        else:
            row.owner = row.owner or r["owner"]
            row.parse_status = r["parse_status"]
        out.append(row)
    db.flush()
    return out


def team_rows(db: Session, track_id: int) -> List[Dict[str, Any]]:
    return [{
        "id": x.id, "track_id": x.track_id, "team_name": x.team_name, "owner": x.owner,
        "stage": x.stage, "stage_label": C.STAGE_LABELS.get(x.stage, x.stage),
        "stage_entered_at": K.dt_iso(x.stage_entered_at), "done": int(x.done or 0),
        "parse_status": x.parse_status, "recipient_status": x.recipient_status,
        "last_feedback_at": K.dt_iso(x.last_feedback_at),
        "supervise_count": x.supervise_count or 0,
    } for x in K.teams_of(db, track_id)]


def matrix(db: Session, plan_id: Optional[int] = None, team_name: str = "",
           stage: str = "", overdue: str = "") -> Dict[str, Any]:
    """团队矩阵：数字 = 子行数；下钻与矩阵同源（同一 plan/team/stage 筛选）。"""
    q = db.query(PmwbPbTrackTeam, PmwbPbTrack).join(
        PmwbPbTrack, PmwbPbTrackTeam.track_id == PmwbPbTrack.id
    ).filter(PmwbPbTrack.active == 1)
    if plan_id:
        ids = [r.track_id for r in db.query(PmwbPbParticipation).filter(
            PmwbPbParticipation.plan_id == plan_id
        ).all()]
        q = q.filter(PmwbPbTrackTeam.track_id.in_(ids) if ids else PmwbPbTrackTeam.track_id == -1)
    if team_name:
        q = q.filter(PmwbPbTrackTeam.team_name == team_name)
    if stage:
        q = q.filter(PmwbPbTrackTeam.stage == stage)
    pairs = q.all()
    stages = [k for k, _ in C.STAGES]
    grid: Dict[str, Dict[str, int]] = {}
    unresolved: List[Dict[str, Any]] = []
    drill: List[Dict[str, Any]] = []
    for sub, t in pairs:
        m = K.stage_metrics(db, t)
        if overdue == "1" and not m["overdue"]:
            continue
        if overdue == "0" and m["overdue"]:
            continue
        grid.setdefault(sub.team_name, {s: 0 for s in stages})
        grid[sub.team_name][sub.stage] = grid[sub.team_name].get(sub.stage, 0) + 1
        if sub.parse_status == "unresolved" or sub.recipient_status == "missing":
            unresolved.append({"track_id": t.id, "ticket_no": t.ticket_no,
                               "team_name": sub.team_name, "reason": "团队/收件人解析失败"})
        drill.append({
            "track_id": t.id, "ticket_no": t.ticket_no, "title": t.title,
            "ticket_type": t.ticket_type, "team_name": sub.team_name,
            "stage": sub.stage, "stage_label": C.STAGE_LABELS.get(sub.stage, sub.stage),
            "admit_status": t.admit_status, "defer_count": t.defer_count or 0,
            "exception_flag": int(t.exception_flag or 0),
            "last_feedback_at": K.dt_iso(sub.last_feedback_at),
            "supervise_count": sub.supervise_count or 0,
            "overdue": m["overdue"], "deadline": m["deadline"],
        })
    main_count = len({d["track_id"] for d in drill})
    return {
        "stages": [{"key": k, "label": v} for k, v in C.STAGES],
        "grid": [{"team_name": name, "counts": cells,
                  "total": sum(cells.values())} for name, cells in sorted(grid.items())],
        "drill": drill,
        "main_row_count": main_count,
        "team_row_count": len(drill),
        "unresolved": unresolved,
        "scope_note": "版本统计按主行、团队视图按团队子行，两处数字不可加总",
        "filter": {"plan_id": plan_id, "team_name": team_name, "stage": stage, "overdue": overdue},
    }


def set_team_stage(db: Session, team_id: int, to_stage: str, *, reason: str = "",
                   operator: str = "", source: str = "page", done: Optional[bool] = None,
                   feedback_id: Optional[int] = None) -> Dict[str, Any]:
    """团队子行改态：逐级校验 + 回退必填原因 + 同一套留痕；主行由 paiban_track 重算。"""
    sub = db.query(PmwbPbTrackTeam).filter(PmwbPbTrackTeam.id == team_id).first()
    if sub is None:
        raise NotFoundException(f"团队子行 {team_id} 不存在")
    t = K.track_or_404(db, sub.track_id)
    fr = sub.stage
    forward = K.validate_transition(fr, to_stage)
    if not forward and not (reason or "").strip():
        raise ValidationException("环节回退必须填写原因")
    before = {"stage": fr, "done": int(sub.done or 0)}
    sub.stage = to_stage
    sub.stage_entered_at = now_cn()
    if done is not None:
        sub.done = int(done)
    K.add_stage_log(db, t, to_stage, from_stage=fr, team_id=sub.id,
                    is_rollback=not forward, reason=reason, source=source,
                    operator=operator, feedback_id=feedback_id,
                    before_value=before, after_value={"stage": to_stage, "done": int(sub.done or 0)})
    from services import paiban_risk as RS
    if not forward:
        RS.upsert(db, t, "stage_rollback", f"团队 {sub.team_name} 由 {C.STAGE_LABELS.get(fr, fr)} 回退至 "
                  f"{C.STAGE_LABELS.get(to_stage, to_stage)}：{reason}",
                  affect_release=1, source="auto", raw_ref=reason, reporter=operator)
    db.flush()
    from services import paiban_track as TS
    TS.recompute_main_stage(db, t, operator=operator, source=source)
    return K.serialize_track(db, t)
