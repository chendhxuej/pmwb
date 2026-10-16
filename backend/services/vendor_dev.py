"""需求「厂家开发状态」服务（2026-10-16 新增，生产部署环节）。

**本模块是厂家维度的唯一真相源**。全站关于「厂家团队有哪些、每家开发到哪一步、
是否可以触发需求上线」的判定，一律走这里，禁止在前端/插件/路由里另写第二份。

三条铁律（改动前务必读完）：
  1. **厂家清单 = 团队评估中 workload > 0 的系统**。
     唯一实现是 ``active_team_systems()``；前端、插件同步、完成联动、
     ``requirement_stage.list_manual_systems()`` 全部调用它。
  2. **本模块不落 workload**。pmwb_req_vendor_dev 表里**没有**工作量列，
     sa_name/team_name 只是展示用冗余快照。工作量与「是否活跃」一律实时读
     pmwb_requirement_evaluation，避免两处口径打架。
  3. **状态只前进不回退**（幂等 upsert）：插件同步只会把厂家推进到 ``live``，
     已经 ``completed`` 的厂家不会被覆盖回 ``live``。``completed`` 只能由人工确认。

状态取值见 constants/status_registry.py 的 ``vendor_dev`` 域：
pending(待开发)/developing(开发中)/live(已上线)/completed(已完成)。
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from constants import status_registry
from db.models import (
    PmwbReqVendorDev,
    PmwbRequirementEvaluation,
    PmwbRequirementExt,
    SentEmail,
    now_cn,
)
from utils.master_service import master_service_client

VENDOR_DEV_DOMAIN = "vendor_dev"
DEFAULT_DEV_STATUS = "developing"
_PLUGIN_LIVE_STATUS = "live"

# 完成联动：全部活跃厂家置此态时，触发需求级「已上线」
TERMINAL_DEV_STATUS = "completed"

# 组织可被当作「厂家/系统」参与匹配的类型
_SYSTEM_ORG_TYPE = "system"


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _norm(v: Optional[str]) -> str:
    """归一化：去空白、全角空格、大小写不敏感比较用。"""
    return (v or "").replace("　", " ").strip()


def status_label(value: Optional[str]) -> str:
    """厂家开发状态 → 中文标签（唯一源：状态注册表）。"""
    return status_registry.labels_for(VENDOR_DEV_DOMAIN).get(_norm(value), _norm(value))


def week_thursday(d: date) -> date:
    """取 d 所在自然周的周四（**周一为一周起点**）。

    完成联动写入「实际上线日」时用：老大确认口径 = 当周周四。
    """
    monday = d - timedelta(days=d.weekday())
    return monday + timedelta(days=3)


def _is_positive_workload(v: Any) -> bool:
    """workload > 0 判定。0 与 NULL 一律视为「无开发工作量」→ 剔除。"""
    if v is None:
        return False
    try:
        return float(v) > 0
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# 一、厂家清单唯一源
# ---------------------------------------------------------------------------
def active_team_systems(db: Session, req_id: str) -> List[Dict[str, Any]]:
    """**厂家团队的唯一真相源**：团队评估中工作量 > 0 人天的系统。

    规则（老大 2026-10-16 确认）：
      - 取 pmwb_requirement_evaluation WHERE req_id
      - **剔除 workload = 0 或 NULL 的团队**（0 与空一并处理）
      - 按 system_name 去重，sa_name 取首个非空
      - 按 system_name 排序

    Returns:
        [{"system_name": str, "sa_name": str, "workload": float}, ...]
    """
    req_id = _norm(req_id)
    if not req_id:
        return []
    evals = (
        db.query(PmwbRequirementEvaluation)
        .filter(PmwbRequirementEvaluation.req_id == req_id)
        .all()
    )
    sa_map: Dict[str, str] = {}
    wl_map: Dict[str, float] = {}
    for ev in evals:
        sys_name = _norm(ev.system_name)
        if not sys_name:
            continue
        if not _is_positive_workload(ev.workload):
            continue  # ★ 0 人天 / 空 → 剔除，不参与厂家维度
        if sys_name not in sa_map:
            sa_map[sys_name] = _norm(ev.sa_name)
        # 同系统多条评估记录时取最大工作量（保守：任一条 >0 即算活跃）
        try:
            wl = float(ev.workload)
        except (TypeError, ValueError):
            wl = 0.0
        wl_map[sys_name] = max(wl_map.get(sys_name, 0.0), wl)

    return [
        {
            "system_name": s,
            "sa_name": sa_map.get(s, ""),
            "workload": round(wl_map.get(s, 0.0), 2),
        }
        for s in sorted(sa_map.keys())
    ]


def _ensure_evaluations_seeded(db: Session, req_id: str) -> None:
    """团队评估未播种时先播种一次（厂家清单强依赖它）。

    get_evaluations 内部自带「首次访问自动从 sent_emails 播种」的逻辑，
    这里复用即可；失败不影响主流程。
    """
    try:
        from services.requirement import requirement_service

        requirement_service.get_evaluations(db, req_id)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# 人员中台组织映射（「组织名/别名 → 目标系统名」的唯一来源）
# ---------------------------------------------------------------------------
def _org_mapping(org_type: Optional[str] = _SYSTEM_ORG_TYPE) -> Tuple[List[Dict[str, Any]], bool]:
    """读取人员中台的映射索引（带进程内 TTL 缓存，见 master_service._cached）。

    Returns:
        (rows, degraded)
          rows     —— [{"org_name","target","aliases","sort","org_id"}, ...] 按 (sort, id) 升序
                      中台不可达时为 []
          degraded —— True 表示中台不可用（此时 rows 一定为 []）
    """
    index, degraded = master_service_client.org_mapping_index()
    if index is None:
        return [], True
    rows = []
    for item in index:
        if org_type and (item.get("org_type") or "") != org_type:
            continue
        rows.append(
            {
                "org_id": item.get("org_id"),
                "org_name": _norm(item.get("org_name")),
                # 中台口径：target 为空 = 映射到自身组织名
                "target": _norm(item.get("target_system_name")) or _norm(item.get("org_name")),
                "aliases": _norm(item.get("aliases")),
                "sort": item.get("sort") or 0,
            }
        )
    rows.sort(key=lambda r: (r["sort"], r["org_id"] or 0))
    return rows, degraded


# ---------------------------------------------------------------------------
# 二、厂家名 → 系统名 的匹配链（四级）
# ---------------------------------------------------------------------------
def resolve_vendor_system(db: Session, req_id: str, raw_name: str) -> Tuple[Optional[str], str]:
    """把工单标题里解析出的厂家名归一到 system_name。

    四级匹配链（``matched_by`` 取值保持 history 兼容，插件侧零改动）：
      1. system  —— 精确命中该需求团队评估里的系统名
      2. team    —— 命中**人员中台组织名**（system 类且启用）
      3. alias   —— 命中中台组织 aliases（如「电子协议系统」→「电子协议」）
      4. contains—— 唯一包含匹配（兜底系统名不统一，如「XX系统」vs「XX」）
      未命中返回 (None, 'unmatched')，由上层标黄等待人工指定，**不静默丢弃**。

    ⚠ 降级纪律：中台不可达时**跳过 2、3 级**，只用 1、4 级。
      宁可少匹配让人指定，**绝不把「拿不到映射」等同于「空映射」而静默放过去**。

    Returns:
        (system_name | None, matched_by)
    """
    raw = _norm(raw_name)
    if not raw:
        return None, "unmatched"

    # 1) 该需求团队评估里的系统名（含 0 人天的，便于上层区分「命中但已剔除」）
    eval_systems = [
        _norm(r[0])
        for r in db.query(PmwbRequirementEvaluation.system_name)
        .filter(PmwbRequirementEvaluation.req_id == _norm(req_id))
        .all()
        if _norm(r[0])
    ]
    uniq_systems = sorted(set(eval_systems))
    low = {s.lower(): s for s in uniq_systems}
    if raw.lower() in low:
        return low[raw.lower()], "system"

    # 2) + 3) 人员中台组织映射（替代原本地字典 pmwb_vendor_team）
    #    中台不可达时 mapping 退化为空列表 → 两级自然落空，等价于「跳过 2、3 级」
    mapping, _degraded = _org_mapping()
    # 2) 组织名精确命中
    for m in mapping:
        if raw.lower() == _norm(m["org_name"]).lower():
            return _norm(m["target"]), "team"
    # 3) aliases 精确命中 —— 必须逐项 split 比对，绝不能用 LIKE 子串
    for m in mapping:
        for alias in (_norm(m["aliases"]) or "").split(","):
            if alias.strip() and alias.strip().lower() == raw.lower():
                return _norm(m["target"]), "alias"

    # 4) 唯一包含匹配（系统名不统一的兜底）
    contained = [s for s in uniq_systems if raw.lower() in s.lower() or s.lower() in raw.lower()]
    if len(contained) == 1:
        return contained[0], "contains"

    return None, "unmatched"


# ---------------------------------------------------------------------------
# 三、厂家开发状态行
# ---------------------------------------------------------------------------
def _row_to_dict(row: PmwbReqVendorDev, workload: float, is_active: bool) -> Dict[str, Any]:
    st = _norm(row.dev_status) or DEFAULT_DEV_STATUS
    return {
        "id": row.id,
        "req_id": row.req_id,
        "system_name": row.system_name,
        "team_name": row.team_name or "",
        "sa_name": row.sa_name or "",
        "dev_ticket_no": row.dev_ticket_no or "",
        "dev_status": st,
        "dev_status_label": status_label(st),
        "dev_status_tone": (
            status_registry.get_status(VENDOR_DEV_DOMAIN, st).tone
            if status_registry.get_status(VENDOR_DEV_DOMAIN, st)
            else "neutral"
        ),
        "allowed_next": status_registry.allowed_next(VENDOR_DEV_DOMAIN, st),
        "workload": workload,
        "is_active": is_active,
        "source": row.source or "manual",
        "manual": {
            "file_name": row.manual_file_name or "",
            "local_path": row.manual_local_path or "",
            "archived_path": row.manual_archived_path or "",
            "uploaded_at": row.manual_uploaded_at.strftime("%Y-%m-%d %H:%M:%S")
            if row.manual_uploaded_at
            else "",
        },
        "updated_at": row.updated_at.strftime("%Y-%m-%d %H:%M:%S") if row.updated_at else "",
    }


def list_vendor_devs(db: Session, req_id: str) -> Dict[str, Any]:
    """列出需求的厂家开发状态（**实时重算**）。

    - 团队评估未播种时先播种（厂家清单强依赖评估）
    - 活跃系统（workload>0）缺行的**自动补建**（默认 developing，source='auto'）
    - **永不自动删除**：系统被剔除/工作量改 0 的行保留并置 is_active=False
      （尤其保护已 completed 的流转记录不被误删）
    """
    req_id = _norm(req_id)
    _ensure_evaluations_seeded(db, req_id)

    actives = active_team_systems(db, req_id)
    active_wl = {a["system_name"]: a["workload"] for a in actives}
    active_sa = {a["system_name"]: a["sa_name"] for a in actives}

    rows = (
        db.query(PmwbReqVendorDev)
        .filter(PmwbReqVendorDev.req_id == req_id)
        .order_by(PmwbReqVendorDev.id.asc())
        .all()
    )
    have = {_norm(r.system_name): r for r in rows}

    # 自动补建缺失的活跃厂家行
    created = 0
    for sys_name in active_wl:
        if sys_name in have:
            continue
        row = PmwbReqVendorDev(
            req_id=req_id,
            system_name=sys_name,
            sa_name=active_sa.get(sys_name, ""),
            team_name=_team_name_of(db, sys_name),
            dev_status=DEFAULT_DEV_STATUS,
            source="auto",
        )
        db.add(row)
        created += 1
    if created:
        db.commit()
        rows = (
            db.query(PmwbReqVendorDev)
            .filter(PmwbReqVendorDev.req_id == req_id)
            .order_by(PmwbReqVendorDev.id.asc())
            .all()
        )

    result = [
        _row_to_dict(r, active_wl.get(_norm(r.system_name), 0.0), _norm(r.system_name) in active_wl)
        for r in rows
    ]
    # 活跃的排前面，其次按系统名
    result.sort(key=lambda x: (not x["is_active"], x["system_name"]))

    return {
        "req_id": req_id,
        "items": result,
        "active_count": len(actives),
        "total": len(result),
        "auto_created": created,
        "hint": "厂家团队取自「团队评估」中工作量 > 0 人天的系统；0 人天团队不参与上线联动。",
    }


def _team_name_of(db: Session, system_name: str) -> str:
    """按 system_name 反查**主组织名**（展示用，查不到留空，绝不抛异常）。

    主组织 = 人员中台里 target 命中该系统名、按 (sort, id) 升序的第一条。
    多对一时（多个组织映射同一系统名）展示的就是这个「主组织」。
    不用人员数做排序基准 —— 人员进出会让展示名漂移。
    """
    mapping, _degraded = _org_mapping()
    target = _norm(system_name)
    if not target:
        return ""
    for m in mapping:
        if _norm(m["target"]).lower() == target.lower():
            return _norm(m["org_name"])
    return ""


def create_vendor_dev(db: Session, req_id: str, obj_in: Dict[str, Any]) -> Dict[str, Any]:
    """手工新增一个厂家行（老大补充厂家时用）。"""
    req_id = _norm(req_id)
    sys_name = _norm(obj_in.get("system_name"))
    if not sys_name:
        raise ValueError("system_name 不能为空")

    exist = (
        db.query(PmwbReqVendorDev)
        .filter(
            PmwbReqVendorDev.req_id == req_id,
            PmwbReqVendorDev.system_name == sys_name,
        )
        .first()
    )
    if exist:
        raise ValueError(f"该需求下已存在厂家「{sys_name}」")

    st = _norm(obj_in.get("dev_status")) or DEFAULT_DEV_STATUS
    if not status_registry.get_status(VENDOR_DEV_DOMAIN, st):
        raise ValueError(f"非法的厂家开发状态：{st}")

    row = PmwbReqVendorDev(
        req_id=req_id,
        system_name=sys_name,
        team_name=_norm(obj_in.get("team_name")) or _team_name_of(db, sys_name),
        sa_name=_norm(obj_in.get("sa_name")),
        dev_ticket_no=_norm(obj_in.get("dev_ticket_no")),
        dev_status=st,
        source="manual",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    actives = {a["system_name"]: a["workload"] for a in active_team_systems(db, req_id)}
    return _row_to_dict(row, actives.get(sys_name, 0.0), sys_name in actives)


def update_vendor_dev(db: Session, vendor_dev_id: int, obj_in: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """更新厂家行；改状态走注册表流转校验，置 completed 时触发完成联动。"""
    row = db.query(PmwbReqVendorDev).filter(PmwbReqVendorDev.id == vendor_dev_id).first()
    if not row:
        return None

    new_status = obj_in.get("dev_status")
    if new_status is not None:
        new_status = _norm(new_status)
        cur = _norm(row.dev_status) or DEFAULT_DEV_STATUS
        if new_status != cur:
            allowed = status_registry.allowed_next(VENDOR_DEV_DOMAIN, cur)
            if allowed and new_status not in allowed:
                raise ValueError(
                    f"不允许从「{status_label(cur)}」流转到「{status_label(new_status)}」"
                )
            if not status_registry.get_status(VENDOR_DEV_DOMAIN, new_status):
                raise ValueError(f"非法的厂家开发状态：{new_status}")
        row.dev_status = new_status

    for key in ("team_name", "sa_name", "dev_ticket_no"):
        if key in obj_in and obj_in[key] is not None:
            setattr(row, key, _norm(obj_in[key]))

    row.updated_at = now_cn()
    db.commit()
    db.refresh(row)

    finalized = None
    if _norm(row.dev_status) == TERMINAL_DEV_STATUS:
        finalized = _maybe_finalize(db, row.req_id)

    actives = {a["system_name"]: a["workload"] for a in active_team_systems(db, row.req_id)}
    out = _row_to_dict(row, actives.get(_norm(row.system_name), 0.0), _norm(row.system_name) in actives)
    out["finalized"] = finalized
    return out


def delete_vendor_dev(db: Session, vendor_dev_id: int) -> bool:
    row = db.query(PmwbReqVendorDev).filter(PmwbReqVendorDev.id == vendor_dev_id).first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# 四、完成联动（需求 5）
# ---------------------------------------------------------------------------
def _maybe_finalize(db: Session, req_id: str) -> Optional[Dict[str, Any]]:
    """全部**活跃**厂家都 completed 时，把需求置为「已上线」。

    条件（老大 2026-10-16 确认）：
      1. 活跃厂家集（workload>0 的系统）非空；
      2. 集合中每个系统都有厂家行且 dev_status == 'completed'（缺行算未完成）；
      3. **0 人天被剔除的厂家不参与判定**（否则挂个 0 人天团队永远触发不了联动）。

    动作：
      - 跟踪状态 → closed（已上线）
      - 实际上线日 → 当周周四，**仅当 delivered_date 为空时写入**（保护手填数据）

    Returns:
        命中联动时返回 {"finalized": True, "status": "closed", "delivered_date": "YYYY-MM-DD"}；
        未命中返回 None。
    """
    req_id = _norm(req_id)
    actives = active_team_systems(db, req_id)
    if not actives:
        return None

    rows = db.query(PmwbReqVendorDev).filter(PmwbReqVendorDev.req_id == req_id).all()
    status_by_sys = {_norm(r.system_name): _norm(r.dev_status) for r in rows}
    for a in actives:
        if status_by_sys.get(a["system_name"]) != TERMINAL_DEV_STATUS:
            return None  # 仍有活跃厂家未完成

    ext = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == req_id).first()
    # 幂等：已上线就不再重复写
    if ext and _norm(ext.status) == "closed":
        return {
            "finalized": False,
            "skipped": True,
            "reason": "需求已处于「已上线」，跳过重复联动",
        }

    payload: Dict[str, Any] = {"status": "closed"}
    delivered = None
    if ext is None or ext.delivered_date is None:
        delivered = week_thursday(now_cn().date())
        payload["delivered_date"] = delivered

    # 复用既有入口，自动触发 requirement_stage.on_status_changed（记录生产部署环节）
    from services.requirement import requirement_service

    requirement_service.update_ext(db, req_id, payload)

    return {
        "finalized": True,
        "status": "closed",
        "delivered_date": delivered.strftime("%Y-%m-%d") if delivered else None,
    }


# ---------------------------------------------------------------------------
# 五、插件同步（需求 3）
# ---------------------------------------------------------------------------
def _find_req_by_code(db: Session, code: str) -> Optional[str]:
    """开发单号优先：先 dev_ticket_no，再 req_id。"""
    code = _norm(code)
    if not code:
        return None
    row = (
        db.query(SentEmail.req_id)
        .filter(SentEmail.dev_ticket_no == code)
        .order_by(SentEmail.id.desc())
        .first()
    )
    if row and row[0]:
        return row[0]
    row = db.query(SentEmail.req_id).filter(SentEmail.req_id == code).first()
    return row[0] if row and row[0] else None


def _find_req_by_title(db: Session, title: str) -> Optional[str]:
    """需求标题兜底：归一化后 LIKE 包含匹配。"""
    t = _norm(title).replace("关于", "").replace(" ", "")
    if not t:
        return None
    rows = db.query(SentEmail.req_id, SentEmail.req_name).all()
    for req_id, req_name in rows:
        n = _norm(req_name).replace("关于", "").replace(" ", "")
        if t and (t in n or n in t):
            return req_id
    return None


def sync_from_plugin(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    """插件扫描到厂家开发单后同步开发状态 → live（幂等、只前进不回退）。

    payload: {code, vendor, title, force}
        code   —— 标题拆出的编号（开发单号优先）
        vendor —— 标题拆出的厂家团队片段，如「CRM」「订单中心」
        title  —— 标题拆出的需求标题（兜底匹配用）
        force  —— 该厂家已被 0 人天规则剔除时，是否强制同步

    Returns:
        {"success": bool, ...}；失败时带 reason 供插件弹窗提示。
    """
    code = _norm(payload.get("code"))
    raw_vendor = _norm(payload.get("vendor"))
    title = _norm(payload.get("title"))
    force = bool(payload.get("force"))

    req_id = _find_req_by_code(db, code) or _find_req_by_title(db, title)
    if not req_id:
        return {"success": False, "reason": "req_not_found", "message": f"未匹配到需求（编号 {code}）"}

    _ensure_evaluations_seeded(db, req_id)
    system_name, matched_by = resolve_vendor_system(db, req_id, raw_vendor)
    if not system_name:
        return {
            "success": False,
            "reason": "vendor_not_matched",
            "req_id": req_id,
            "vendor": raw_vendor,
            "message": f"厂家「{raw_vendor}」未能匹配到系统，请在插件里指定或补充别名",
        }

    actives = active_team_systems(db, req_id)
    active_wl = {a["system_name"]: a["workload"] for a in actives}
    is_active = system_name in active_wl
    if not is_active and not force:
        return {
            "success": False,
            "reason": "zero_workload",
            "req_id": req_id,
            "system_name": system_name,
            "message": f"系统「{system_name}」在团队评估中工作量为 0，已被规则剔除（可勾选强制同步）",
        }

    row = (
        db.query(PmwbReqVendorDev)
        .filter(
            PmwbReqVendorDev.req_id == req_id,
            PmwbReqVendorDev.system_name == system_name,
        )
        .first()
    )
    if row is None:
        row = PmwbReqVendorDev(
            req_id=req_id,
            system_name=system_name,
            team_name=_team_name_of(db, system_name),
            dev_status=_PLUGIN_LIVE_STATUS,
            source="plugin",
        )
        db.add(row)
    else:
        # ★ 只前进不回退：已 completed 的厂家不被插件覆盖回 live
        if _norm(row.dev_status) != TERMINAL_DEV_STATUS:
            row.dev_status = _PLUGIN_LIVE_STATUS
        row.source = "plugin"

    if code:
        row.dev_ticket_no = code
    active_sa = {a["system_name"]: a["sa_name"] for a in actives}
    if not row.sa_name:
        row.sa_name = active_sa.get(system_name, "")
    row.updated_at = now_cn()
    db.commit()
    db.refresh(row)

    return {
        "success": True,
        "req_id": req_id,
        "system_name": system_name,
        "vendor_dev_id": row.id,
        "dev_status": row.dev_status,
        "dev_status_label": status_label(row.dev_status),
        "matched_by": matched_by,
        "is_active": is_active,
        "forced": bool(force and not is_active),
    }


# ---------------------------------------------------------------------------
# 六、厂家手册落位（需求 4）
# ---------------------------------------------------------------------------
def save_vendor_manual(
    db: Session,
    vendor_dev_id: int,
    filename: str,
    content: bytes,
    base_dir: str,
) -> Optional[Dict[str, Any]]:
    """把插件抓到的厂家操作手册落盘并登记到该厂家行。

    注意：**不复用 PmwbReqManual**（其 unique(req_id, system_name) 是给
    「按系统的操作手册」卡片用的，厂家手册走自己的字段，避免互相覆盖）。
    """
    row = db.query(PmwbReqVendorDev).filter(PmwbReqVendorDev.id == vendor_dev_id).first()
    if not row:
        return None

    safe_sys = "".join(c for c in (row.system_name or "厂家") if c not in r'\/:*?"<>|') or "厂家"
    folder = os.path.join(base_dir, "操作手册", safe_sys)
    os.makedirs(folder, exist_ok=True)
    target = os.path.join(folder, filename)
    with open(target, "wb") as f:
        f.write(content)

    row.manual_file_name = filename
    row.manual_local_path = target
    row.manual_uploaded_at = now_cn()
    row.updated_at = now_cn()
    db.commit()
    db.refresh(row)

    actives = {a["system_name"]: a["workload"] for a in active_team_systems(db, row.req_id)}
    return _row_to_dict(
        row, actives.get(_norm(row.system_name), 0.0), _norm(row.system_name) in actives
    )


# ---------------------------------------------------------------------------
# 七、目标系统名候选集（供配置下拉）
#
# 注：原「厂家别名映射字典 CRUD」（list/create/update/delete_vendor_team）已随
#     pmwb_vendor_team 一并下线 —— 映射唯一的维护入口在人员中台「组织管理」。
# ---------------------------------------------------------------------------
def target_system_options(db: Session) -> Dict[str, Any]:
    """完整候选集 = 中台候选 ∪ 评估表历史 distinct ∪ sent_emails 历史 distinct。

    为什么必须在主后端合并：后两张历史表在 yxtyg_db，中台读不到（也不应跨库）。
    为什么要并入历史值：老工单里出现过的系统名（如已被合并的旧称）也要能选到。

    Returns:
        {"options": [...], "degraded": bool, "master_count": int}
        degraded=True 表示中台不可达，此时 options 只含本地历史值。
    """
    master_opts, degraded = master_service_client.target_system_options()

    history: List[str] = []
    for model in (PmwbRequirementEvaluation, SentEmail):
        try:
            rows = db.query(model.system_name).distinct().all()
        except Exception:  # noqa: BLE001 兼容个别环境下模型字段差异
            rows = []
        history.extend(_norm(r[0]) for r in rows)

    merged: Dict[str, str] = {}
    for name in list(master_opts) + history:
        key = name.lower()
        if name and key not in merged:
            merged[key] = name

    return {
        "options": sorted(merged.values()),
        "degraded": bool(degraded),
        "master_count": len(master_opts),
    }


def org_type_options(db: Session = None) -> List[str]:
    """组织类型合法值。取值域唯一真相源在人员中台，主后端**不落第二份**。"""
    return master_service_client.org_type_options()
