"""候选池与纳入（pb-2 / L2）—— 唯一可复算规则实现。

- 只读源模块：需求 = pmwb_requirement_ext + sent_emails；BUG = pmwb_operation_issue；
- 命中/排除逐条带 reason，规则常量在 constants/paiban.py 唯一定义；
- **不做后台静默自动纳入**（决策 Q3）：候选只读，纳入必须显式调用；
- 三处入口（候选池批量 / 行内 / 幂等同步）共用 include_once()，同锚唯一主行；
- 源消失 / 人工移出 → 墓碑留行（active=0），默认列表排除，历史不删。

⚠ 绝不回写源表状态、不回写运营 BUG 工单（本期边界 Q7）。
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from constants import paiban as C
from core.exceptions import NotFoundException, ValidationException
from db.models import (
    PmwbOperationIssue, PmwbPbTrack, PmwbRequirementExt, SentEmail, now_cn,
)
from services import paiban_common as K
from services import paiban_team as TEAM
from services import paiban_track as TS


def _as_date(v: Any):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if v:
        try:
            return date.fromisoformat(str(v)[:10])
        except ValueError:
            return None
    return None


def reason_label(key: str) -> str:
    return dict(C.CANDIDATE_REASONS).get(key, key)


def _existing(db: Session, ticket_type: str, ticket_no: str) -> Optional[PmwbPbTrack]:
    return db.query(PmwbPbTrack).filter(
        PmwbPbTrack.ticket_type == ticket_type,
        PmwbPbTrack.ticket_no == ticket_no,
    ).first()


def _source_by_no(db: Session, ticket_type: str, no: str) -> Optional[Dict[str, Any]]:
    """按锚点取源快照（纳入 / 同步共用），不存在返回 None → 墓碑。"""
    if ticket_type == "req":
        ext = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == no).first()
        if ext is None:
            return None
        mail = db.query(SentEmail).filter(SentEmail.req_id == no).first()
        return {
            "ticket_type": "req", "ticket_no": no,
            "title": (ext.req_name or (mail.req_name if mail else "") or no).strip(),
            "system_name": (ext.system_name or (mail.system_name if mail else "") or "").strip(),
            "owner": (ext.sa_name or (mail.sa_name if mail else "") or "").strip(),
            "priority": (ext.priority or "P2").strip(),
            "expected_date": K.iso(ext.version_required_date),
            "delivered_date": K.iso(ext.delivered_date),
            "status": (ext.status or "proposed").strip(),
            "version_anchor": bool(mail and (mail.dev_ticket_no or "").strip()),
        }
    x = db.query(PmwbOperationIssue).filter(PmwbOperationIssue.issue_no == no).first()
    if x is None:
        return None
    return {
        "ticket_type": "bug", "ticket_no": no, "title": (x.title or "").strip(),
        "system_name": (x.related_system or "").strip(),
        "owner": (x.handler or "").strip(),
        "priority": (x.impact_level or "P2").strip(),
        "expected_date": K.iso(x.go_live_date),
        "status": (x.status or "pending").strip(),
        "category": (x.category or "").strip(),
        "issue_type": (x.issue_type or "").strip(),
        "version_anchor": False,
    }


def _judge(row: Dict[str, Any]) -> str:
    """唯一筛选判定：返回命中或排除的 reason key。"""
    no = (row.get("ticket_no") or "").strip()
    if not no:
        return "source_missing"
    if row["ticket_type"] == "bug":
        cat, sub = row.get("category", ""), row.get("issue_type", "")
        if cat not in C.BUG_CATEGORY_KEYS and sub not in C.BUG_CATEGORY_KEYS:
            return "excluded_type"
        if row.get("status") in C.BUG_CLOSED_STATUSES:
            return "closed"
        if not row.get("expected_date") and row.get("priority") not in C.BUG_PRIORITY_KEYS:
            return "no_anchor"
    else:
        if row.get("status") in C.REQ_CLOSED_STATUSES or row.get("delivered_date"):
            return "closed"
        if not row.get("expected_date") and not row.get("version_anchor"):
            return "no_anchor"
    if not row.get("system_name"):
        return "no_system"
    return "hit"


def scan(db: Session, *, keyword: str = "", limit: int = 200,
         ticket_type: str = "") -> Dict[str, Any]:
    """候选池：只读扫描 + 逐条可复算原因；不做任何写入。"""
    limit = max(1, min(int(limit or 200), 500))
    hits, excluded = [], []
    if ticket_type != "bug":
        # 只按需求主表查，每行一条需求：严禁 outerjoin SentEmail —— 一个需求有多封
        # 邮件会 join 出 N 行重复候选（运行态 2026110031 有 4 封邮件曾重复 4 次）。
        # 邮件名/系统/版本锚点的兜底由 _source_by_no() 内部按 req_id 取首封完成。
        q = db.query(PmwbRequirementExt)
        if keyword:
            q = q.filter(PmwbRequirementExt.req_id.like(f"%{keyword}%")
                         | PmwbRequirementExt.req_name.like(f"%{keyword}%"))
        for ext in q.order_by(PmwbRequirementExt.id.desc()).limit(limit).all():
            row = _source_by_no(db, "req", (ext.req_id or "").strip())
            if row:
                _classify(db, row, hits, excluded)
    if ticket_type != "req":
        q = db.query(PmwbOperationIssue)
        if keyword:
            q = q.filter(PmwbOperationIssue.issue_no.like(f"%{keyword}%")
                         | PmwbOperationIssue.title.like(f"%{keyword}%"))
        for x in q.order_by(PmwbOperationIssue.id.desc()).limit(limit).all():
            row = _source_by_no(db, "bug", (x.issue_no or "").strip())
            if row:
                _classify(db, row, hits, excluded)
    counts: Dict[str, int] = {}
    for x in excluded:
        counts[x["reason"]] = counts.get(x["reason"], 0) + 1
    return {
        "items": hits, "excluded": excluded,
        "summary": {
            "hit_count": len(hits), "excluded_count": len(excluded),
            "by_reason": [{"reason": k, "label": reason_label(k), "count": v}
                          for k, v in sorted(counts.items())],
        },
        "scope_note": "候选只读、规则可复算；纳入须显式确认，不后台静默写入",
        "filter": {"keyword": keyword, "limit": limit, "ticket_type": ticket_type},
    }


def _classify(db: Session, row: Dict[str, Any], hits: List, excluded: List) -> None:
    reason = _judge(row)
    existing = _existing(db, row["ticket_type"], row["ticket_no"])
    if existing is not None and reason == "hit":
        reason = "tombstone" if not existing.active else "already_tracked"
    item = dict(row)
    item["reason"] = reason
    item["reason_label"] = reason_label(reason)
    item["can_include"] = reason == "hit"
    item["existing_track_id"] = existing.id if existing else None
    (hits if reason == "hit" else excluded).append(item)


def include_once(db: Session, ticket_type: str, ticket_no: str, *,
                 operator: str = "", source: str = "pool") -> Dict[str, Any]:
    """纳入唯一实现：同锚幂等；写主行 + 团队子行 + 版本归属，不复制源本体。"""
    if ticket_type not in [k for k, _ in C.TICKET_TYPES]:
        raise ValidationException("工单类型只能是需求或 BUG")
    no = (ticket_no or "").strip()
    if not no:
        raise ValidationException("工单编号不能为空")
    if source not in [k for k, _ in C.INCLUDE_SOURCES]:
        raise ValidationException("纳入入口不在闭集内")
    row = _source_by_no(db, ticket_type, no)
    if row is None:
        raise NotFoundException(f"源工单 {no} 不存在，不能纳入")
    reason = _judge(row)
    if reason != "hit":
        raise ValidationException(f"该工单不符合纳入条件：{reason_label(reason)}")
    old = _existing(db, ticket_type, no)
    if old is not None:
        if old.active:
            return {"created": False, "id": old.id, "ticket_no": no,
                    "idempotent": True, "reason": "already_tracked"}
        # 墓碑复归：保留原主行与历史，重新纳入
        old.active, old.removed_at, old.removed_reason = 1, None, None
        t = old
    else:
        t = PmwbPbTrack(
            ticket_type=ticket_type, ticket_no=no, title=row["title"],
            system_name=row["system_name"], owner=row["owner"],
            priority=row["priority"], expected_date=_as_date(row.get("expected_date")),
            source_snapshot=K.jdump(row), include_source=source,
            included_at=now_cn(), included_by=operator, stage="plan_confirm",
            admit_status="pending", result="", active=1,
        )
        db.add(t)
        db.flush()
    t.title, t.system_name, t.owner, t.priority = (
        row["title"], row["system_name"], row["owner"], row["priority"]
    )
    t.expected_date = _as_date(row.get("expected_date"))
    t.source_snapshot = K.jdump(row)
    t.include_source, t.included_by = source, operator
    t.included_at = t.included_at or now_cn()
    TS.initialize(db, t, operator=operator)
    TEAM.sync_teams(db, t)
    db.commit()
    return {"created": old is None, "id": t.id, "ticket_no": no,
            "idempotent": False, "track": K.serialize_track(db, t)}


def include_batch(db: Session, items: List[Dict[str, Any]], *,
                  operator: str = "", source: str = "pool") -> Dict[str, Any]:
    created, skipped = [], []
    for it in items or []:
        try:
            out = include_once(db, str(it.get("ticket_type") or ""),
                               str(it.get("ticket_no") or ""),
                               operator=operator, source=source)
            (created if out.get("created") else skipped).append(out)
        except Exception as exc:  # 单条失败不影响整批，原因可见
            skipped.append({"ticket_no": it.get("ticket_no"),
                            "error": str(exc)[:200]})
    return {"created_count": len(created), "skipped_count": len(skipped),
            "created": created, "skipped": skipped}


def sync(db: Session, *, operator: str = "", mark_missing: bool = True) -> Dict[str, Any]:
    """显式幂等同步：刷新源快照，源消失置墓碑；**不改环节 / 准入 / 结果**。"""
    rows = db.query(PmwbPbTrack).all()
    updated, missing, unchanged = [], [], []
    for t in rows:
        src = _source_by_no(db, t.ticket_type, t.ticket_no)
        if src is None:
            if mark_missing and t.active:
                t.active, t.removed_at = 0, now_cn()
                t.removed_reason = "源工单已删除（幂等同步自动墓碑）"
                missing.append(t.ticket_no)
            continue
        sig = K.jdump({k: src.get(k) for k in
                       ("title", "system_name", "owner", "priority", "expected_date", "status")})
        if sig == t.source_snapshot_sig:
            continue
        t.source_snapshot, t.source_snapshot_sig = K.jdump(src), sig
        t.title, t.system_name, t.owner, t.priority = (
            src["title"], src["system_name"], src["owner"], src["priority"]
        )
        t.expected_date = _as_date(src.get("expected_date"))
        updated.append(t.ticket_no)
    db.commit()
    return {"total": len(rows), "updated": updated, "missing": missing,
            "unchanged_count": len(rows) - len(updated) - len(missing),
            "scope_note": "同步只刷新源快照与墓碑，不改环节/准入/结果"}


def remove(db: Session, track_id: int, *, reason: str, operator: str = "") -> Dict[str, Any]:
    """人工移出：主行 + 子行墓碑留行，历史督办/反馈/顺延不删。"""
    t = db.query(PmwbPbTrack).filter(PmwbPbTrack.id == track_id).first()
    if t is None:
        raise NotFoundException(f"跟踪主行 {track_id} 不存在")
    if not (reason or "").strip():
        raise ValidationException("移出必须填写原因")
    t.active, t.removed_at, t.removed_reason = 0, now_cn(), reason.strip()
    for sub in K.teams_of(db, t.id):
        sub.note = f"{sub.note or ''}\n[{K.dt_iso(now_cn())}] 主行移出：{reason}".strip()
    K.add_stage_log(db, t, t.stage, from_stage=t.stage, source="page",
                    operator=operator, reason=f"人工移出：{reason}")
    db.commit()
    return {"id": track_id, "removed": True, "reason": reason.strip()}
