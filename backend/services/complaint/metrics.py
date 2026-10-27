"""客诉周度指标计算 —— 12 项指标的**唯一计算实现**。

所有指标公式只在本文件出现一次，报告、导出、后续看板一律调用这里，
禁止在模板或其它脚本里重算（避免第二份口径）。

指标清单（口径见 docs/客诉工单分析体系规范.md）：
  1  总量 / 日均
  2  周环比（WOW）
  3  问题性质结构（一级）
  4  问题场景结构（二级 TOP）
  5  批量异常簇数 / 批量簇工单占比
  6  批量组织修复率（簇内出现批量处置话术）
  7  平均经手环节（处理意见条数）
  8  重复派单率（派单次数 > 1）
  9  首轮返工率（首条意见即索要素材）
  10 互推外部率 / 挂起率
  11 滞留单数（超 N 天未完结）
  12 同类复发率（措施上线后同场景再现）
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.complaint import config as C

_OPINION_RE = re.compile(r"处理意见")


# ── 周工具 ────────────────────────────────────────────────────
def week_bounds(week: str) -> tuple[datetime, datetime]:
    """'2026-W44' → (周一 00:00, 下周一 00:00)。"""
    year, w = week.split("-W")
    monday = date.fromisocalendar(int(year), int(w), 1)
    start = datetime(monday.year, monday.month, monday.day)
    return start, start + timedelta(days=7)


def prev_week(week: str) -> str:
    start, _ = week_bounds(week)
    d = start - timedelta(days=7)
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def recent_weeks(week: str, n: int = 8) -> List[str]:
    """返回截至 week 的最近 n 个自然周（含自身，正序）。"""
    out = [week]
    cur = week
    for _ in range(n - 1):
        cur = prev_week(cur)
        out.append(cur)
    return list(reversed(out))


def latest_week(db: Session) -> str:
    row = db.execute(text(
        "SELECT week FROM pmwb_complaint_ticket WHERE week IS NOT NULL AND week <> '' "
        "ORDER BY week DESC LIMIT 1"
    )).scalar()
    return row or ""


# ── 证据口径抽提（共性问题识别 problems.py 与 collect 共用，防第二份实现） ──
def scene_week_counts(db: Session, week: str) -> Dict[str, int]:
    """某自然周各二级场景单量 {l2: cnt}（周单量唯一实现）。"""
    start, end = week_bounds(week)
    rows = db.execute(text(
        "SELECT category_l2, COUNT(*) AS cnt FROM pmwb_complaint_ticket "
        "WHERE category_l2 IS NOT NULL AND category_l2 <> '' "
        "AND created_time >= :s AND created_time < :e "
        "GROUP BY category_l2"
    ), {"s": start, "e": end}).fetchall()
    return {r[0]: int(r[1]) for r in rows}


def scene_wow(db: Session, week: str) -> Dict[str, Dict]:
    """某自然周各二级场景环比 {l2: {cur, prev, wow}}（环比唯一实现）。"""
    pw = prev_week(week)
    cur = scene_week_counts(db, week)
    prev = scene_week_counts(db, pw)
    out: Dict[str, Dict] = {}
    for l2 in set(cur) | set(prev):
        c, p = cur.get(l2, 0), prev.get(l2, 0)
        wow = round((c - p) / p * 100, 1) if p else None
        out[l2] = {"cur": c, "prev": p, "wow": wow}
    return out


def daily_clusters(db: Session, weeks: Optional[List[str]] = None) -> List[Dict]:
    """批量簇聚合唯一实现：读取派生字段 cluster_key（由 ingest.refresh_derived 打标），
    按 cluster_key 聚合返回 [{key, l2, date, cnt, tickets}]。
    problems.R1 判定与周报批量专题共用；调用方须先完成 refresh_derived。
    """
    f_week = ""
    params: Dict = {}
    if weeks:
        for i, w in enumerate(weeks):
            params[f"w{i}"] = w
        in_list = ",".join(f":w{i}" for i in range(len(weeks)))
        f_week = f" AND week IN ({in_list})"
    rows = db.execute(text(
        "SELECT ticket_no, category_l2, cluster_key FROM pmwb_complaint_ticket "
        "WHERE cluster_key IS NOT NULL AND cluster_key <> ''" + f_week
    ), params).fetchall()
    clusters: Dict[str, Dict] = {}
    for no, l2, ck in rows:
        c = clusters.setdefault(ck, {"key": ck, "l2": l2, "date": ck.split("@")[-1],
                                     "cnt": 0, "tickets": []})
        c["cnt"] += 1
        c["tickets"].append(no)
    return sorted(clusters.values(), key=lambda x: -x["cnt"])


# ── 文本判定 ──────────────────────────────────────────────────
def _opinion_count(solution: str) -> int:
    return len(_OPINION_RE.findall(solution or ""))


def _first_opinion(solution: str) -> str:
    s = solution or ""
    idx = s.find("处理意见")
    return s[idx: idx + 400] if idx >= 0 else s[:400]


def _has_any(text_: str, keywords) -> bool:
    return any(k in (text_ or "") for k in keywords)


# ── 主入口 ────────────────────────────────────────────────────
def collect(db: Session, week: Optional[str] = None) -> Dict:
    week = week or latest_week(db)
    if not week:
        raise ValueError("库中无客诉数据，请先执行 ingest 导入")

    start, end = week_bounds(week)
    pw = prev_week(week)
    p_start, p_end = week_bounds(pw)

    rows = db.execute(text("""
        SELECT id, ticket_no, created_time, city, handler, dispatch_count, status,
               category_l1, category_l2, cluster_key, is_batch, is_recur,
               content, solution_history, linked_issue_no
        FROM pmwb_complaint_ticket
        WHERE created_time >= :s AND created_time < :e
        ORDER BY created_time
    """), {"s": start, "e": end}).mappings().all()

    total = len(rows)
    prev_total = db.execute(text(
        "SELECT COUNT(*) FROM pmwb_complaint_ticket WHERE created_time >= :s AND created_time < :e"
    ), {"s": p_start, "e": p_end}).scalar() or 0
    # 上周有效数据天数（导出往往只覆盖部分上周，天不足则环比不可比）
    prev_days = db.execute(text(
        "SELECT COUNT(DISTINCT DATE(created_time)) FROM pmwb_complaint_ticket "
        "WHERE created_time >= :s AND created_time < :e"
    ), {"s": p_start, "e": p_end}).scalar() or 0

    # 结构（二级场景单量走唯一实现，防第二份口径）
    by_l1: Dict[str, int] = {}
    by_city: Dict[str, int] = {}
    by_handler: Dict[str, int] = {}
    for r in rows:
        by_l1[r["category_l1"] or "未分类"] = by_l1.get(r["category_l1"] or "未分类", 0) + 1
        by_city[r["city"] or "未知"] = by_city.get(r["city"] or "未知", 0) + 1
        by_handler[r["handler"] or "未分配"] = by_handler.get(r["handler"] or "未分配", 0) + 1
    by_l2: Dict[str, int] = scene_week_counts(db, week)

    l2_to_l1 = {r[0]: r[1] for r in db.execute(text(
        "SELECT name, parent_name FROM pmwb_complaint_category WHERE level = 2"
    )).fetchall()}

    def _sorted(d: Dict[str, int], limit: int = 0):
        items = sorted(d.items(), key=lambda kv: -kv[1])
        if limit:
            items = items[:limit]
        return [{"name": k, "cnt": v, "pct": round(v / total * 100, 1) if total else 0.0}
                for k, v in items]

    # 批量异常簇
    clusters: Dict[str, Dict] = {}
    for r in rows:
        ck = r["cluster_key"]
        if not ck:
            continue
        c = clusters.setdefault(ck, {
            "key": ck, "l2": r["category_l2"], "cnt": 0, "fixed": False,
            "dates": set(), "cities": set(), "tickets": [],
        })
        c["cnt"] += 1
        if r["created_time"]:
            c["dates"].add(r["created_time"].date().isoformat())
        if r["city"]:
            c["cities"].add(r["city"])
        c["tickets"].append(r["ticket_no"])
        sol = r["solution_history"] or ""
        if _has_any(sol, C.BATCH_FIX_KEYWORDS) and not _has_any(sol, C.BATCH_TRANSFER_KEYWORDS):
            c["fixed"] = True

    cluster_list = []
    for c in sorted(clusters.values(), key=lambda x: -x["cnt"]):
        cluster_list.append({
            "key": c["key"],
            "l2": c["l2"],
            "cnt": c["cnt"],
            "fixed": c["fixed"],
            "date": min(c["dates"]) if c["dates"] else "",
            "cities": "、".join(sorted(c["cities"])) if c["cities"] else "",
            "tickets": ", ".join(c["tickets"][:6]) + (" 等" if len(c["tickets"]) > 6 else ""),
        })

    batch_cnt = sum(c["cnt"] for c in clusters.values())
    fixed_cnt = sum(1 for c in clusters.values() if c["fixed"])

    # 时效与效率
    long_chain = repeat_dispatch = rework = pushout = pending = retention = unclosed = 0
    opinion_sum = 0
    for r in rows:
        oc = _opinion_count(r["solution_history"])
        opinion_sum += oc
        if oc >= C.LONG_CHAIN_OPINIONS:
            long_chain += 1
        if (r["dispatch_count"] or 1) > 1:
            repeat_dispatch += 1
        first = _first_opinion(r["solution_history"])
        if _has_any(first, C.REWORK_KEYWORDS):
            rework += 1
        if _has_any(first, C.PUSHOUT_KEYWORDS):
            pushout += 1
        if _has_any(r["solution_history"], C.PENDING_KEYWORDS):
            pending += 1
        if (r["status"] or "") not in C.TERMINAL_STATUSES:
            unclosed += 1
            if r["created_time"] and (end - r["created_time"]).days > C.RETENTION_DAYS:
                retention += 1

    def pct(n: int) -> float:
        return round(n / total * 100, 1) if total else 0.0

    recur_cnt = sum(1 for r in rows if r["is_recur"])
    recur_l2: Dict[str, int] = {}
    for r in rows:
        if r["is_recur"] and r["category_l2"]:
            recur_l2[r["category_l2"]] = recur_l2.get(r["category_l2"], 0) + 1

    # 日趋势
    daily: Dict[str, int] = {}
    cur = start
    while cur < end:
        daily[cur.date().isoformat()] = 0
        cur += timedelta(days=1)
    for r in rows:
        if r["created_time"]:
            k = r["created_time"].date().isoformat()
            daily[k] = daily.get(k, 0) + 1

    # 近 8 周趋势
    weeks8 = recent_weeks(week, 8)
    trend = []
    for w in weeks8:
        s, e = week_bounds(w)
        cnt = db.execute(text(
            "SELECT COUNT(*) FROM pmwb_complaint_ticket WHERE created_time >= :s AND created_time < :e"
        ), {"s": s, "e": e}).scalar() or 0
        bcnt = db.execute(text(
            "SELECT COUNT(*) FROM pmwb_complaint_ticket "
            "WHERE created_time >= :s AND created_time < :e AND is_batch = 1"
        ), {"s": s, "e": e}).scalar() or 0
        trend.append({"week": w, "total": int(cnt), "batch": int(bcnt)})

    # 措施台账
    actions = db.execute(text("""
        SELECT a.action_no, a.title, a.category_l2, a.owner, a.due_date, a.go_live_date, a.status,
               a.baseline_cnt, a.target_drop_pct, a.last_week_cnt, a.actual_drop_pct, a.issue_no,
               (SELECT l.problem_no FROM pmwb_complaint_problem_action l
                 WHERE l.action_no = a.action_no ORDER BY l.id LIMIT 1) AS problem_no
        FROM pmwb_complaint_action a
        ORDER BY FIELD(a.status,'ineffective','verifying','in_progress','planned','effective','cancelled'), a.due_date
    """)).mappings().all()
    action_by_status: Dict[str, int] = {}
    for a in actions:
        action_by_status[a["status"]] = action_by_status.get(a["status"], 0) + 1

    done = action_by_status.get("effective", 0)
    action_total = len(actions)
    action_completion = round(done / action_total * 100, 1) if action_total else 0.0

    days = (end - start).days
    prev_partial = int(prev_days) < 5
    wow = None if (prev_partial or not prev_total) else round((total - prev_total) / prev_total * 100, 1)

    return {
        "week": week,
        "range": f"{start:%Y-%m-%d} ~ {(end - timedelta(days=1)):%Y-%m-%d}",
        "total": total,
        "daily_avg": round(total / days, 1) if days else 0,
        "prev_week": pw,
        "prev_total": int(prev_total),
        "prev_days": int(prev_days),
        "prev_partial": prev_partial,
        "wow_pct": wow,
        "by_l1": _sorted(by_l1),
        "by_l2": [dict(x, l1=l2_to_l1.get(x["name"], "")) for x in _sorted(by_l2, 12)],
        "by_city": _sorted(by_city, 8),
        "by_handler": _sorted(by_handler, 8),
        "batch": {
            "clusters": cluster_list,
            "cluster_count": len(cluster_list),
            "ticket_cnt": batch_cnt,
            "ticket_pct": pct(batch_cnt),
            "fix_rate": round(fixed_cnt / len(cluster_list) * 100, 1) if cluster_list else 0.0,
        },
        "efficiency": {
            "avg_opinions": round(opinion_sum / total, 1) if total else 0,
            "long_chain": long_chain, "long_chain_pct": pct(long_chain),
            "repeat_dispatch": repeat_dispatch, "repeat_dispatch_pct": pct(repeat_dispatch),
            "rework": rework, "rework_pct": pct(rework),
            "pushout": pushout, "pushout_pct": pct(pushout),
            "pending": pending, "pending_pct": pct(pending),
            "retention": retention,
            "unclosed": unclosed, "unclosed_pct": pct(unclosed),
        },
        "recur": {
            "cnt": recur_cnt, "pct": pct(recur_cnt),
            "tops": [{"name": k, "cnt": v} for k, v in
                     sorted(recur_l2.items(), key=lambda kv: -kv[1])[:5]],
        },
        "daily": daily,
        "trend": trend,
        "actions": [dict(a) for a in actions],
        "action_stats": {
            "total": action_total,
            "by_status": action_by_status,
            "completion_pct": action_completion,
        },
    }
