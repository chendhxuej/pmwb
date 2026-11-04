"""客诉共性问题闭环引擎 —— 识别、归因、确认、状态联动、闭环建议的唯一实现。

设计定调（2026-10-27 老大确认口径）：
  - 问题=实体、场景=维度、簇=证据、工单=措施的执行载体；
  - 唯一归因键 problem_no（ticket.problem_no 单指针，本模块 assign_tickets 唯一写入）；
  - 识别=自动候选 + 人工确认（candidate 确认后方可关联措施）；
  - 问题↔措施多对多（pmwb_complaint_problem_action）；
  - 措施↔运营工单双向同步（after_issue_status / after_action_status）；
  - 阈值唯一来源 config.py PROBLEM_* 段；证据口径唯一来源 metrics 三个抽提函数。

闭环五环节：周分析(导入+扫描) → 台账管理(确认/合并/忽略) → 措施跟踪 →
后续周验证(recompute) → 闭环确认(closure_suggestions + 人工 closed)。
"""

from __future__ import annotations

import contextvars
import json
from datetime import date, datetime
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from constants import status_registry
from services.complaint import config as C
from services.complaint.ingest import week_key
from services.complaint.metrics import latest_week, prev_week, week_bounds

# 双向同步递归深度守卫（A 触 B、B 触 A 防死循环；>0 时只落库不再派发下游）
_SYNC_DEPTH = contextvars.ContextVar("complaint_sync_depth", default=0)

# 状态联动自动备注标记（幂等：同标记只写一次）
_SYNC_NOTE_MARK = "[自动同步"


# ── 编号与查询工具 ────────────────────────────────────────────
def _next_problem_no(db: Session, week: str) -> str:
    prefix = f"CPB-{week.replace('-', '')}-"
    row = db.execute(text(
        "SELECT problem_no FROM pmwb_complaint_problem WHERE problem_no LIKE :p "
        "ORDER BY problem_no DESC LIMIT 1"
    ), {"p": prefix + "%"}).scalar()
    seq = int(row.split("-")[-1]) + 1 if row else 1
    return f"{prefix}{seq:02d}"


# ── 根因簇聚合（候选识别与归因的唯一数据源）──────────────────
def _cluster_week_stats(db: Session, week: str) -> Dict[str, Dict]:
    """当周按根因簇聚合（唯一聚合实现，供候选识别/归因/重算共用）。

    为什么按簇而不是按场景：二级场景实测平均 7.6 单/桶、最大桶混装 6 类不相关
    问题，用场景做问题实体等于把不同缺陷打成一个问题，压降空间无法量化。

    实现说明：明细拉回 Python 聚合，**不用 MySQL 的 SUBSTRING_INDEX/GROUP_CONCAT**
    ——测试跑 SQLite 没有这些函数，且聚合口径用 Python 表达更直观、跨库一致。
    """
    if not week:
        return {}
    start, end = week_bounds(week)
    rows = db.execute(text(
        "SELECT rootcause_no, ticket_no, is_recur, category_l1, category_l2, "
        "       fault_system, fault_stage, fault_type, own_party, fix_mode "
        "FROM pmwb_complaint_ticket "
        "WHERE rootcause_no IS NOT NULL AND rootcause_no <> '' "
        "  AND created_time >= :s AND created_time < :e ORDER BY id"
    ), {"s": start, "e": end}).mappings().all()

    fields = (("category_l1", "l1"), ("category_l2", "l2"),
              ("fault_system", "fault_system"), ("fault_stage", "fault_stage"),
              ("fault_type", "fault_type"), ("own_party", "own_party"),
              ("fix_mode", "fix_mode"))
    out: Dict[str, Dict] = {}
    for r in rows:
        key = str(r["rootcause_no"])
        it = out.setdefault(key, {
            "rootcause_no": key, "cnt": 0, "recur_cnt": 0, "samples": [],
            "l1": "", "l2": "", "fault_system": "", "fault_stage": "",
            "fault_type": "", "own_party": "", "fix_mode": "",
        })
        it["cnt"] += 1
        if r["is_recur"]:
            it["recur_cnt"] += 1
        if len(it["samples"]) < 8 and r["ticket_no"] not in it["samples"]:
            it["samples"].append(r["ticket_no"])
        for src, dst in fields:
            if not it[dst] and r[src]:
                it[dst] = r[src]
    return out


def _cluster_titles(db: Session, rc_nos: List[str]) -> Dict[str, Dict]:
    if not rc_nos:
        return {}
    marks = ", ".join(f":c{i}" for i in range(len(rc_nos)))
    rows = db.execute(text(
        "SELECT rootcause_no, title, description, fault_system, fault_stage, "
        "       fault_type, own_party, fix_mode, status "
        f"FROM pmwb_complaint_rootcause WHERE rootcause_no IN ({marks})"
    ), {f"c{i}": v for i, v in enumerate(rc_nos)}).fetchall()
    return {r[0]: {"title": r[1] or "", "description": r[2] or "", "fault_system": r[3] or "",
                   "fault_stage": r[4] or "", "fault_type": r[5] or "",
                   "own_party": r[6] or "", "fix_mode": r[7] or "",
                   "status": r[8] or ""} for r in rows}


def _problem_cluster_nos(p: Dict) -> List[str]:
    """问题覆盖的簇编号（rootcause_nos 优先，兜底 rootcause_no）。"""
    nos = [k.strip() for k in str(p.get("rootcause_nos") or "").split(",") if k.strip()]
    main = str(p.get("rootcause_no") or "").strip()
    if main and main not in nos:
        nos.insert(0, main)
    return nos


def _problem_cluster_index(db: Session) -> Dict[str, Dict[str, Dict]]:
    """簇号 → 问题索引（唯一实现；识别扫描的一次性查询，替代逐簇 SQL 匹配）。

    为什么在 Python 侧匹配：簇号存于逗号分隔列表 rootcause_nos，SQL 精确匹配需要
    FIND_IN_SET / FIELD（MySQL 专有，SQLite 测试库无此函数），用 LIKE 又会把
    RC-0001 误配到 RC-00011。问题表规模在百级，全量拉回内存建索引既保证跨库一致，
    也把 scan_candidates 的逐簇查询降为一次。

    返回 {"inflight": {rc: problem}, "closed": {rc: problem}}：
      - inflight 仅 candidate/open/resolving，同簇冲突按 resolving>open>candidate、id 升序取一；
      - closed 用于「已闭环问题本周再现」判定，同簇取最近一条（id 降序）。
    """
    rows = db.execute(text(
        "SELECT id, problem_no, status, rule_hits, evidence, total_cnt, peak_cnt, "
        "       recur_cnt, recur_weeks, last_week, rootcause_no, rootcause_nos "
        "FROM pmwb_complaint_problem "
        "WHERE status IN ('candidate', 'open', 'resolving', 'closed')"
    )).mappings().all()
    prio = {"resolving": 0, "open": 1, "candidate": 2}
    inflight_rows = sorted((r for r in rows if r["status"] != "closed"),
                           key=lambda r: (prio.get(r["status"], 9), r["id"]))
    closed_rows = sorted((r for r in rows if r["status"] == "closed"),
                         key=lambda r: r["id"], reverse=True)
    inflight: Dict[str, Dict] = {}
    closed: Dict[str, Dict] = {}
    for r in inflight_rows:
        for rc_no in _problem_cluster_nos(dict(r)):
            inflight.setdefault(rc_no, dict(r))
    for r in closed_rows:
        for rc_no in _problem_cluster_nos(dict(r)):
            closed.setdefault(rc_no, dict(r))
    return {"inflight": inflight, "closed": closed}



# ── 识别扫描（根因簇口径，幂等） ───────────────────────────────
def scan_candidates(db: Session, week: Optional[str] = None,
                    dry_run: bool = False) -> Dict:
    """每周导入后扫描候选共性问题（唯一识别实现）。

    判定规则（全部落在根因簇上）：
      R1 rootcause_batch  同簇当周 >= RC_BATCH_WEEK_MIN 单 → 批量问题（主力规则）；
      R2 surge            簇当周单量环比 >= PROBLEM_SURGE_PCT 且绝对量 >= PROBLEM_SURGE_MIN；
      R3 recur            簇已被在办问题收纳，本周仍有「复发」标记单。
    幂等：同簇已有 candidate/open/resolving 问题 → 累加证据与单量，不新建。
    """
    week = week or latest_week(db)
    if not week:
        return {"week": "", "created": [], "updated": [], "reopen": []}

    stats = _cluster_week_stats(db, week)
    prev = _cluster_week_stats(db, prev_week(week))
    titles = _cluster_titles(db, list(stats.keys()))
    index = _problem_cluster_index(db)

    created: List[str] = []
    updated: List[str] = []
    reopened: List[str] = []
    now_ts = datetime.now()

    for rc_no, st in stats.items():
        cnt = st["cnt"]
        hits: List[str] = []
        evidence: Dict = {
            "week": week, "cnt": cnt, "rootcause_no": rc_no,
            "fault_system": st["fault_system"], "fault_stage": st["fault_stage"],
            "fault_type": st["fault_type"],
        }
        # R1 批量根因簇
        if cnt >= C.RC_BATCH_WEEK_MIN:
            hits.append("rootcause_batch")
            evidence["batch_min"] = C.RC_BATCH_WEEK_MIN
        # R2 环比激增
        prev_cnt = (prev.get(rc_no) or {}).get("cnt", 0)
        if prev_cnt and cnt >= C.PROBLEM_SURGE_MIN:
            wow = round((cnt - prev_cnt) / prev_cnt * 100, 1)
            if wow >= C.PROBLEM_SURGE_PCT:
                hits.append("surge")
                evidence["wow"] = wow
                evidence["prev_cnt"] = prev_cnt
        elif not prev_cnt and cnt >= max(C.PROBLEM_SURGE_MIN, C.RC_BATCH_WEEK_MIN):
            # 新出现的簇（上周 0 单）且量级达到批量线，视作激增
            hits.append("surge")
            evidence["wow"] = None
            evidence["prev_cnt"] = 0
        # R3 复发（仅对已认账的问题成立）
        inflight = index["inflight"].get(rc_no)
        if st["recur_cnt"] and inflight and inflight["status"] in ("open", "resolving"):
            hits.append("recur")
            evidence["recur_cnt"] = st["recur_cnt"]

        if not hits:
            continue
        evidence["sample_tickets"] = st["samples"]
        rule_hits = ",".join(h for h in C.PROBLEM_SOURCE_STRENGTH if h in hits)
        source_type = rule_hits.split(",")[0]
        title = (titles.get(rc_no) or {}).get("title") or f"根因簇 {rc_no}"

        if dry_run:  # 只读预演：任何分支都不得写库（含在办问题的累加分支）
            if inflight:
                updated.append(inflight["problem_no"])
            elif index["closed"].get(rc_no):
                reopened.append(index["closed"][rc_no]["problem_no"])
            else:
                created.append(f"{rc_no}(dry)")
            continue

        if inflight:
            # 累计口径只在「首见该周」时累加，重复扫描/重复导入幂等
            first_sight = inflight.get("last_week") != week
            old_hits = set((inflight.get("rule_hits") or "").split(",")) - {""}
            new_hits = old_hits | set(hits)
            new_evidence = _merge_evidence(inflight.get("evidence"), evidence)
            recur_weeks = inflight.get("recur_weeks") or 0
            if first_sight and st["recur_cnt"]:
                recur_weeks += 1
            db.execute(text("""
                UPDATE pmwb_complaint_problem
                SET rule_hits = :rh, source_type = :st, evidence = :ev,
                    last_week = :wk, week_cnt = :cnt,
                    total_cnt = total_cnt + :add_cnt,
                    peak_cnt = :peak,
                    recur_cnt = recur_cnt + :add_rc, recur_weeks = :rw,
                    active_weeks = active_weeks + :add_aw, quiet_weeks = 0,
                    updated_at = :now_ts
                WHERE id = :id
            """), {"rh": ",".join(h for h in C.PROBLEM_SOURCE_STRENGTH if h in new_hits),
                    "st": source_type, "ev": json.dumps(new_evidence, ensure_ascii=False),
                    "wk": week, "cnt": cnt,
                    "add_cnt": cnt if first_sight else 0,
                    "add_rc": st["recur_cnt"] if first_sight else 0,
                    "rw": recur_weeks,
                    "add_aw": 1 if first_sight else 0,
                    "peak": max(inflight.get("peak_cnt") or 0, cnt),
                    "now_ts": now_ts, "id": inflight["id"]})
            updated.append(inflight["problem_no"])
            continue

        # 已闭环问题本周再现 → 置 reopen_flag 待人工确认重开（不自动新建）
        closed = index["closed"].get(rc_no)
        if closed:
            db.execute(text("""
                UPDATE pmwb_complaint_problem
                SET reopen_flag = 1, quiet_weeks = 0, last_week = :wk, week_cnt = :cnt,
                    updated_at = :now_ts
                WHERE id = :id
            """), {"wk": week, "cnt": cnt, "now_ts": now_ts, "id": closed["id"]})
            reopened.append(closed["problem_no"])
            continue

        problem_no = _next_problem_no(db, week)
        db.execute(text("""
            INSERT INTO pmwb_complaint_problem
                (problem_no, title, category_l1, category_l2, rootcause_no, rootcause_nos,
                 source_type, rule_hits, evidence, status, first_week, last_week,
                 active_weeks, quiet_weeks, week_cnt, peak_cnt, total_cnt,
                 recur_cnt, recur_weeks, created_at, updated_at)
            VALUES
                (:no, :title, :l1, :l2, :rc, :rc, :st, :rh, :ev, 'candidate',
                 :wk, :wk, 1, 0, :cnt, :cnt, :cnt, :rw_cnt, :rw, :now_ts, :now_ts)
        """), {"no": problem_no, "title": title[:200], "l1": st["l1"], "l2": st["l2"],
                "rc": rc_no, "st": source_type, "rh": rule_hits,
                "ev": json.dumps(evidence, ensure_ascii=False), "wk": week,
                "cnt": cnt, "rw_cnt": st["recur_cnt"],
                "rw": 1 if st["recur_cnt"] else 0, "now_ts": now_ts})
        created.append(problem_no)

    if not dry_run:
        db.commit()
    return {"week": week, "created": created, "updated": updated, "reopen": reopened}


def _merge_evidence(old_evidence: Optional[str], new_evidence: Dict) -> Dict:
    """在办问题累加证据快照（保留历史周段落，只留近 12 周）。"""
    if old_evidence:
        try:
            old = json.loads(old_evidence)
        except (TypeError, ValueError):
            old = {}
        weeks = old.get("weeks") if isinstance(old, dict) else None
        if not weeks:
            weeks = [old] if old else []
        weeks.append(dict(new_evidence))
        return {"weeks": weeks[-12:]}
    return new_evidence


# ── 归因（ticket.problem_no 唯一写入点） ──────────────────────
def assign_tickets(db: Session, week: Optional[str] = None) -> Dict:
    """按根因簇归属回写工单 problem_no（幂等：先清空本周再回写）。

    优先级：①在办问题（open/resolving）②候选中未确认问题。
    簇未挂任何问题 → NULL（这些单即「新增问题」，由 known.py 判定）。
    """
    week = week or latest_week(db)
    if not week:
        return {"week": "", "assigned": 0}
    rows = db.execute(text(
        "SELECT id, rootcause_no, problem_no FROM pmwb_complaint_ticket "
        "WHERE week = :wk"
    ), {"wk": week}).fetchall()
    problems = db.execute(text(
        "SELECT problem_no, status, rootcause_no, rootcause_nos "
        "FROM pmwb_complaint_problem "
        "WHERE status IN ('candidate', 'open', 'resolving') ORDER BY id"
    )).mappings().all()

    inflight_p: Dict[str, str] = {}
    candidate_p: Dict[str, str] = {}
    for p in problems:
        for rc_no in _problem_cluster_nos(dict(p)):
            if p["status"] in ("open", "resolving"):
                inflight_p.setdefault(rc_no, p["problem_no"])
            else:
                candidate_p.setdefault(rc_no, p["problem_no"])

    updates = []
    for tid, rc_no, cur in rows:
        target = None
        key = (rc_no or "").strip()
        if key:
            target = inflight_p.get(key) or candidate_p.get(key)
        if target != cur:
            updates.append({"id": tid, "pno": target})
    if updates:
        db.execute(text(
            "UPDATE pmwb_complaint_ticket SET problem_no = :pno WHERE id = :id"
        ), updates)
        db.commit()
    return {"week": week, "assigned": len(updates)}


# ── 派生计数重建（自愈：把累计/峰值/活跃周按工单真值整体重算） ──
def rebuild_counters(db: Session) -> Dict:
    """按「簇 × 周」工单真值重建问题的派生计数（幂等，可随时执行）。

    为什么需要：total_cnt / peak_cnt / active_weeks / recur_cnt / quiet_weeks 都是
    **派生字段**，scan_candidates 只做增量累加。一旦同一周被扫描两次（重复导入、
    手工重跑、修数脚本），累加型字段就会虚高且无法回退——派生数据必须有能从
    工单重建的路径，否则没有唯一真相源。

    重建口径（与 recompute 的周轨迹一致）：
      total_cnt   = 首见周起各周该簇单量之和
      peak_cnt    = 各周单量最大值
      week_cnt    = 最近一次有单周的单量
      active_weeks= 有单周数
      quiet_weeks = 自最新周向前连续零单周数
      recur_cnt   = 首见周起 is_recur 单量之和
      recur_weeks = 自最新周向前连续（有复发标记）周数
    """
    rows = db.execute(text(
        "SELECT rootcause_no, week, COUNT(*) c, "
        "       SUM(CASE WHEN is_recur = 1 THEN 1 ELSE 0 END) r "
        "FROM pmwb_complaint_ticket "
        "WHERE rootcause_no IS NOT NULL AND rootcause_no <> '' "
        "  AND week IS NOT NULL AND week <> '' "
        "GROUP BY rootcause_no, week"
    )).fetchall()
    cnt: Dict[tuple, int] = {}
    rec: Dict[tuple, int] = {}
    for rc_no, wk, c, r in rows:
        cnt[(str(rc_no), wk)] = int(c or 0)
        rec[(str(rc_no), wk)] = int(r or 0)
    weeks = sorted({wk for _, wk in cnt})

    ps = db.execute(text(
        "SELECT id, problem_no, status, first_week, rootcause_no, rootcause_nos "
        "FROM pmwb_complaint_problem"
    )).mappings().all()
    rows_of_week: Dict[int, list] = {}
    for p in ps:
        nos = _problem_cluster_nos(dict(p))
        fw = p["first_week"] or ""
        rows_of_week[p["id"]] = [
            (w, sum(cnt.get((n, w), 0) for n in nos), sum(rec.get((n, w), 0) for n in nos))
            for w in weeks if w >= fw
        ]
    now_ts = datetime.now()
    updated = 0
    for p in ps:
        per_week = rows_of_week[p["id"]]
        if not per_week:
            continue
        total = sum(c for _, c, _ in per_week)
        peak = max(c for _, c, _ in per_week)
        active = sum(1 for _, c, _ in per_week if c > 0)
        recur_total = sum(r for _, _, r in per_week)
        last = next((w for w, c, _ in reversed(per_week) if c > 0), p["first_week"])
        week_cnt = next((c for w, c, _ in per_week if w == last), 0)
        quiet = 0
        for _, c, _ in reversed(per_week):
            if c > 0:
                break
            quiet += 1
        recur_weeks = 0
        for _, _, r in reversed(per_week):
            if r == 0:
                break
            recur_weeks += 1
        db.execute(text("""
            UPDATE pmwb_complaint_problem
            SET total_cnt = :total, peak_cnt = :peak, week_cnt = :wcnt, last_week = :last,
                active_weeks = :active, quiet_weeks = :quiet,
                recur_cnt = :rcnt, recur_weeks = :rw, updated_at = :now_ts
            WHERE id = :id
        """), {"total": total, "peak": peak, "wcnt": week_cnt, "last": last,
                "active": active, "quiet": quiet, "rcnt": recur_total,
                "rw": recur_weeks, "now_ts": now_ts, "id": p["id"]})
        updated += 1
    db.commit()
    return {"updated": updated, "weeks": len(weeks)}


# ── 周轨迹重算（累计口径只在首见该周时累加，重复导入幂等） ────
def recompute(db: Session, week: Optional[str] = None) -> Dict:
    """按问题覆盖的根因簇重算周轨迹（簇口径唯一实现）。"""
    week = week or latest_week(db)
    if not week:
        return {"week": "", "updated": 0}
    stats = _cluster_week_stats(db, week)
    rows = db.execute(text(
        "SELECT id, problem_no, rootcause_no, rootcause_nos, status, last_week, "
        "       total_cnt, peak_cnt, active_weeks, quiet_weeks, recur_cnt, recur_weeks "
        "FROM pmwb_complaint_problem "
        "WHERE status IN ('candidate', 'open', 'resolving', 'closed')"
    )).mappings().all()
    now_ts = datetime.now()
    updated = 0
    for p in rows:
        nos = _problem_cluster_nos(dict(p))
        cnt = sum((stats.get(n) or {}).get("cnt", 0) for n in nos)
        recur_w = sum((stats.get(n) or {}).get("recur_cnt", 0) for n in nos)
        first_sight = p["last_week"] != week  # 累计口径只在首见该周时累加
        sets = ["week_cnt = :cnt", "last_week = :wk", "updated_at = :now_ts"]
        params: Dict = {"cnt": cnt, "wk": week, "now_ts": now_ts, "id": p["id"]}
        if p["status"] == "closed":
            if cnt > 0:
                sets += ["reopen_flag = CASE WHEN :rc > 0 THEN 1 ELSE reopen_flag END",
                         "quiet_weeks = 0"]
                params["rc"] = recur_w
        elif first_sight:
            sets += ["total_cnt = total_cnt + :cnt", "peak_cnt = :peak"]
            params["peak"] = max(p["peak_cnt"] or 0, cnt)
            if cnt > 0:
                sets += ["active_weeks = active_weeks + 1", "quiet_weeks = 0"]
            else:
                sets += ["quiet_weeks = quiet_weeks + 1"]
            if recur_w > 0:
                sets += ["recur_cnt = recur_cnt + :rc", "recur_weeks = :rw", "quiet_weeks = 0"]
                params["rc"] = recur_w
                params["rw"] = p["recur_weeks"] + 1
            else:
                sets += ["recur_weeks = 0"]
        db.execute(text(
            f"UPDATE pmwb_complaint_problem SET {', '.join(sets)} WHERE id = :id"
        ), params)
        updated += 1
    db.commit()
    return {"week": week, "updated": updated}


def after_import(db: Session, weeks: Optional[List[str]] = None) -> Dict:
    """每周导入后的固定后处理：扫描候选 → 回写归因 → 重算周轨迹 → 纠正派生计数。

    末尾的 rebuild_counters 是「结构上防漂移」：增量累加与全量重建各跑一次，
    耗时在百毫秒级，但保证重复导入/手工重扫不会把 total_cnt 这类派生值顶高。
    """
    weeks = weeks or ([latest_week(db)] if latest_week(db) else [])
    summary = {"weeks": [], "created": [], "updated": [], "reopen": [], "assigned": 0}
    for w in sorted(w for w in weeks if w):
        scan = scan_candidates(db, week=w)
        assign = assign_tickets(db, week=w)
        recompute(db, week=w)
        summary["weeks"].append(w)
        summary["created"] += scan["created"]
        summary["updated"] += scan["updated"]
        summary["reopen"] += scan["reopen"]
        summary["assigned"] += assign["assigned"]
    summary["rebuilt"] = rebuild_counters(db)["updated"]
    return summary


# ── 人工确认 / 合并 / 忽略 ────────────────────────────────────
def get_problem(db: Session, problem_no: str) -> Optional[Dict]:
    row = db.execute(text(
        "SELECT * FROM pmwb_complaint_problem WHERE problem_no = :no"
    ), {"no": problem_no}).mappings().first()
    if not row:
        return None
    out = dict(row)
    out["actions"] = linked_actions(db, problem_no)
    return out


def linked_actions(db: Session, problem_no: str) -> List[Dict]:
    rows = db.execute(text("""
        SELECT l.action_no, l.is_primary, l.linked_at, l.note,
               a.title, a.category_l2, a.owner, a.status, a.due_date, a.go_live_date,
               a.baseline_cnt, a.target_drop_pct, a.last_week_cnt, a.actual_drop_pct,
               a.issue_no
        FROM pmwb_complaint_problem_action l
        JOIN pmwb_complaint_action a ON a.action_no = l.action_no
        WHERE l.problem_no = :no
        ORDER BY l.is_primary DESC, l.linked_at
    """), {"no": problem_no}).mappings().all()
    return [dict(r) for r in rows]


def confirm(db: Session, problem_no: str, decision: str, owner: str = "",
            merged_into: str = "", note: str = "", confirm_by: str = "") -> Dict:
    """候选确认：open（入账）/ merge（合并）/ ignore（忽略）。仅 candidate 可确认。"""
    p = get_problem(db, problem_no)
    if not p:
        raise ValueError(f"问题不存在：{problem_no}")
    if p["status"] != "candidate":
        raise ValueError(f"仅待确认候选可确认，当前状态：{p['status']}")
    now_ts = datetime.now()

    if decision == "open":
        if not owner:
            raise ValueError("入账必须指定责任人 owner")
        db.execute(text("""
            UPDATE pmwb_complaint_problem
            SET status = 'open', owner = :owner, confirm_by = :by, confirm_at = :at, note = :note
            WHERE problem_no = :no
        """), {"owner": owner, "by": confirm_by, "at": now_ts,
                "note": note or None, "no": problem_no})
    elif decision == "ignore":
        db.execute(text(
            "UPDATE pmwb_complaint_problem SET status = 'ignored', confirm_by = :by, "
            "confirm_at = :at, note = :note WHERE problem_no = :no"
        ), {"by": confirm_by, "at": now_ts, "note": note or None, "no": problem_no})
        db.execute(text(
            "UPDATE pmwb_complaint_ticket SET problem_no = NULL WHERE problem_no = :no"
        ), {"no": problem_no})
    elif decision == "merge":
        target = get_problem(db, merged_into)
        if not target:
            raise ValueError(f"合并目标不存在：{merged_into}")
        if merged_into == problem_no:
            raise ValueError("合并目标不能是自身")
        if target["status"] not in ("candidate", "open", "resolving"):
            raise ValueError(f"合并目标须为在办问题，当前状态：{target['status']}")
        # 归因改写 + 计数吸收
        db.execute(text(
            "UPDATE pmwb_complaint_ticket SET problem_no = :t WHERE problem_no = :s"
        ), {"t": merged_into, "s": problem_no})
        db.execute(text("""
            UPDATE pmwb_complaint_problem
            SET total_cnt = total_cnt + :tc, recur_cnt = recur_cnt + :rc,
                peak_cnt = :pc, first_week = :fw, rule_hits = :rh,
                updated_at = :now_ts
            WHERE problem_no = :no
        """), {"tc": p["total_cnt"], "rc": p["recur_cnt"],
                "pc": max(target.get("peak_cnt") or 0, p["peak_cnt"] or 0),
                "fw": min(p["first_week"], target["first_week"]) if target.get("first_week") else p["first_week"],
                "rh": _merge_rule_hits(p.get("rule_hits") or "", target.get("rule_hits") or ""),
                "now_ts": now_ts, "no": merged_into})
        db.execute(text(
            "UPDATE pmwb_complaint_problem SET status = 'merged', merged_into = :t, "
            "confirm_by = :by, confirm_at = :at, note = :note WHERE problem_no = :no"
        ), {"t": merged_into, "by": confirm_by, "at": now_ts,
            "note": note or None, "no": problem_no})
        # 关联行迁移
        for la in p.get("actions") or []:
            link_action(db, merged_into, la["action_no"], linked_by=confirm_by or "merge",
                        note="合并自动迁移", _skip_status_check=True)
    else:
        raise ValueError(f"未知 decision：{decision}（open/merge/ignore）")
    db.commit()
    return get_problem(db, problem_no if decision != "merge" else merged_into)


def _merge_rule_hits(a: str, b: str) -> str:
    merged = set(filter(None, a.split(","))) | set(filter(None, b.split(",")))
    return ",".join(h for h in C.PROBLEM_SOURCE_STRENGTH if h in merged)


# ── 问题↔措施 多对多 ─────────────────────────────────────────
def link_action(db: Session, problem_no: str, action_no: str, is_primary: bool = False,
                linked_by: str = "", note: str = "",
                _skip_status_check: bool = False) -> Dict:
    p = db.execute(text(
        "SELECT status, category_l2 FROM pmwb_complaint_problem WHERE problem_no = :no"
    ), {"no": problem_no}).mappings().first()
    if not p:
        raise ValueError(f"问题不存在：{problem_no}")
    if not _skip_status_check:
        if p["status"] == "candidate":
            raise ValueError("候选问题须先确认入账，才能关联措施")
        if p["status"] in ("merged", "ignored"):
            raise ValueError(f"问题状态 {p['status']} 不允许关联措施")
    exists = db.execute(text(
        "SELECT 1 FROM pmwb_complaint_action WHERE action_no = :no"
    ), {"no": action_no}).scalar()
    if not exists:
        raise ValueError(f"措施不存在：{action_no}")
    if is_primary:
        db.execute(text(
            "UPDATE pmwb_complaint_problem_action SET is_primary = 0 WHERE problem_no = :no"
        ), {"no": problem_no})
    dup = db.execute(text(
        "SELECT id FROM pmwb_complaint_problem_action "
        "WHERE problem_no = :pno AND action_no = :ano"
    ), {"pno": problem_no, "ano": action_no}).scalar()
    if dup:
        db.execute(text(
            "UPDATE pmwb_complaint_problem_action "
            "SET is_primary = :pri, linked_by = :by, note = :note WHERE id = :id"
        ), {"pri": 1 if is_primary else 0, "by": linked_by or None,
            "note": note or None, "id": dup})
    else:
        db.execute(text("""
            INSERT INTO pmwb_complaint_problem_action
                (problem_no, action_no, is_primary, linked_by, linked_at, note)
            VALUES (:pno, :ano, :pri, :by, :at, :note)
        """), {"pno": problem_no, "ano": action_no, "pri": 1 if is_primary else 0,
               "by": linked_by or None, "at": datetime.now(), "note": note or None})
    db.commit()
    warning = ""
    a_l2 = db.execute(text(
        "SELECT category_l2 FROM pmwb_complaint_action WHERE action_no = :no"
    ), {"no": action_no}).scalar()
    if a_l2 and p["category_l2"] and a_l2 != p["category_l2"]:
        warning = f"措施场景（{a_l2}）与问题锚点场景（{p['category_l2']}）不一致，请确认"
    return {"problem_no": problem_no, "action_no": action_no, "warning": warning}


def unlink_action(db: Session, problem_no: str, action_no: str) -> None:
    db.execute(text(
        "DELETE FROM pmwb_complaint_problem_action "
        "WHERE problem_no = :pno AND action_no = :ano"
    ), {"pno": problem_no, "ano": action_no})
    db.commit()


# ── 状态流转（status_registry 唯一校验） ─────────────────────
def update_status(db: Session, problem_no: str, target: str,
                  payload: Optional[Dict] = None) -> Dict:
    payload = payload or {}
    p = get_problem(db, problem_no)
    if not p:
        raise ValueError(f"问题不存在：{problem_no}")
    current = p["status"]
    allowed = status_registry.allowed_next("complaint_problem", current)
    if target not in allowed:
        raise ValueError(f"状态流转不合法：{current} → {target}（允许：{allowed or '无'}）")
    merged = {**p, **{k: v for k, v in payload.items() if v not in (None, "")}}
    missing = [f for f in status_registry.required_fields("complaint_problem", target)
               if not merged.get(f)]
    if missing:
        raise ValueError(f"进入该状态缺必填字段：{', '.join(missing)}")

    sets = ["status = :target", "updated_at = :now_ts"]
    params: Dict = {"target": target, "no": problem_no, "now_ts": datetime.now()}
    if payload.get("owner"):
        sets.append("owner = :owner")
        params["owner"] = payload["owner"]
    if payload.get("note") is not None:
        sets.append("note = :note")
        params["note"] = payload["note"]
    if target == "closed":
        sets.append("closed_at = :cat")
        params["cat"] = datetime.now()
        if payload.get("closed_week"):
            sets.append("closed_week = :cw")
            params["cw"] = payload["closed_week"]
        db.execute(text(
            "UPDATE pmwb_complaint_ticket SET problem_no = NULL WHERE problem_no = :no"
        ), {"no": problem_no})  # 闭环后本周新单不再归因到已闭环问题
    if target == "resolving" and current == "closed":
        sets.append("reopen_flag = 0")  # 人工确认重开
    db.execute(text(
        f"UPDATE pmwb_complaint_problem SET {', '.join(sets)} WHERE problem_no = :no"
    ), params)
    db.commit()
    return get_problem(db, problem_no)


# ── 闭环建议 ─────────────────────────────────────────────────
def closure_suggestions(db: Session) -> List[Dict]:
    """自动建议（只读，不改状态）：人工确认后才 closed。"""
    from services.complaint.actions import week_count
    rows = db.execute(text(
        "SELECT * FROM pmwb_complaint_problem WHERE status IN ('open', 'resolving')"
    )).mappings().all()
    out: List[Dict] = []
    for p in rows:
        actions_ = linked_actions(db, p["problem_no"])
        if not actions_:
            continue
        sts = {a["status"] for a in actions_}
        if not sts <= {"effective", "cancelled"} or "effective" not in sts:
            continue
        if p["recur_weeks"] > 0:
            continue
        if p["quiet_weeks"] < C.PROBLEM_CLOSE_QUIET_WEEKS:
            continue
        primary = next((a for a in actions_ if a["is_primary"]), actions_[0])
        if primary.get("baseline_cnt") and p["week_cnt"] is not None:
            limit = primary["baseline_cnt"] * (1 - (primary.get("target_drop_pct") or 50) / 100)
            if p["week_cnt"] > limit:
                continue
        out.append({
            "problem_no": p["problem_no"], "title": p["title"],
            "category_l2": p["category_l2"], "week_cnt": p["week_cnt"],
            "quiet_weeks": p["quiet_weeks"], "owner": p["owner"],
            "primary_action": primary["action_no"],
            "reason": f"关联措施全部验证有效，连续 {p['quiet_weeks']} 周零复发",
        })
    return out


# ── 台账查询 ─────────────────────────────────────────────────
def list_problems(db: Session, status: str = "", week: str = "", l1: str = "",
                  l2: str = "", source_type: str = "", keyword: str = "",
                  owner: str = "", limit: int = 200, offset: int = 0) -> List[Dict]:
    conds = ["1 = 1"]
    params: Dict = {}
    if status:
        sts = [s.strip() for s in status.split(",") if s.strip()]
        keys = []
        for i, s in enumerate(sts):
            params[f"s{i}"] = s
            keys.append(f":s{i}")
        conds.append(f"p.status IN ({', '.join(keys)})")
    if week:
        conds.append("(p.last_week = :wk OR p.first_week = :wk)")
        params["wk"] = week
    if l1:
        conds.append("p.category_l1 = :l1")
        params["l1"] = l1
    if l2:
        conds.append("p.category_l2 = :l2")
        params["l2"] = l2
    if source_type:
        conds.append("p.source_type = :st")
        params["st"] = source_type
    if owner:
        conds.append("p.owner LIKE :owner")
        params["owner"] = f"%{owner}%"
    if keyword:
        conds.append("(p.title LIKE :kw OR p.problem_no LIKE :kw)")
        params["kw"] = f"%{keyword}%"
    sql = f"""
        SELECT p.*,
               (SELECT COUNT(*) FROM pmwb_complaint_problem_action l
                 WHERE l.problem_no = p.problem_no) AS action_cnt,
               (SELECT COUNT(*) FROM pmwb_complaint_problem_action l
                 JOIN pmwb_complaint_action a ON a.action_no = l.action_no
                 WHERE l.problem_no = p.problem_no AND a.status = 'effective') AS effective_cnt
        FROM pmwb_complaint_problem p
        WHERE {' AND '.join(conds)}
        ORDER BY CASE p.status
                     WHEN 'candidate' THEN 0 WHEN 'open' THEN 1 WHEN 'resolving' THEN 2
                     WHEN 'closed' THEN 3 WHEN 'ignored' THEN 4 ELSE 5 END,
                 p.updated_at DESC
        LIMIT :limit OFFSET :offset
    """
    params.update({"limit": int(limit), "offset": int(offset)})
    return [dict(r) for r in db.execute(text(sql), params).mappings().all()]


def weekly_trajectory(db: Session, problem_no: str, weeks: int = 12) -> List[Dict]:
    """问题周度轨迹（近 N 周，按根因簇统计——与归并锚点同口径）。"""
    p = db.execute(text(
        "SELECT rootcause_no, rootcause_nos, first_week FROM pmwb_complaint_problem "
        "WHERE problem_no = :no"
    ), {"no": problem_no}).mappings().first()
    if not p:
        return []
    from services.complaint.actions import week_count
    from services.complaint.metrics import recent_weeks
    latest = latest_week(db)
    if not latest:
        return []
    nos = _problem_cluster_nos(dict(p))
    out = []
    for w in recent_weeks(latest, weeks):
        cnt = week_count(db, nos, w) if nos else 0
        out.append({"week": w, "cnt": cnt,
                    "active": w >= (p["first_week"] or "9999")})
    return out


def list_for_report(db: Session, week: str) -> List[Dict]:
    """周报第七章问题台账表数据（只读，不进 metrics 保 12 项口径纯净）。"""
    rows = db.execute(text("""
        SELECT p.problem_no, p.title, p.category_l1, p.category_l2, p.status,
               p.first_week, p.active_weeks, p.week_cnt, p.total_cnt,
               p.recur_cnt, p.reopen_flag, p.owner, p.conclusion,
               (SELECT COUNT(*) FROM pmwb_complaint_problem_action l
                 JOIN pmwb_complaint_action a ON a.action_no = l.action_no
                 WHERE l.problem_no = p.problem_no AND a.status = 'effective') AS effective_cnt,
               (SELECT COUNT(*) FROM pmwb_complaint_problem_action l
                 WHERE l.problem_no = p.problem_no) AS action_cnt
        FROM pmwb_complaint_problem p
        WHERE p.last_week = :wk OR p.status IN ('open', 'resolving')
        ORDER BY CASE p.status
                     WHEN 'open' THEN 0 WHEN 'resolving' THEN 1 WHEN 'candidate' THEN 2
                     WHEN 'closed' THEN 3 WHEN 'ignored' THEN 4 ELSE 5 END,
                 p.week_cnt DESC
    """), {"wk": week}).mappings().all()
    return [dict(r) for r in rows]


# ══ 措施 ↔ 运营工单 双向状态同步（唯一实现；写入口各自挂 after_* 钩子） ══
#
# 同步规则（关键校验点）：
#   1. 双方状态机合法：一律走 status_registry.allowed_next，禁抄近路直接 UPDATE；
#   2. 工单存在且 source=complaint_weekly，否则静默跳过（不卷入手工工单）；
#   3. 幂等：old==new 直接返回；note 固定标记 _SYNC_NOTE_MARK 防重复书写；
#   4. 循环防护：_SYNC_DEPTH 深度守卫 + 同步只单向推进（除显式回退规则）；
#   5. 多措施挂同一工单：逐条独立尝试，一条失败不阻塞其余（收集 warnings）；
#   6. 一端缺失全跳过不报错。


def _related_action_nos(db: Session, issue_id: int, issue_no: str) -> List[str]:
    rows = db.execute(text(
        "SELECT action_no FROM pmwb_complaint_action WHERE issue_id = :iid"
    ), {"iid": issue_id}).fetchall()
    if not rows and issue_no:
        rows = db.execute(text(
            "SELECT action_no FROM pmwb_complaint_action WHERE issue_no = :ino"
        ), {"ino": issue_no}).fetchall()
    return [r[0] for r in rows]


def _find_issue(db: Session, issue_id: Optional[int], issue_no: Optional[str]):
    from db.models import PmwbOperationIssue
    if issue_id:
        return db.get(PmwbOperationIssue, issue_id)
    if issue_no:
        return db.query(PmwbOperationIssue).filter(
            PmwbOperationIssue.issue_no == issue_no).first()
    return None


def _append_note(db: Session, action_no: str, text_: str) -> None:
    """追加同步备注（幂等：同标记只写一次）。"""
    row = db.execute(text(
        "SELECT note FROM pmwb_complaint_action WHERE action_no = :no"
    ), {"no": action_no}).scalar()
    existing = row or ""
    if _SYNC_NOTE_MARK in text_ and _SYNC_NOTE_MARK in existing:
        return
    merged = f"{existing}；{text_}" if existing else text_
    db.execute(text(
        "UPDATE pmwb_complaint_action SET note = :note, updated_at = :now_ts "
        "WHERE action_no = :no"
    ), {"note": merged, "now_ts": datetime.now(), "no": action_no})
    db.commit()


def after_issue_status(db: Session, issue, old_status: str, new_status: str) -> List[str]:
    """运营工单状态变更 → 下游措施联动（operation.update_status commit 后调用）。

    返回 warnings（联动失败不阻断工单本身，绝不抛异常）。
    """
    warnings: List[str] = []
    if old_status == new_status:
        return warnings
    if getattr(issue, "source", "") != "complaint_weekly":
        return warnings
    if _SYNC_DEPTH.get() > 0:
        return warnings
    token = _SYNC_DEPTH.set(1)
    try:
        for action_no in _related_action_nos(db, issue.id, issue.issue_no):
            warnings += _sync_issue_to_action(db, action_no, issue, new_status)
        return warnings
    except Exception as e:  # 联动兜底：不阻断工单主流程
        warnings.append(f"工单→措施联动异常：{e}")
        return warnings
    finally:
        _SYNC_DEPTH.reset(token)


def _sync_issue_to_action(db: Session, action_no: str, issue, new_status: str) -> List[str]:
    from services.complaint import get_action, update_status as _action_update
    warnings: List[str] = []
    a = get_action(db, action_no)
    if not a:
        return warnings
    mark = f"{_SYNC_NOTE_MARK}:工单 {issue.issue_no}]"
    resolved_word = "关闭" if new_status == "closed" else "解决"

    if new_status in ("resolved", "closed") and a["status"] in ("planned", "in_progress"):
        missing = [f for f in ("owner", "go_live_date") if not a.get(f)]
        if missing:
            warnings.append(
                f"{action_no} 工单已{resolved_word}但缺 {'/'.join(missing)}，待补后进验证")
            _append_note(db, action_no,
                         f"{mark} 工单已{resolved_word}，待补 {'/'.join(missing)} 后进验证")
            return warnings
        try:
            _action_update(db, action_no, "verifying",
                           {"note": f"{mark} 工单已{resolved_word}，自动进入验证"})
        except ValueError as e:
            warnings.append(f"{action_no} 自动进入验证失败：{e}")
    elif (new_status == "processing" and a["status"] == "verifying"):
        try:
            _action_update(db, action_no, "in_progress",
                           {"note": f"{mark} 工单回退处理中，措施重新推进"})
        except ValueError as e:
            warnings.append(f"{action_no} 回退失败：{e}")
    return warnings


def after_action_status(db: Session, action_no: str, old_status: str,
                        new_status: str) -> List[str]:
    """措施状态变更 → 运营工单推进（complaint.update_status commit 后调用）。

    - go-live（进 verifying）：工单单次最多推进一档 pending→processing / processing→verify；
    - 生效（进 effective）：工单 pending/processing/verify → resolved；
    - cancelled/ineffective 不同步工单（防误关）。
    """
    warnings: List[str] = []
    if old_status == new_status:
        return warnings
    if new_status not in ("verifying", "effective"):
        return warnings
    if _SYNC_DEPTH.get() > 0:
        return warnings
    token = _SYNC_DEPTH.set(1)
    try:
        from services.operation import operation_issue_service
        a = db.execute(text(
            "SELECT issue_id, issue_no FROM pmwb_complaint_action WHERE action_no = :no"
        ), {"no": action_no}).mappings().first()
        if not a or (not a["issue_id"] and not a["issue_no"]):
            return warnings
        issue = _find_issue(db, a["issue_id"], a["issue_no"])
        if not issue or getattr(issue, "source", "") != "complaint_weekly":
            return warnings
        cur = issue.status
        if new_status == "verifying":
            nxt = {"pending": "processing", "processing": "verify"}.get(cur)
        else:  # effective
            nxt = "resolved" if cur in ("pending", "processing", "verify") else None
        if not nxt:
            if cur == "suspended":
                warnings.append(f"工单 {issue.issue_no} 已挂起，未自动推进（请人工恢复）")
            return warnings
        allowed = status_registry.allowed_next("operation", cur)
        if nxt not in allowed:
            warnings.append(f"工单 {issue.issue_no} 流转 {cur}→{nxt} 不合法（允许：{allowed}）")
            return warnings
        operation_issue_service.update_status(db, issue.id, nxt)
        return warnings
    except Exception as e:  # 联动兜底
        warnings.append(f"措施→工单联动异常：{e}")
        return warnings
    finally:
        _SYNC_DEPTH.reset(token)
