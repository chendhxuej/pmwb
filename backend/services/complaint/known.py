"""客诉「已知问题 / 新增问题」判定（2026-11-04，老大核心 KPI）。

为什么需要这个模块：
  老大对投诉现状页的核心诉求是一句话——**本周客户反馈的问题，是不是已知问题**。
  这个指标（已知问题率）衡量的是组织行为的性质：
    - 已知率低 → 每周都在救新火，根因没被真正消灭，压降无从谈起；
    - 已知率高 → 问题在被持续治理，本周新增只是存量问题的余量释放。
  没有这个判定，投诉现状页就只剩「本周多少单」这种统计，而统计不能指导压降。

判定口径（唯一实现，禁在路由/脚本另写）：
  1. 工单 → 问题实体（**双锚，2026-11-10 修**）：
     a) 根因簇：ticket.rootcause_no（rootcause.py / rootcause_lib.py 写入）→ 问题台账 rootcause_no/nos
     b) 功能模块：pmwb_complaint_ticket_module.module_problem_id → 问题台账 module_problem_id
     两锚任一命中在办问题即视为「已知」；簇锚优先（粒度更细、直达具体缺陷对象）。
  2. **已知** = 已被某个在办问题（open / resolving）收纳 —— 即组织已认账、正在处理；
     **新增** = 未被在办问题收纳（含 candidate 未确认：AI 已识别但组织未认账，仍算新增）。
  3. 既无根因簇、又无模块归类的工单（信息不足 / 未归并 / 未归类）→ known_flag = NULL，
     不参与已知率分母，避免用未分析的单稀释指标。

⚠ 历史坑（2026-11-10 老大反馈「W45 已知命中极少、大量误判为新增」）：
   旧实现只按 rootcause_no 建映射，而 #69 之后问题台账主力锚点是 module_problem_id
   （24 条在办里 12 条无根因簇），这些在办问题完全不参与判定 → W45 已知仅 25 单，
   实际应有约 74 单。**问题实体锚点变了，判定必须跟着变，否则指标失真。**

写入边界：本模块是 ticket.known_flag / known_problem_no 的**唯一写入点**。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

INFLIGHT = ("open", "resolving")


# ── 在办问题 ↔ 问题实体（根因簇 / 功能模块）双锚映射 ──────────
def _inflight_rows(db: Session):
    """在办问题原始行（唯一取数点，供三种映射共用）。"""
    return db.execute(text(
        "SELECT problem_no, title, rootcause_no, rootcause_nos, module_problem_id, "
        "       owner, status, category_l1, last_week "
        "FROM pmwb_complaint_problem "
        "WHERE status IN ('open', 'resolving')"
    )).mappings().all()


def _row_info(r) -> Dict[str, Any]:
    return {
        "problem_no": r["problem_no"], "title": r["title"] or "", "owner": r["owner"] or "",
        "status": r["status"] or "", "category_l1": r["category_l1"] or "",
        "last_week": r["last_week"] or "",
    }


def inflight_cluster_map(db: Session) -> Dict[str, Dict[str, Any]]:
    """在办问题覆盖的根因簇 → 问题信息（簇锚，粒度细）。"""
    out: Dict[str, Dict[str, Any]] = {}
    for r in _inflight_rows(db):
        info = _row_info(r)
        keys: List[str] = []
        if r["rootcause_no"]:
            keys.append(str(r["rootcause_no"]).strip())
        for k in str(r["rootcause_nos"] or "").split(","):
            k = k.strip()
            if k and k not in keys:
                keys.append(k)
        for k in keys:
            out.setdefault(k, info)
    return out


def inflight_module_map(db: Session) -> Dict[str, Dict[str, Any]]:
    """在办问题覆盖的功能模块 → 问题信息（模块锚，2026-11-10 新增）。

    必要性：#69 之后问题台账以 module_problem_id 为主力锚点，只按根因簇判定会漏掉
    一半以上的在办问题（实测 24 条在办中 12 条无根因簇），把已认账的问题误判为新增。
    """
    out: Dict[str, Dict[str, Any]] = {}
    for r in _inflight_rows(db):
        mid = str(r["module_problem_id"] or "").strip()
        if mid:
            out.setdefault(mid, _row_info(r))
    return out


def inflight_problem_map(db: Session) -> Dict[str, Dict[str, Any]]:
    """problem_no → 问题信息（汇总回显用，锚点无关）。"""
    return {r["problem_no"]: _row_info(r) for r in _inflight_rows(db)}


def candidate_cluster_map(db: Session) -> Dict[str, Dict[str, Any]]:
    """待确认候选覆盖的簇 → 候选信息（辅助指标：AI 已识别但未入账）。"""
    rows = db.execute(text(
        "SELECT problem_no, title, rootcause_no, rootcause_nos, module_problem_id, status "
        "FROM pmwb_complaint_problem WHERE status = 'candidate'"
    )).mappings().all()
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        keys = [k.strip() for k in str(r["rootcause_nos"] or "").split(",") if k.strip()]
        if r["rootcause_no"] and str(r["rootcause_no"]).strip() not in keys:
            keys.insert(0, str(r["rootcause_no"]).strip())
        for k in keys:
            out.setdefault(k, {"problem_no": r["problem_no"], "title": r["title"] or "",
                               "status": r["status"]})
    return out


def candidate_module_map(db: Session) -> Dict[str, Dict[str, Any]]:
    """待确认候选取覆盖的功能模块 → 候选信息（辅助指标用）。"""
    rows = db.execute(text(
        "SELECT problem_no, title, module_problem_id, status "
        "FROM pmwb_complaint_problem WHERE status = 'candidate'"
    )).mappings().all()
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        mid = str(r["module_problem_id"] or "").strip()
        if mid:
            out.setdefault(mid, {"problem_no": r["problem_no"], "title": r["title"] or "",
                                 "status": r["status"]})
    return out


# ── 判定与回填 ────────────────────────────────────────────────
def mark(db: Session, weeks: Optional[List[str]] = None, commit: bool = True) -> Dict[str, Any]:
    """回填工单的已知/新增标记（幂等，可反复跑）。

    weeks 为空则对全部工单重判（口径变更后使用）；指定周则只刷这几周。
    判定双锚：根因簇优先，未命中再看工单的功能模块归类（见模块头注释）。
    """
    cmap = inflight_cluster_map(db)
    mmap = inflight_module_map(db)
    # 非缺陷类（如 MP-CONSULT 使用咨询）：本质不是缺陷问题，不进已知率的分子分母
    non_defect = {r[0] for r in db.execute(text(
        "SELECT module_problem_id FROM pmwb_complaint_module_problem WHERE is_defect = 0"))}

    week_cond, params = "", {}
    if weeks:
        marks = ", ".join(f":w{i}" for i in range(len(weeks)))
        week_cond = f" AND t.week IN ({marks})"
        params.update({f"w{i}": w for i, w in enumerate(weeks)})

    # 一次联查带出「根因簇 + 功能模块集合」，避免逐单回查（1582 单量级可接受）
    rows = db.execute(text(
        "SELECT t.id, t.rootcause_no, "
        "       GROUP_CONCAT(tm.module_problem_id ORDER BY tm.module_problem_id) AS mids "
        "FROM pmwb_complaint_ticket t "
        "LEFT JOIN pmwb_complaint_ticket_module tm ON tm.ticket_no = t.ticket_no "
        "WHERE ((t.rootcause_no IS NOT NULL AND t.rootcause_no != '') "
        "       OR tm.module_problem_id IS NOT NULL)"
        f"{week_cond} "
        "GROUP BY t.id, t.rootcause_no"
    ), params).fetchall()

    known = new = consult = 0
    hit_by_module = 0
    for r in rows:
        rc = str(r[1]).strip() if r[1] else ""
        mids = [m.strip() for m in str(r[2] or "").split(",") if m.strip()]
        info = cmap.get(rc) if rc else None
        if not info:
            for mid in mids:
                info = mmap.get(mid)
                if info:
                    hit_by_module += 1
                    break
        if info:
            db.execute(text(
                "UPDATE pmwb_complaint_ticket SET known_flag = 1, known_problem_no = :pn "
                "WHERE id = :i"
            ), {"pn": info["problem_no"], "i": r[0]})
            known += 1
        elif mids and non_defect and all(m in non_defect for m in mids):
            # 全部归类都是非缺陷（咨询/使用操作问题）→ 不参与已知率，避免把咨询当「新增问题」
            db.execute(text(
                "UPDATE pmwb_complaint_ticket SET known_flag = NULL, known_problem_no = NULL "
                "WHERE id = :i"
            ), {"i": r[0]})
            consult += 1
        else:
            db.execute(text(
                "UPDATE pmwb_complaint_ticket SET known_flag = 0, known_problem_no = NULL "
                "WHERE id = :i"
            ), {"i": r[0]})
            new += 1

    # 既无簇又无模块归类的工单：标记清空（不参与已知率分母）
    clear_where = ("NOT EXISTS (SELECT 1 FROM pmwb_complaint_ticket_module tm "
                   "WHERE tm.ticket_no = t.ticket_no) "
                   "AND (t.rootcause_no IS NULL OR t.rootcause_no = '')")
    if weeks:
        marks = ", ".join(f":w{i}" for i in range(len(weeks)))
        clear_where += f" AND t.week IN ({marks})"
    db.execute(text(
        f"UPDATE pmwb_complaint_ticket t SET known_flag = NULL, known_problem_no = NULL "
        f"WHERE {clear_where}"
    ), {f"w{i}": w for i, w in enumerate(weeks or [])})

    if commit:
        db.commit()
    logger.info("已知/新增判定回填：已知 %s（其中模块锚命中 %s）/ 新增 %s / 非缺陷咨询 %s"
                "（在办簇 %s / 在办模块 %s）",
                known, hit_by_module, new, consult, len(cmap), len(mmap))
    return {"known": known, "new": new, "consult": consult, "hit_by_module": hit_by_module,
            "inflight_clusters": len(cmap), "inflight_modules": len(mmap)}


# ── 本周汇总（投诉现状页核心 KPI 数据源）──────────────────────
def summary(db: Session, week: str, rows: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """本周已知/新增汇总。

    rows 可传入 metrics.collect 已查好的本周工单（含 known_flag/rootcause_no），
    省一次全表扫描；不传则自行查询。
    """
    if rows is None:
        rows = [dict(r) for r in db.execute(text(
            "SELECT t.ticket_no, t.known_flag, t.known_problem_no, t.rootcause_no, t.root_cause, "
            "       t.fault_system, t.fault_stage, t.fault_type, t.own_party, t.fix_mode, "
            "       t.rc_status, "
            "       (SELECT GROUP_CONCAT(tm.module_problem_id ORDER BY tm.module_problem_id) "
            "          FROM pmwb_complaint_ticket_module tm "
            "         WHERE tm.ticket_no = t.ticket_no) AS module_ids "
            "FROM pmwb_complaint_ticket t WHERE t.week = :w"
        ), {"w": week}).mappings().all()]

    total = len(rows)
    # 传入的 rows 若没带模块投影（旧调用方），就地补齐，保证「咨询拆分」不失真
    if rows and "module_ids" not in rows[0]:
        rows = [dict(r) for r in rows]
        nos = [r.get("ticket_no") for r in rows if r.get("ticket_no")]
        if nos:
            marks = ", ".join(f":t{i}" for i in range(len(nos)))
            got = {r[0]: r[1] for r in db.execute(text(
                f"SELECT ticket_no, GROUP_CONCAT(module_problem_id ORDER BY module_problem_id) "
                f"FROM pmwb_complaint_ticket_module WHERE ticket_no IN ({marks}) GROUP BY ticket_no"
            ), {f"t{i}": v for i, v in enumerate(nos)})}
            for r in rows:
                r["module_ids"] = got.get(r.get("ticket_no") or "")

    known_rows = [r for r in rows if r.get("known_flag") == 1]
    new_rows = [r for r in rows if r.get("known_flag") == 0]
    null_rows = [r for r in rows if r.get("known_flag") is None]

    # 未判定里再拆出「非缺陷（咨询/使用操作）」——它们不是「新增问题」，不能混进分子分母
    non_defect = {r[0] for r in db.execute(text(
        "SELECT module_problem_id FROM pmwb_complaint_module_problem WHERE is_defect = 0"))}

    def _mids(r) -> List[str]:
        return [m.strip() for m in str(r.get("module_ids") or "").split(",") if m.strip()]

    consult_rows = [r for r in null_rows
                    if non_defect and _mids(r) and all(m in non_defect for m in _mids(r))]
    consult_ids = {id(r) for r in consult_rows}
    unknown_rows = [r for r in null_rows if id(r) not in consult_ids]
    # 已判定的单才进分母（分母可比，指标才不会被未分析数据稀释）
    judged = len(known_rows) + len(new_rows)

    # 双锚：簇锚回显 + 模块锚回显（problem_no 是共同主键，直接按 problem_no 取信息）
    pmap = inflight_problem_map(db)
    cand = candidate_cluster_map(db)
    cand_m = candidate_module_map(db)

    # 已知问题 TOP（按本周命中单量）
    by_problem: Dict[str, Dict[str, Any]] = {}
    for r in known_rows:
        pn = r.get("known_problem_no") or ""
        if not pn:
            continue
        info = pmap.get(pn, {})
        item = by_problem.setdefault(pn, {
            "problem_no": pn, "cnt": 0, "title": info.get("title", ""),
            "owner": info.get("owner", ""), "status": info.get("status", ""),
        })
        item["cnt"] += 1
    known_list = sorted(by_problem.values(), key=lambda x: -x["cnt"])

    # 新增问题簇（本周出现但未被在办问题收纳）→ 直接可作为候选
    mp_names: Dict[str, str] = {}
    if any(r.get("module_ids") for r in new_rows):
        mp_names = {r[0]: r[1] for r in db.execute(text(
            "SELECT module_problem_id, name FROM pmwb_complaint_module_problem"))}
    new_clusters: Dict[str, Dict[str, Any]] = {}
    for r in new_rows:
        rc_no = (r.get("rootcause_no") or "").strip()
        mids = str(r.get("module_ids") or "").strip()
        first_mid = mids.split(",")[0].strip() if mids else ""
        key = rc_no or (f"mp:{first_mid}" if first_mid else f"_noclu_{r.get('ticket_no')}")
        item = new_clusters.setdefault(key, {
            "rootcause_no": rc_no, "module_problem_id": first_mid, "cnt": 0, "title": "",
            "fault_system": "", "fault_stage": "", "fault_type": "", "own_party": "",
            "fix_mode": "", "tickets": [], "in_candidate": False, "cand_problem_no": "",
        })
        item["cnt"] += 1
        item["tickets"].append(r.get("ticket_no") or "")
        if not item["title"]:
            item["title"] = (_cluster_title(db, rc_no) if rc_no else "") \
                or mp_names.get(first_mid, "") or (r.get("root_cause") or "")[:60]
            item["fault_system"] = r.get("fault_system") or ""
            item["fault_stage"] = r.get("fault_stage") or ""
            item["fault_type"] = r.get("fault_type") or ""
            item["own_party"] = r.get("own_party") or ""
            item["fix_mode"] = r.get("fix_mode") or ""
        c = (cand.get(rc_no) if rc_no else None) or (cand_m.get(first_mid) if first_mid else None)
        if c:
            item["in_candidate"] = True
            item["cand_problem_no"] = c["problem_no"]
    new_list = sorted(new_clusters.values(), key=lambda x: -x["cnt"])

    pot_known = sum(
        1 for r in new_rows
        if ((r.get("rootcause_no") or "") in cand)
        or (str(r.get("module_ids") or "").split(",")[0].strip() in cand_m and r.get("module_ids"))
    )
    return {
        "week": week,
        "total": total,
        "judged": judged,
        "known_cnt": len(known_rows),
        "new_cnt": len(new_rows),
        "unknown_cnt": len(unknown_rows),
        # 非缺陷（咨询/使用操作）单：不计入已知率分子分母，单列展示避免被读成「新增问题」
        "consult_cnt": len(consult_rows),
        "defect_total": total - len(consult_rows),
        # 主 KPI：已知问题率（分母=已判定单量，非总单量）
        "known_rate": round(len(known_rows) / judged * 100, 1) if judged else 0.0,
        "new_rate": round(len(new_rows) / judged * 100, 1) if judged else 0.0,
        "coverage_pct": round(judged / total * 100, 1) if total else 0.0,
        # 辅助：AI 已识别但组织未认账（推动入账用）
        "potential_known_cnt": pot_known,
        "inflight_problem_cnt": len(pmap),
        "known_problems": known_list,
        "new_clusters": new_list,
    }


def _cluster_title(db: Session, rc_no: str) -> str:
    row = db.execute(text(
        "SELECT title FROM pmwb_complaint_rootcause WHERE rootcause_no = :n"
    ), {"n": rc_no}).fetchone()
    return (row[0] or "") if row else ""
