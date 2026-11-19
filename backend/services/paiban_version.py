"""版本计划唯一服务（pb-1 / L1）。

职责：默认统一计划 + 系统覆盖、发布日派生四环节截止、计划状态与变更日志、
准入模式配置、系统→计划回落解析（**不落副本**）、顺延目标版本序列解析。

单一真相源纪律：
  - 枚举与倒排公式只在 constants/paiban.py；本文件不复制第二份；
  - 派生截止/准入时点**不落库**，改期后由读取期自动重算；
  - 系统字典只走 services/vendor_dev.py::target_system_options，禁 LIKE 硬凑；
  - 准入规则属于版本计划，不属于工单（工单级例外放行由 pb-3 负责）。

⚠ 本模块不写工单、不发邮件、不改源模块状态。
"""

from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlalchemy.orm import Session

from constants import paiban as C
from core.exceptions import DuplicateException, NotFoundException, ValidationException
from db.models import PmwbPbVersionChangeLog, PmwbPbVersionPlan, now_cn
from services.vendor_dev import target_system_options


def _norm(v: Any) -> str:
    return str(v).strip() if v is not None else ""


def _today() -> date:
    return now_cn().date()


def _iso(v: Any) -> str:
    return v.isoformat() if isinstance(v, date) else ""


# ── 系统字典（唯一源，可注入以便测试）────────────────────────────
def system_options(db: Session):
    """返回 (options, degraded)。中台不可达不硬拒登记，标 system_verified=0 待自动补校验。"""
    try:
        res = target_system_options(db) or {}
    except Exception:
        return [], True
    opts = [_norm(o) for o in (res.get("options") or []) if _norm(o)]
    return sorted(set(opts)), bool(res.get("degraded"))


def meta(db: Session) -> Dict[str, Any]:
    opts, degraded = system_options(db)
    return C.meta_payload(opts, degraded)


def preview(release_date: date, admit_mode: str = "open", admit_lead_days: int = 0) -> Dict[str, Any]:
    """登记页实时预览：倒排公式仍只在 constants/paiban.py，前端不另算一份。"""
    if not isinstance(release_date, date):
        raise ValidationException("计划发布日必填")
    if admit_mode not in dict(C.ADMIT_MODES):
        raise ValidationException("准入模式非法")
    if admit_mode == "wait_release_n_days" and int(admit_lead_days or 0) <= 0:
        admit_lead_days = C.DEFAULT_ADMIT_LEAD_DAYS
    return {
        "deadlines": C.derive_deadlines(release_date),
        "admit_gate_at": C.admit_gate_at(release_date, admit_mode, admit_lead_days),
        "admit_lead_days": int(admit_lead_days or 0),
    }


# ── 序列化（派生信息随读随算）──────────────────────────────────
def serialize_plan(plan: PmwbPbVersionPlan) -> Dict[str, Any]:
    labels = {
        "version_types": dict(C.VERSION_TYPES),
        "plan_statuses": dict(C.PLAN_STATUSES),
        "admit_modes": dict(C.ADMIT_MODES),
        "scope_types": dict(C.SCOPE_TYPES),
    }
    return {
        "id": plan.id,
        "version_no": plan.version_no,
        "scope_type": plan.scope_type,
        "scope_label": labels["scope_types"].get(plan.scope_type, plan.scope_type),
        "system_name": plan.system_name or "",
        "system_verified": int(plan.system_verified or 0),
        "version_type": plan.version_type,
        "version_type_label": labels["version_types"].get(plan.version_type, plan.version_type),
        "release_date": _iso(plan.release_date),
        "status": plan.status,
        "status_label": labels["plan_statuses"].get(plan.status, plan.status),
        "admit_mode": plan.admit_mode,
        "admit_mode_label": labels["admit_modes"].get(plan.admit_mode, plan.admit_mode),
        "admit_lead_days": int(plan.admit_lead_days or 0),
        "allow_temp_merge": int(plan.allow_temp_merge or 0),
        "next_version_id": plan.next_version_id,
        "remark": plan.remark or "",
        "created_at": plan.created_at.isoformat() if plan.created_at else "",
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else "",
        "deadlines": C.derive_deadlines(plan.release_date),
        "admit_gate_at": C.admit_gate_at(plan.release_date, plan.admit_mode, plan.admit_lead_days),
        "is_crm": _norm(plan.system_name) == C.CRM_SYSTEM_KEY,
    }


def _serialize_log(row: PmwbPbVersionChangeLog) -> Dict[str, Any]:
    return {
        "id": row.id,
        "plan_id": row.plan_id,
        "version_no": row.version_no,
        "change_type": row.change_type,
        "field": row.field,
        "old_value": row.old_value or "",
        "new_value": row.new_value or "",
        "affected_count": int(row.affected_count or 0),
        "operator": row.operator or "",
        "changed_at": row.changed_at.isoformat() if row.changed_at else "",
        "remark": row.remark or "",
    }


# ── 计划序列 / 回落 ────────────────────────────────────────────
def _series(db: Session, scope_type: str, system_name: Optional[str]) -> List[PmwbPbVersionPlan]:
    q = db.query(PmwbPbVersionPlan).filter(PmwbPbVersionPlan.scope_type == scope_type)
    if scope_type == "default":
        q = q.filter(PmwbPbVersionPlan.system_name.is_(None))
    else:
        q = q.filter(PmwbPbVersionPlan.system_name == _norm(system_name))
    q = q.filter(PmwbPbVersionPlan.status.in_(C.ACTIVE_PLAN_STATUSES))
    return q.order_by(PmwbPbVersionPlan.release_date.asc(), PmwbPbVersionPlan.id.asc()).all()


def _pick(plans: List[PmwbPbVersionPlan], as_of: date):
    """取「最近一条未来有效计划」；无未来计划时取最近一条历史计划并标 overdue。"""
    future = [p for p in plans if p.release_date and p.release_date >= as_of]
    if future:
        return future[0], False
    if plans:
        return plans[-1], True
    return None, False


def resolve_plan(db: Session, system_name: str, as_of: Optional[date] = None) -> Dict[str, Any]:
    """系统 → 版本计划的**唯一解析**（查询期解析，不落副本）。

    优先级：该系统专属有效计划 → 统一默认有效计划 → 缺失（待补版本计划）。
    """
    as_of = as_of or _today()
    system_name = _norm(system_name)
    exclusive, overdue = _pick(_series(db, "system", system_name), as_of) if system_name else (None, False)
    if exclusive is not None:
        return {
            "system": system_name,
            "source": "exclusive",
            "source_label": "专属计划",
            "overdue": overdue,
            "plan": serialize_plan(exclusive),
            "hint": "",
        }
    default, overdue = _pick(_series(db, "default", None), as_of)
    if default is not None:
        return {
            "system": system_name,
            "source": "default",
            "source_label": "统一默认",
            "overdue": overdue,
            "plan": serialize_plan(default),
            "hint": "该系统未单独配置版本计划，已回落统一默认计划；默认计划改期将自动重算截止与准入时点。",
        }
    return {
        "system": system_name,
        "source": "missing",
        "source_label": "待补版本计划",
        "overdue": False,
        "plan": None,
        "hint": "无有效版本计划：工单进「待补版本计划」清单，主行不关闭、不自动取消。",
    }


def next_plan(db: Session, plan: PmwbPbVersionPlan) -> Optional[Dict[str, Any]]:
    """顺延目标版本的**唯一解析**（pb-3 直接调用，禁止各入口另算一份）。

    显式 next_version_id 优先；否则同系统「发布日 > 当前发布日」的最近有效计划，
    系统专属序列无下一版时回落默认序列；仍无 → None（待补版本计划）。
    """
    if plan.next_version_id:
        target = db.query(PmwbPbVersionPlan).filter(
            PmwbPbVersionPlan.id == plan.next_version_id,
            PmwbPbVersionPlan.id != plan.id,
            PmwbPbVersionPlan.status.in_(C.ACTIVE_PLAN_STATUSES),
        ).first()
        # 人工指定不得指向自身或更早版本，否则顺延会原地打转 / 倒挂。
        if target is not None and target.release_date and plan.release_date \
                and target.release_date > plan.release_date:
            return serialize_plan(target)

    after = [p for p in _series(db, plan.scope_type, plan.system_name)
             if p.id != plan.id and p.release_date and plan.release_date
             and p.release_date > plan.release_date]
    if after:
        return serialize_plan(after[0])
    if plan.scope_type == "system":
        after_default = [p for p in _series(db, "default", None)
                         if p.release_date and plan.release_date and p.release_date > plan.release_date]
        if after_default:
            return serialize_plan(after_default[0])
    return None


# ── 变更日志 ─────────────────────────────────────────────────
def _affected_count(db: Session) -> int:
    """受本次变更影响的在跟主行数；pb-2 建表前恒为 0，之后自动生效。"""
    try:
        # 必须用 Session 当前持有的 Connection 做 has_table：另开 Engine 连接时
        # Connection.close() 会在 SQLite :memory: 单连接上触发 DBAPI rollback，
        # 把同一事务里尚未提交的 INSERT 一并回滚（2026-11-19 实测 POST 200 但表内 0 行）。
        conn = db.connection()
        if not sa_inspect(conn).has_table("pmwb_pb_track"):
            return 0
        return int(conn.execute(text("SELECT COUNT(*) FROM pmwb_pb_track WHERE active = 1")).scalar() or 0)
    except Exception:
        return 0


def _log(db: Session, plan: PmwbPbVersionPlan, change_type: str, field: str,
         old_value: Any, new_value: Any, operator: str, remark: str = "") -> None:
    db.add(PmwbPbVersionChangeLog(
        plan_id=plan.id,
        version_no=plan.version_no,
        change_type=change_type,
        field=field,
        old_value="" if old_value is None else str(old_value),
        new_value="" if new_value is None else str(new_value),
        affected_count=_affected_count(db),
        operator=_norm(operator) or "system",
        changed_at=now_cn(),
        remark=remark,
    ))


def change_logs(db: Session, plan_id: int) -> List[Dict[str, Any]]:
    rows = (db.query(PmwbPbVersionChangeLog)
            .filter(PmwbPbVersionChangeLog.plan_id == plan_id)
            .order_by(PmwbPbVersionChangeLog.id.desc()).all())
    return [_serialize_log(r) for r in rows]


# ── 校验 / CRUD ──────────────────────────────────────────────
def _validate(db: Session, data: Dict[str, Any], creating: bool) -> Dict[str, Any]:
    out = dict(data)
    scope = _norm(out.get("scope_type") or "system")
    if scope not in dict(C.SCOPE_TYPES):
        raise ValidationException(f"scope_type 非法：{scope}")
    out["scope_type"] = scope

    system_name = _norm(out.get("system_name"))
    if scope == "default":
        out["system_name"] = None
        out["system_verified"] = 1
    else:
        if not system_name:
            raise ValidationException("指定系统计划必须填写系统名")
        opts, degraded = system_options(db)
        if opts and system_name not in opts:
            raise ValidationException(f"系统名「{system_name}」不在人员中台目标系统字典内")
        out["system_name"] = system_name
        # 中台不可达：不静默拒绝，标记待自动补校验（不转人工判定）
        out["system_verified"] = 0 if (degraded or not opts) else 1

    if creating or "version_no" in out:
        if not _norm(out.get("version_no")):
            raise ValidationException("版本标识不能为空")
        out["version_no"] = _norm(out["version_no"])

    if creating or "version_type" in out:
        if out.get("version_type") not in dict(C.VERSION_TYPES):
            raise ValidationException("版本类型非法")
    if creating or "status" in out:
        if out.get("status") not in dict(C.PLAN_STATUSES):
            raise ValidationException("计划状态非法")

    mode = out.get("admit_mode")
    if creating or "admit_mode" in out:
        if mode not in dict(C.ADMIT_MODES):
            raise ValidationException("准入模式非法")
        if mode == "wait_release_n_days" and int(out.get("admit_lead_days") or 0) <= 0:
            out["admit_lead_days"] = C.DEFAULT_ADMIT_LEAD_DAYS
        if mode == "open":
            out["admit_lead_days"] = 0
    if creating or "allow_temp_merge" in out:
        out["allow_temp_merge"] = int(out.get("allow_temp_merge") or 0)
    # 闸门模式必然禁止临时合入，否则提前 N 天准入形同虚设。
    # 决策 #3 的「手工处理」= 单据级例外放行（pb-3），不是放开规则开关；
    # 未准入的默认动作恒为自动顺延。
    if mode == "wait_release_n_days":
        out["allow_temp_merge"] = 0

    if creating and not out.get("release_date"):
        raise ValidationException("计划发布日必填")
    # 派生公式自校验：非法 release_date 会在 derive_deadlines / admit_gate_at 抛出
    if out.get("release_date"):
        C.derive_deadlines(out["release_date"])
        C.admit_gate_at(out["release_date"], mode or "open", int(out.get("admit_lead_days") or 0))
    return out


def _check_duplicate(db: Session, scope: str, system_name: Optional[str], version_no: str,
                     exclude_id: Optional[int] = None) -> None:
    q = db.query(PmwbPbVersionPlan).filter(
        PmwbPbVersionPlan.scope_type == scope,
        PmwbPbVersionPlan.version_no == version_no,
    )
    if scope == "default":
        q = q.filter(PmwbPbVersionPlan.system_name.is_(None))
    else:
        q = q.filter(PmwbPbVersionPlan.system_name == system_name)
    if exclude_id:
        q = q.filter(PmwbPbVersionPlan.id != exclude_id)
    if q.first():
        raise DuplicateException(f"版本标识「{version_no}」在该范围内已存在")


def list_plans(db: Session, scope_type: Optional[str] = None, system_name: Optional[str] = None,
               status: Optional[str] = None, include_cancelled: bool = False) -> Dict[str, Any]:
    q = db.query(PmwbPbVersionPlan)
    if scope_type:
        q = q.filter(PmwbPbVersionPlan.scope_type == scope_type)
    if system_name:
        q = q.filter(PmwbPbVersionPlan.system_name == _norm(system_name))
    if status:
        q = q.filter(PmwbPbVersionPlan.status == status)
    if not include_cancelled:
        q = q.filter(PmwbPbVersionPlan.status != "cancelled")
    rows = q.order_by(PmwbPbVersionPlan.release_date.desc(), PmwbPbVersionPlan.id.desc()).all()
    items = [serialize_plan(r) for r in rows]
    return {
        "items": items,
        "total": len(items),
        "default_count": sum(1 for i in items if i["scope_type"] == "default"),
        "crm_gate_count": sum(1 for i in items if i["admit_mode"] == "wait_release_n_days"),
    }


def get_plan(db: Session, plan_id: int) -> Dict[str, Any]:
    plan = db.query(PmwbPbVersionPlan).filter(PmwbPbVersionPlan.id == plan_id).first()
    if plan is None:
        raise NotFoundException("版本计划不存在")
    data = serialize_plan(plan)
    data["change_logs"] = change_logs(db, plan_id)
    data["next_plan"] = next_plan(db, plan)
    return data


def create_plan(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = _validate(db, payload, creating=True)
    _check_duplicate(db, data["scope_type"], data["system_name"], data["version_no"])
    plan = PmwbPbVersionPlan(
        version_no=data["version_no"],
        scope_type=data["scope_type"],
        system_name=data["system_name"],
        system_verified=data.get("system_verified", 1),
        version_type=data["version_type"],
        release_date=data["release_date"],
        status=data["status"],
        admit_mode=data["admit_mode"],
        admit_lead_days=data["admit_lead_days"],
        allow_temp_merge=data["allow_temp_merge"],
        next_version_id=data.get("next_version_id"),
        remark=data.get("remark") or "",
        created_at=now_cn(),
        updated_at=now_cn(),
    )
    db.add(plan)
    db.flush()
    _log(db, plan, "create", "release_date", "", data["release_date"],
         data.get("operator"), "登记版本计划")
    # commit 前取快照：不依赖 commit 后的 ORM 刷新（SQLite StaticPool 多 session 下
    # db.refresh 会抛 Could not refresh instance，且返回体本就是只读快照）。
    result = serialize_plan(plan)
    db.commit()
    return result


def update_plan(db: Session, plan_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    plan = db.query(PmwbPbVersionPlan).filter(PmwbPbVersionPlan.id == plan_id).first()
    if plan is None:
        raise NotFoundException("版本计划不存在")
    incoming = {k: v for k, v in (payload or {}).items()
                if v is not None and k != "operator" and hasattr(PmwbPbVersionPlan, k)}
    merged = {
        "scope_type": plan.scope_type,
        "system_name": plan.system_name,
        "version_no": plan.version_no,
        "version_type": plan.version_type,
        "status": plan.status,
        "release_date": plan.release_date,
        "admit_mode": plan.admit_mode,
        "admit_lead_days": plan.admit_lead_days,
        "allow_temp_merge": plan.allow_temp_merge,
        "next_version_id": plan.next_version_id,
        "remark": plan.remark,
    }
    merged.update(incoming)
    data = _validate(db, merged, creating=False)
    _check_duplicate(db, data["scope_type"], data["system_name"], data["version_no"], exclude_id=plan_id)

    operator = _norm((payload or {}).get("operator")) or "system"
    for field in C.WATCHED_FIELDS:
        old = getattr(plan, field)
        new = data.get(field)
        old_s = _iso(old) if isinstance(old, date) else ("" if old is None else str(old))
        new_s = _iso(new) if isinstance(new, date) else ("" if new is None else str(new))
        if old_s != new_s:
            _log(db, plan, "update", field, old_s, new_s, operator,
                 "发布日变更将自动重算全部派生截止与准入时点（不落副本）" if field == "release_date" else "")
            setattr(plan, field, new)

    # system_name / scope_type 一经登记不可变；system_verified 只由字典可用性决定，
    # 避免中台临时不可达时把已校验计划降级为「待补校验」。
    for field in ("version_no", "version_type", "remark"):
        if field in data and getattr(plan, field) != data[field]:
            setattr(plan, field, data[field])
    plan.updated_at = now_cn()
    db.flush()
    result = serialize_plan(plan)
    result["change_logs"] = change_logs(db, plan_id)
    result["next_plan"] = next_plan(db, plan)
    db.commit()
    return result
