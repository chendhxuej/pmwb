"""问题族（业务链路）聚合——报表与看板的「不散」视角唯一实现

为什么需要这一层：根因簇是「个案级」（776/859 个簇只有 1 单，标题精确到订单号），
直接当问题列表展示会又散又不准。业务要看的是链路级：这条链路本周多少单、
环比涨跌、是不是已知问题。

口径（与 known.py / problems.py 保持单一真相源）：
  - 族由簇的 fault_stage 派生（constants.complaint_theme.STAGE_TO_THEME），不落库；
  - 族单量 = 族内所有簇的工单量之和；未归因工单（无簇）单列，不摊到任何族；
  - 已知/新增沿用工单上的 known_flag（known.py 是唯一写入点），这里只做聚合；
  - 「一次性个案」= 累计只有 1 单的簇，单独计数，不混进族的问题列表。
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from constants import complaint_theme as T
from services.complaint.metrics import latest_week, prev_week, week_bounds
from datetime import datetime


def _week_cluster_counts(db: Session, week: str) -> Dict[str, Dict]:
    """当周按簇计数（工单量 / 已知 / 新增）。week 为空返回空。"""
    if not week:
        return {}
    start, end = week_bounds(week)
    rows = db.execute(text(
        "SELECT rootcause_no, COUNT(*) c, "
        "       SUM(CASE WHEN known_flag = 1 THEN 1 ELSE 0 END) k, "
        "       SUM(CASE WHEN known_flag = 0 THEN 1 ELSE 0 END) n "
        "FROM pmwb_complaint_ticket "
        "WHERE created_time >= :s AND created_time < :e "
        "  AND rootcause_no IS NOT NULL AND rootcause_no <> '' "
        "GROUP BY rootcause_no"
    ), {"s": start, "e": end}).fetchall()
    return {str(r[0]): {"cnt": int(r[1] or 0), "known": int(r[2] or 0), "new": int(r[3] or 0)}
            for r in rows}


def _effective_days(db: Session, week: str) -> Dict[str, Any]:
    """该周的有效天数与是否完整。

    为什么不能直接用 7 天：
      - 正在进行的周（如周三看当周）数据只到当天，用 7 摊薄会把环比算成暴跌；
      - 历史残缺周（只有 2 天数据）用 2 天又会让日均虚高。
    口径：进行中的周 = 周一至今天；历史周 = 实际有工单的天数；≥5 天视为完整
    （与 actions.complete_weeks 的完整性判定同口径，避免两套标准）。
    """
    start, end = week_bounds(week)
    rows = db.execute(text(
        "SELECT created_time FROM pmwb_complaint_ticket "
        "WHERE created_time >= :s AND created_time < :e"
    ), {"s": start, "e": end}).fetchall()
    dates = set()
    for (v,) in rows:
        if v is None:
            continue
        dates.add(v.date() if hasattr(v, "date") else v)
    today = datetime.now().date()
    if start.date() <= today < end.date():
        days = max(1, (today - start.date()).days + 1)
        return {"days": days, "complete": days >= 5, "running": True}
    days = max(len(dates), 1)
    return {"days": days, "complete": days >= 5, "running": False}


def _unattributed(db: Session, week: str) -> Dict[str, int]:
    """未归因工单（没有根因簇，或根因仍在分析中）——必须单列，不能静默丢。"""
    if not week:
        return {"cnt": 0, "known": 0, "new": 0}
    start, end = week_bounds(week)
    r = db.execute(text(
        "SELECT COUNT(*), "
        "       SUM(CASE WHEN known_flag = 1 THEN 1 ELSE 0 END), "
        "       SUM(CASE WHEN known_flag = 0 THEN 1 ELSE 0 END) "
        "FROM pmwb_complaint_ticket "
        "WHERE created_time >= :s AND created_time < :e "
        "  AND (rootcause_no IS NULL OR rootcause_no = '')"
    ), {"s": start, "e": end}).first()
    return {"cnt": int(r[0] or 0), "known": int(r[1] or 0), "new": int(r[2] or 0)}


def theme_stats(db: Session, week: Optional[str] = None, top_n: int = 3) -> Dict:
    """按业务链路族聚合当前周（默认最新周）的单量与环比。

    返回：
      {
        "week": "2026-W45", "prev_week": "2026-W44",
        "total": 60,                       # 当周总单量（含未归因）
        "themes": [{key,name,week_cnt,prev_cnt,wow,total_cnt,cluster_cnt,case_cnt,
                    known_cnt,new_cnt,is_new,top_clusters:[{rc_no,title,cnt}]}],
        "unattributed": {cnt,known,new},
        "cases": {"cluster_cnt": N, "ticket_cnt": M},   # 一次性个案汇总
        "new_case_cnt": K,                              # 当周首次出现的一次性个案
      }
    """
    week = week or latest_week(db)
    if not week:
        return {"week": "", "prev_week": "", "total": 0, "themes": [],
                "unattributed": {"cnt": 0, "known": 0, "new": 0},
                "cases": {"cluster_cnt": 0, "ticket_cnt": 0}, "new_case_cnt": 0}

    pw = prev_week(week)
    cur = _week_cluster_counts(db, week)
    prev = _week_cluster_counts(db, pw)
    cur_d = _effective_days(db, week)
    prev_d = _effective_days(db, pw)
    # 环比一律走「日均对比」：本周若只看 3 天，直接比总量会得出 -70% 这种假暴跌
    cur_days = cur_d["days"]
    prev_days = prev_d["days"]
    prev_usable = bool(prev_d["complete"])

    clusters = db.execute(text(
        "SELECT rootcause_no, title, fault_stage, ticket_cnt, first_week, "
        "       COALESCE(is_defect, 1) "
        "FROM pmwb_complaint_rootcause "
        "WHERE status IN ('open', 'candidate')"
    )).fetchall()

    buckets: Dict[str, Dict] = {}
    cases = {"cluster_cnt": 0, "ticket_cnt": 0}
    new_case_cnt = 0
    for rc_no, title, stage, tcnt, first_week, is_defect in clusters:
        rc_no = str(rc_no)
        tcnt = int(tcnt or 0)
        key = T.theme_of(stage)
        b = buckets.setdefault(key, {
            "key": key, "name": T.theme_name(key), "week_cnt": 0, "prev_cnt": 0,
            "total_cnt": 0, "cluster_cnt": 0, "case_cnt": 0,
            "known_cnt": 0, "new_cnt": 0, "is_new": False, "first_week": "",
            "_clusters": [], "_rc_nos": [],
        })
        c = cur.get(rc_no) or {}
        p = prev.get(rc_no) or {}
        b["week_cnt"] += int(c.get("cnt", 0))
        b["prev_cnt"] += int(p.get("cnt", 0))
        b["known_cnt"] += int(c.get("known", 0))
        b["new_cnt"] += int(c.get("new", 0))
        b["total_cnt"] += tcnt
        b["cluster_cnt"] += 1
        b["_rc_nos"].append(rc_no)
        if first_week and (not b["first_week"] or first_week < b["first_week"]):
            b["first_week"] = first_week
        if tcnt <= 1:
            b["case_cnt"] += 1
            cases["cluster_cnt"] += 1
            cases["ticket_cnt"] += tcnt
            if first_week == week:
                new_case_cnt += 1
        else:
            b["_clusters"].append({
                "rc_no": rc_no, "title": title or "", "cnt": tcnt,
                "week_cnt": int(c.get("cnt", 0)), "is_defect": int(is_defect or 1),
            })

    out: List[Dict] = []
    for key, b in buckets.items():
        clusters_sorted = sorted(b["_clusters"], key=lambda x: (-x["cnt"], x["rc_no"]))
        b["top_clusters"] = clusters_sorted[:top_n]
        b["problem_cluster_cnt"] = len(clusters_sorted)
        b.pop("_clusters", None)
        # 族内全部簇号：前端「下钻该族工单」用（多簇逗号透传给 /tickets?rootcause_no=）
        b["rc_nos"] = b.pop("_rc_nos", [])
        if b["prev_cnt"] and prev_usable:
            cur_avg = b["week_cnt"] / cur_days
            prev_avg = b["prev_cnt"] / prev_days
            b["wow"] = round((cur_avg - prev_avg) / prev_avg * 100, 1) if prev_avg else None
        else:
            # 上周该族为 0 或上周数据不完整（<5 天）：环比不可计算，不给假降幅/假增幅
            b["wow"] = None
        b["avg"] = round(b["week_cnt"] / cur_days, 1)
        b["prev_avg"] = round(b["prev_cnt"] / prev_days, 1)
        # 样本过小（两周合计 <5 单）时环比数字没有决策意义，页面需要标出来
        b["low_sample"] = (b["week_cnt"] + b["prev_cnt"]) < 5
        b["is_new"] = bool(b["first_week"] == week and b["week_cnt"] > 0)
        out.append(b)

    out.sort(key=lambda x: (T.sort_key(x["key"]), -x["week_cnt"]))

    start, end = week_bounds(week)
    total = db.execute(text(
        "SELECT COUNT(*) FROM pmwb_complaint_ticket "
        "WHERE created_time >= :s AND created_time < :e"
    ), {"s": start, "e": end}).scalar() or 0

    return {
        "week": week, "prev_week": pw, "total": int(total),
        "themes": out,
        "unattributed": _unattributed(db, week),
        "cases": cases,
        "new_case_cnt": new_case_cnt,
        # 环比口径说明：页面/报表必须一起展示，否则读者会以为是总量同比
        "wow_basis": "daily_avg",
        "week_days": cur_days,
        "prev_days": prev_days,
        "week_running": bool(cur_d["running"]),
        "prev_usable": prev_usable,
    }


def theme_of_problem(db: Session, problem_rows: List[Dict]) -> Dict[str, str]:
    """问题 → 族 key（问题台账/报表给问题打族标签用）。"""
    nos = [str(p.get("rootcause_no") or "") for p in problem_rows]
    nos = [n for n in nos if n]
    if not nos:
        return {}
    marks = ",".join(f":c{i}" for i in range(len(nos)))
    rows = db.execute(text(
        f"SELECT rootcause_no, fault_stage FROM pmwb_complaint_rootcause "
        f"WHERE rootcause_no IN ({marks})"
    ), {f"c{i}": v for i, v in enumerate(nos)}).fetchall()
    stage_of = {str(r[0]): r[1] or "" for r in rows}
    return {str(p.get("rootcause_no") or ""): T.theme_of(stage_of.get(str(p.get("rootcause_no") or ""), ""))
            for p in problem_rows}
