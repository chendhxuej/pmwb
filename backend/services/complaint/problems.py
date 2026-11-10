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
        "       fault_type, own_party, fix_mode, status, is_defect "
        f"FROM pmwb_complaint_rootcause WHERE rootcause_no IN ({marks})"
    ), {f"c{i}": v for i, v in enumerate(rc_nos)}).fetchall()
    return {r[0]: {"title": r[1] or "", "description": r[2] or "", "fault_system": r[3] or "",
                   "fault_stage": r[4] or "", "fault_type": r[5] or "",
                   "own_party": r[6] or "", "fix_mode": r[7] or "",
                   "status": r[8] or "", "is_defect": int(r[9] if r[9] is not None else 1)}
            for r in rows}


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
    # 2026-11-10 候选收敛：簇若能被某个「在办模块问题」解释，就并入该台账而不是另立候选。
    # 背景：旧扫描只看根因簇，每周产出与 19 个闭集模块重复的新 problem_no（台账膨胀、措施分散）。
    module_idx = _open_module_map(db)
    rc_module = _cluster_module_map(db, list(stats.keys()), module_idx) if module_idx else {}

    created: List[str] = []
    updated: List[str] = []
    reopened: List[str] = []
    absorbed: List[str] = []
    now_ts = datetime.now()

    for rc_no, st in stats.items():
        cnt = st["cnt"]
        meta = titles.get(rc_no) or {}
        # 咨询/非缺陷簇（is_defect=0）不进台账：这些是业务/操作咨询，不是系统缺陷，
        # 混进台账会把压降空间算虚（如 109 单的「非系统缺陷-使用咨询」垃圾桶簇）。
        # 它们仍在根因库可见、计入咨询类统计，只是不生成候选。
        if not int(meta.get("is_defect", 1)):
            continue
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

        # 候选收敛（2026-11-10）：簇已能被某个在办模块问题解释 → 并入该台账的 rootcause_nos。
        # 这样 19 个闭集模块问题之外的「新簇」才会真正新建候选，台账不再按周膨胀。
        mid = rc_module.get(rc_no)
        if not inflight and mid:
            target = module_idx[mid]
            if dry_run:
                absorbed.append(f"{rc_no}->{target}(dry)")
                continue
            cur = db.execute(text(
                "SELECT rootcause_nos FROM pmwb_complaint_problem WHERE problem_no = :p"
            ), {"p": target}).scalar() or ""
            keys = [k.strip() for k in cur.split(",") if k.strip()]
            if rc_no not in keys:
                keys.append(rc_no)
            db.execute(text(
                "UPDATE pmwb_complaint_problem SET rootcause_nos = :v, updated_at = :t "
                "WHERE problem_no = :p"
            ), {"v": ",".join(keys), "t": now_ts, "p": target})
            absorbed.append(f"{rc_no}->{target}")
            continue

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
    return {"week": week, "created": created, "updated": updated, "reopen": reopened,
            "absorbed": absorbed}


def _open_module_map(db: Session) -> Dict[str, str]:
    """在办模块问题 → 台账编号（候选收敛用；模块锚是新一代归因入口）。"""
    rows = db.execute(text(
        "SELECT module_problem_id, problem_no FROM pmwb_complaint_problem "
        "WHERE status IN ('open', 'resolving') "
        "  AND module_problem_id IS NOT NULL AND module_problem_id <> ''"
    )).fetchall()
    return {r[0]: r[1] for r in rows}


def _cluster_module_map(db: Session, rc_list: List[str],
                        module_idx: Dict[str, str]) -> Dict[str, str]:
    """簇 → 最多数归属的在办模块（只保留能在 module_idx 里找到台账的模块）。

    一次 GROUP BY 查完，避免逐簇回查；同簇多模块取工单量最大者（业务主归属）。
    """
    keys = [k for k in rc_list if k]
    if not keys:
        return {}
    marks = ", ".join(f":c{i}" for i in range(len(keys)))
    rows = db.execute(text(
        f"SELECT t.rootcause_no, tm.module_problem_id, COUNT(*) c "
        f"FROM pmwb_complaint_ticket t "
        f"JOIN pmwb_complaint_ticket_module tm ON tm.ticket_no = t.ticket_no "
        f"WHERE t.rootcause_no IN ({marks}) "
        f"GROUP BY t.rootcause_no, tm.module_problem_id"
    ), {f"c{i}": v for i, v in enumerate(keys)}).fetchall()
    best: Dict[str, tuple] = {}
    for rc, mid, c in rows:
        if mid not in module_idx:
            continue
        if rc not in best or int(c or 0) > best[rc][1]:
            best[rc] = (mid, int(c or 0))
    return {rc: v[0] for rc, v in best.items()}


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
      total_cnt   = 该问题覆盖簇的**全部工单量**（含问题认账前的历史单）
      peak_cnt    = 各周单量最大值
      week_cnt    = 最近一次有单周的单量
      active_weeks= 有单周数
      quiet_weeks = 自最新周向前连续零单周数
      recur_cnt   = is_recur 单量之和
      recur_weeks = 自最新周向前连续（有复发标记）周数

    为什么统计全周期而不是「首见周之后」：历史工单是补导进来的，问题实体的
    first_week 是「认账周」，晚于该簇真实首单周。若按 first_week 截断，total_cnt
    会显著小于工单真值（实测 RC-0001 只有 26/63、RC-0080 只有 12/83），
    报表里的「同类问题累计单量」就失真了。压降有效性另有 go_live 基线口径，不看这里。
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
        rows_of_week[p["id"]] = [
            (w, sum(cnt.get((n, w), 0) for n in nos), sum(rec.get((n, w), 0) for n in nos))
            for w in weeks
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


# ── 台账自愈：同簇重复问题收敛 / 非缺陷问题出账 ────────────────
_STATUS_RANK = {"resolving": 3, "open": 2, "candidate": 1}


def dedupe_inflight(db: Session, dry_run: bool = False) -> Dict:
    """同一根因簇只允许一条在办/候选问题（应用层不变量的存量修复）。

    为什么需要：多次 after_import 叠加历史数据导入，会让同一簇重复建问题——
    实测 RC-0080 挂 3 条、RC-0001 挂 2 条、RC-0618 挂 2 条，台账看着「问题很多很散」，
    已知问题率也被重复计入。本函数按主簇（rootcause_no）归组，保留状态最靠后/
    单量最大的一条，其余置 merged 并迁移措施关联；簇已标记 is_defect=0 的问题
    置 ignored（咨询类不进台账）。

    dry_run=True 只算不写，便于回归与人工预览。
    """
    rows = db.execute(text(
        "SELECT problem_no, rootcause_no, status, total_cnt, id "
        "FROM pmwb_complaint_problem WHERE status IN ('candidate', 'open', 'resolving') "
        "ORDER BY id"
    )).mappings().all()

    groups: Dict[str, List[Dict]] = {}
    for r in rows:
        rc = str(r["rootcause_no"] or "").strip()
        if not rc:
            continue
        groups.setdefault(rc, []).append(dict(r))

    titles = _cluster_titles(db, list(groups.keys()))
    merged: List[Dict] = []
    ignored: List[str] = []

    for rc_no, items in groups.items():
        if not int((titles.get(rc_no) or {}).get("is_defect", 1)):
            # 咨询/非缺陷：整组出账（不进台账，但仍留在根因库）
            for it in items:
                ignored.append(it["problem_no"])
                if dry_run:
                    continue
                # 注意：字符串拼接不能用 `||`（MySQL 里是逻辑或）也不能用 CONCAT（SQLite 无），
                # 统一在 Python 侧拼好再入库
                old_note = db.execute(text(
                    "SELECT note FROM pmwb_complaint_problem WHERE id = :id"), {"id": it["id"]}
                ).scalar() or ""
                marker = "[系统] 所属根因簇为咨询/非缺陷类，不进问题台账"
                new_note = old_note if marker in old_note else (old_note + "\n" + marker if old_note else marker)
                db.execute(text(
                    "UPDATE pmwb_complaint_problem SET status = 'ignored', note = :nt, "
                    "updated_at = :ts WHERE id = :id"
                ), {"nt": new_note, "ts": datetime.now(), "id": it["id"]})
            continue
        if len(items) < 2:
            continue
        # 保留规则必须与 _problem_cluster_index 完全一致（同簇同状态取 id 最小），
        # 否则 assign_tickets 会把工单指回被合并的那条，去重等于白做
        items.sort(key=lambda x: (_STATUS_RANK.get(x["status"], 9) * -1, int(x["id"])))
        keep, others = items[0], items[1:]
        for it in others:
            merged.append({"from": it["problem_no"], "to": keep["problem_no"], "rc": rc_no})
            if dry_run:
                continue
            # 措施关联迁移（冲突则丢弃重复行，避免 uk_cpp_linked 报错）
            for link in db.execute(text(
                "SELECT id, action_no FROM pmwb_complaint_problem_action WHERE problem_no = :p"
            ), {"p": it["problem_no"]}).mappings().all():
                dup = db.execute(text(
                    "SELECT id FROM pmwb_complaint_problem_action "
                    "WHERE problem_no = :p AND action_no = :a"
                ), {"p": keep["problem_no"], "a": link["action_no"]}).first()
                if dup:
                    db.execute(text("DELETE FROM pmwb_complaint_problem_action WHERE id = :id"),
                               {"id": link["id"]})
                else:
                    db.execute(text(
                        "UPDATE pmwb_complaint_problem_action SET problem_no = :p WHERE id = :id"
                    ), {"p": keep["problem_no"], "id": link["id"]})
            db.execute(text(
                "UPDATE pmwb_complaint_ticket SET problem_no = :keep WHERE problem_no = :old"
            ), {"keep": keep["problem_no"], "old": it["problem_no"]})
            db.execute(text(
                "UPDATE pmwb_complaint_problem SET status = 'merged', merged_into = :keep, "
                "updated_at = :ts WHERE id = :id"
            ), {"keep": keep["problem_no"], "ts": datetime.now(), "id": it["id"]})

    if not dry_run:
        # 保留项单量按簇重算，避免合并后计数停在旧值
        refresh = rebuild_counters(db)
        db.commit()
    else:
        refresh = {"updated": 0}
    return {"merged": merged, "ignored": ignored, "counters": refresh.get("updated", 0)}


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
    summary["dedupe"] = {
        "merged": len(dedupe_inflight(db)["merged"]),
    }
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


# ── 候选问题台账：以闭集模块问题为种子（2026-11-05 新归因入口） ──
def seed_from_module_problem(db: Session, dry_run: bool = False,
                             only_defect: bool = True) -> Dict:
    """以 L2 闭集模块问题为种子，生成「待确认候选问题」供人工确认入账。

    设计（对应 #69）：
      - 闭集 `pmwb_complaint_module_problem` 是「主要投诉点」唯一真相源（19 个缺陷类）；
        它已是业务可读、跨表象汇聚、零 LLM 的产物，直接作为问题台账的种子最贴合
        老大「识别投诉问题 → 人工确认 → 安排整改措施」的诉求；
      - 每个缺陷类生成一条 candidate 问题，锚 module_problem_id（取代旧 rootcause 簇锚），
        title 取模块问题中文名，evidence 含工单量/活跃周/首现周/样本单号；
      - 幂等：同 module_problem_id 已存在 candidate/open/resolving/closed 问题则不重建；
      - 咨询类（is_defect=0）默认不进台账（与旧逻辑一致），可通过 only_defect=False 放宽。
    不依赖人工修正即可运行：种子只是候选，未确认前不挂措施、不影响已知问题率。
    """
    mp_rows = db.execute(text(
        "SELECT module_problem_id, name, module, fail_object, fail_nature, "
        "       ticket_cnt, first_week, active_weeks, status, is_defect "
        "FROM pmwb_complaint_module_problem "
        "WHERE status = 'published'"
    )).mappings().all()
    if only_defect:
        mp_rows = [r for r in mp_rows if (int(r["is_defect"]) if r["is_defect"] is not None else 1) == 1]

    # 已锚定的 module_problem_id（任一在办/已闭环状态都视为已生成过）
    existing = set(r[0] for r in db.execute(text(
        "SELECT module_problem_id FROM pmwb_complaint_problem "
        "WHERE module_problem_id IS NOT NULL AND module_problem_id <> ''"
    )).fetchall())

    created: List[str] = []
    skipped: List[str] = []
    now_ts = datetime.now()

    for mp in mp_rows:
        mp_id = mp["module_problem_id"]
        if mp_id in existing:
            skipped.append(mp_id)
            continue
        if dry_run:
            created.append(f"{mp_id}(dry)")
            continue
        # 样本工单（按模块问题映射取前 8 单）
        samples = [r[0] for r in db.execute(text(
            "SELECT t.ticket_no FROM pmwb_complaint_ticket_module tm "
            "JOIN pmwb_complaint_ticket t ON t.ticket_no = tm.ticket_no "
            "WHERE tm.module_problem_id = :mid ORDER BY t.created_time DESC LIMIT 8"
        ), {"mid": mp_id}).fetchall()]
        week = mp["first_week"] or (latest_week(db) or "")
        problem_no = _next_problem_no(db, week or "2026-W44")
        evidence = {
            "module_problem_id": mp_id,
            "ticket_cnt": int(mp["ticket_cnt"] or 0),
            "active_weeks": int(mp["active_weeks"] or 0),
            "first_week": week,
            "sample_tickets": samples,
        }
        db.execute(text("""
            INSERT INTO pmwb_complaint_problem
                (problem_no, title, category_l1, category_l2, rootcause_no, rootcause_nos,
                 module_problem_id, source_type, rule_hits, evidence, status,
                 first_week, last_week, active_weeks, quiet_weeks, week_cnt, peak_cnt,
                 total_cnt, recur_cnt, recur_weeks, created_at, updated_at)
            VALUES
                (:no, :title, :l1, :l2, NULL, NULL, :mid, 'module_seed', 'module_seed',
                 :ev, 'candidate', :wk, :wk, :aw, 0, :cnt, :cnt, :cnt, 0, 0, :now_ts, :now_ts)
        """), {
            "no": problem_no, "title": (mp["name"] or mp_id)[:200],
            "l1": mp["module"] or "", "l2": mp["fail_object"] or mp["fail_nature"] or "",
            "mid": mp_id, "ev": json.dumps(evidence, ensure_ascii=False),
            "wk": week, "aw": int(mp["active_weeks"] or 0),
            "cnt": int(mp["ticket_cnt"] or 0), "now_ts": now_ts,
        })
        created.append(problem_no)
    if not dry_run:
        db.commit()
    return {"total_modules": len(mp_rows), "created": created, "skipped": skipped}


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
def _week_tuple(w: str) -> tuple:
    """'2026-W45' → (2026, 45)；无法解析返回 (0, 0)。跨年也安全（按年+周号比较）。"""
    try:
        y, n = str(w).split("-W")
        return (int(y), int(n))
    except Exception:
        return (0, 0)


def _attach_week_stats(db: Session, items: List[Dict], stat_week: str) -> None:
    """给问题列表补「指定周增量 + 截至该周累计」（2026-11-04 老大要求拆字段）。

    口径（唯一实现，禁别处另算）：
      - week_delta：该问题锚点在 stat_week 当周的新增投诉单量；
      - cum_total ：该问题锚点在 stat_week **及之前**的累计单量（与指定周视角一致）。
    锚点双源：旧 rootcause 簇（rootcause_no/rootcause_nos）+ 新闭集模块问题（module_problem_id），
    按各自映射汇总；一条问题两种锚点不会同时有（种子问题只挂 module_problem_id）。
    """
    rc_to_items: Dict[str, List[Dict]] = {}
    mp_to_items: Dict[str, List[Dict]] = {}
    for it in items:
        it["week_delta"] = 0
        it["cum_total"] = 0
        it["stat_week"] = stat_week
        mid = (it.get("module_problem_id") or "").strip()
        if mid:
            mp_to_items.setdefault(mid, []).append(it)
        nos = {x.strip() for x in f"{it.get('rootcause_nos') or ''},{it.get('rootcause_no') or ''}".split(",") if x.strip()}
        for n in nos:
            rc_to_items.setdefault(n, []).append(it)
    st = _week_tuple(stat_week)
    # 根因簇路径
    if rc_to_items:
        keys = list(rc_to_items.keys())
        marks = ",".join(f":r{i}" for i in range(len(keys)))
        rows = db.execute(text(
            f"SELECT rootcause_no, week, COUNT(*) c FROM pmwb_complaint_ticket "
            f"WHERE rootcause_no IN ({marks}) AND week IS NOT NULL AND week <> '' "
            f"GROUP BY rootcause_no, week"
        ), {f"r{i}": v for i, v in enumerate(keys)}).fetchall()
        for rc, wk, c in rows:
            cnt = int(c or 0)
            for it in rc_to_items.get(rc, []):
                if wk == stat_week:
                    it["week_delta"] += cnt
                if _week_tuple(wk) <= st:
                    it["cum_total"] += cnt
    # 闭集模块问题路径（经逐单映射表聚合）
    if mp_to_items:
        keys = list(mp_to_items.keys())
        marks = ",".join(f":m{i}" for i in range(len(keys)))
        rows = db.execute(text(
            f"SELECT tm.module_problem_id, t.week, COUNT(*) c "
            f"FROM pmwb_complaint_ticket_module tm "
            f"JOIN pmwb_complaint_ticket t ON t.ticket_no = tm.ticket_no "
            f"WHERE tm.module_problem_id IN ({marks}) AND t.week IS NOT NULL AND t.week <> '' "
            f"GROUP BY tm.module_problem_id, t.week"
        ), {f"m{i}": v for i, v in enumerate(keys)}).fetchall()
        for mid, wk, c in rows:
            cnt = int(c or 0)
            for it in mp_to_items.get(mid, []):
                if wk == stat_week:
                    it["week_delta"] += cnt
                if _week_tuple(wk) <= st:
                    it["cum_total"] += cnt


def list_problems(db: Session, status: str = "", week: str = "", l1: str = "",
                  l2: str = "", source_type: str = "", keyword: str = "",
                  owner: str = "", limit: int = 200, offset: int = 0,
                  stat_week: str = "", sort: str = "") -> List[Dict]:
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
    """
    # 指定周口径下须先统计+排序再分页（否则排序只作用于当前页，是假的）
    items = [dict(r) for r in db.execute(text(sql), params).mappings().all()]
    sw = stat_week or latest_week(db)
    if sw and items:
        _attach_week_stats(db, items, sw)
    if sort in ("delta_desc", "delta_asc", "total_desc", "total_asc"):
        by_delta = sort.startswith("delta")
        key = (lambda x: (x.get("week_delta") or 0, x.get("cum_total") or 0)) if by_delta \
            else (lambda x: (x.get("cum_total") or 0, x.get("week_delta") or 0))
        items.sort(key=key, reverse=sort.endswith("desc"))
    return items[int(offset): int(offset) + int(limit)]


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
