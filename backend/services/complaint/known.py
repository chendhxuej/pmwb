"""客诉「已知问题 / 新增问题」判定（2026-11-04，老大核心 KPI）。

为什么需要这个模块：
  老大对投诉现状页的核心诉求是一句话——**本周客户反馈的问题，是不是已知问题**。
  这个指标（已知问题率）衡量的是组织行为的性质：
    - 已知率低 → 每周都在救新火，根因没被真正消灭，压降无从谈起；
    - 已知率高 → 问题在被持续治理，本周新增只是存量问题的余量释放。
  没有这个判定，投诉现状页就只剩「本周多少单」这种统计，而统计不能指导压降。

判定口径（唯一实现，禁在路由/脚本另写）：
  1. 工单 → 根因簇：ticket.rootcause_no（rootcause.py / rootcause_lib.py 写入）
  2. 根因簇 → 问题：problem.rootcause_no / problem.rootcause_nos（problems.py 写入）
  3. **已知** = 该簇已被某个在办问题（open / resolving）收纳 —— 即组织已认账、正在处理；
     **新增** = 未被在办问题收纳（含 candidate 未确认：AI 已识别但组织未认账，仍算新增）。
  4. 无根因簇的工单（信息不足 / 未归并）→ known_flag = NULL，不参与已知率分母，
     避免用未分析的单稀释指标。

写入边界：本模块是 ticket.known_flag / known_problem_no 的**唯一写入点**。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

INFLIGHT = ("open", "resolving")


# ── 在办问题 ↔ 根因簇 映射 ────────────────────────────────────
def inflight_cluster_map(db: Session) -> Dict[str, Dict[str, Any]]:
    """在办问题覆盖的根因簇 → 问题信息（唯一映射实现）。"""
    rows = db.execute(text(
        "SELECT problem_no, title, rootcause_no, rootcause_nos, owner, status, "
        "       category_l1, last_week "
        "FROM pmwb_complaint_problem "
        "WHERE status IN ('open', 'resolving')"
    )).fetchall()
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        info = {
            "problem_no": r[0], "title": r[1] or "", "owner": r[4] or "",
            "status": r[5] or "", "category_l1": r[6] or "", "last_week": r[7] or "",
        }
        keys: List[str] = []
        if r[2]:
            keys.append(str(r[2]).strip())
        for k in str(r[3] or "").split(","):
            k = k.strip()
            if k and k not in keys:
                keys.append(k)
        for k in keys:
            out.setdefault(k, info)
    return out


def candidate_cluster_map(db: Session) -> Dict[str, Dict[str, Any]]:
    """待确认候选覆盖的簇 → 候选信息（辅助指标：AI 已识别但未入账）。"""
    rows = db.execute(text(
        "SELECT problem_no, title, rootcause_no, rootcause_nos, status "
        "FROM pmwb_complaint_problem WHERE status = 'candidate'"
    )).fetchall()
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        keys = [k.strip() for k in str(r[3] or "").split(",") if k.strip()]
        if r[2] and str(r[2]).strip() not in keys:
            keys.insert(0, str(r[2]).strip())
        for k in keys:
            out.setdefault(k, {"problem_no": r[0], "title": r[1] or "", "status": r[4]})
    return out


# ── 判定与回填 ────────────────────────────────────────────────
def mark(db: Session, weeks: Optional[List[str]] = None, commit: bool = True) -> Dict[str, Any]:
    """回填工单的已知/新增标记（幂等，可反复跑）。

    weeks 为空则对全部工单重判（口径变更后使用）；指定周则只刷这几周。
    """
    inflight = inflight_cluster_map(db)

    where, params = "rootcause_no IS NOT NULL AND rootcause_no != ''", {}
    if weeks:
        marks = ", ".join(f":w{i}" for i in range(len(weeks)))
        where += f" AND week IN ({marks})"
        params.update({f"w{i}": w for i, w in enumerate(weeks)})

    rows = db.execute(text(
        f"SELECT id, rootcause_no FROM pmwb_complaint_ticket WHERE {where}"
    ), params).fetchall()

    known = new = 0
    for r in rows:
        info = inflight.get(str(r[1]).strip())
        if info:
            db.execute(text(
                "UPDATE pmwb_complaint_ticket SET known_flag = 1, known_problem_no = :pn "
                "WHERE id = :i"
            ), {"pn": info["problem_no"], "i": r[0]})
            known += 1
        else:
            db.execute(text(
                "UPDATE pmwb_complaint_ticket SET known_flag = 0, known_problem_no = NULL "
                "WHERE id = :i"
            ), {"i": r[0]})
            new += 1

    # 无簇工单：标记清空（不参与已知率分母）
    clear_where = "rootcause_no IS NULL OR rootcause_no = ''"
    if weeks:
        marks = ", ".join(f":w{i}" for i in range(len(weeks)))
        clear_where += f" AND week IN ({marks})"
    db.execute(text(
        f"UPDATE pmwb_complaint_ticket SET known_flag = NULL, known_problem_no = NULL "
        f"WHERE {clear_where}"
    ), {f"w{i}": w for i, w in enumerate(weeks or [])})

    if commit:
        db.commit()
    logger.info("已知/新增判定回填：已知 %s / 新增 %s（在办问题覆盖 %s 簇）",
                known, new, len(inflight))
    return {"known": known, "new": new, "inflight_clusters": len(inflight)}


# ── 本周汇总（投诉现状页核心 KPI 数据源）──────────────────────
def summary(db: Session, week: str, rows: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """本周已知/新增汇总。

    rows 可传入 metrics.collect 已查好的本周工单（含 known_flag/rootcause_no），
    省一次全表扫描；不传则自行查询。
    """
    if rows is None:
        rows = [dict(r) for r in db.execute(text(
            "SELECT ticket_no, known_flag, known_problem_no, rootcause_no, root_cause, "
            "       fault_system, fault_stage, fault_type, own_party, fix_mode, rc_status "
            "FROM pmwb_complaint_ticket WHERE week = :w"
        ), {"w": week}).mappings().all()]

    total = len(rows)
    known_rows = [r for r in rows if r.get("known_flag") == 1]
    new_rows = [r for r in rows if r.get("known_flag") == 0]
    unknown_rows = [r for r in rows if r.get("known_flag") is None]
    # 已判定的单才进分母（分母可比，指标才不会被未分析数据稀释）
    judged = len(known_rows) + len(new_rows)

    inflight = inflight_cluster_map(db)
    cand = candidate_cluster_map(db)

    # 已知问题 TOP（按本周命中单量）
    by_problem: Dict[str, Dict[str, Any]] = {}
    for r in known_rows:
        pn = r.get("known_problem_no") or ""
        if not pn:
            continue
        item = by_problem.setdefault(pn, {
            "problem_no": pn, "cnt": 0,
            "title": inflight.get(r.get("rootcause_no") or "", {}).get("title", ""),
            "owner": inflight.get(r.get("rootcause_no") or "", {}).get("owner", ""),
            "status": inflight.get(r.get("rootcause_no") or "", {}).get("status", ""),
        })
        item["cnt"] += 1
    known_list = sorted(by_problem.values(), key=lambda x: -x["cnt"])

    # 新增问题簇（本周出现但未被在办问题收纳）→ 直接可作为候选
    new_clusters: Dict[str, Dict[str, Any]] = {}
    for r in new_rows:
        rc_no = (r.get("rootcause_no") or "").strip()
        key = rc_no or f"_noclu_{r.get('ticket_no')}"
        item = new_clusters.setdefault(key, {
            "rootcause_no": rc_no, "cnt": 0, "title": "", "fault_system": "",
            "fault_stage": "", "fault_type": "", "own_party": "", "fix_mode": "",
            "tickets": [], "in_candidate": False, "cand_problem_no": "",
        })
        item["cnt"] += 1
        item["tickets"].append(r.get("ticket_no") or "")
        if rc_no and not item["title"]:
            item["title"] = _cluster_title(db, rc_no) or (r.get("root_cause") or "")[:60]
            item["fault_system"] = r.get("fault_system") or ""
            item["fault_stage"] = r.get("fault_stage") or ""
            item["fault_type"] = r.get("fault_type") or ""
            item["own_party"] = r.get("own_party") or ""
            item["fix_mode"] = r.get("fix_mode") or ""
        c = cand.get(rc_no) if rc_no else None
        if c:
            item["in_candidate"] = True
            item["cand_problem_no"] = c["problem_no"]
    new_list = sorted(new_clusters.values(), key=lambda x: -x["cnt"])

    pot_known = sum(1 for r in new_rows
                    if (r.get("rootcause_no") or "") in cand) if cand else 0
    return {
        "week": week,
        "total": total,
        "judged": judged,
        "known_cnt": len(known_rows),
        "new_cnt": len(new_rows),
        "unknown_cnt": len(unknown_rows),
        # 主 KPI：已知问题率（分母=已判定单量，非总单量）
        "known_rate": round(len(known_rows) / judged * 100, 1) if judged else 0.0,
        "new_rate": round(len(new_rows) / judged * 100, 1) if judged else 0.0,
        "coverage_pct": round(judged / total * 100, 1) if total else 0.0,
        # 辅助：AI 已识别但组织未认账（推动入账用）
        "potential_known_cnt": pot_known,
        "inflight_problem_cnt": len({v["problem_no"] for v in inflight.values()}),
        "known_problems": known_list,
        "new_clusters": new_list,
    }


def _cluster_title(db: Session, rc_no: str) -> str:
    row = db.execute(text(
        "SELECT title FROM pmwb_complaint_rootcause WHERE rootcause_no = :n"
    ), {"n": rc_no}).fetchone()
    return (row[0] or "") if row else ""
