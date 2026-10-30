"""热点投诉模块（方案 v3.0 第②模块）——近一周投诉都集中在什么事。

设计要点：
  - 数据源唯一：复用 metrics.scene_wow（周单量+环比唯一实现），不自建第二份 SQL；
  - 排序：按本周单量倒序取 TOP N，凸显当下热点；
  - 环比标注四态：new（上期无）/ up / flat / down；
  - 反弹检测：该场景存在已闭环问题且本周量未低于闭环建议安静线 → 标 rebound 提示复盘；
  - 在办问题关联：热点场景直接挂出在办/候选问题编号（一键关联入口）；
  - 代表工单：本周该场景最新 2 条工单号（下钻入口）；
  - 所有数量均可通过 tickets 端点过滤参数下钻（week+l2）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.complaint import config as C
from services.complaint.metrics import latest_week, prev_week, recent_weeks, scene_wow


def weekly_hotspots(db: Session, week: Optional[str] = None,
                    top_n: int = 10) -> Dict[str, Any]:
    """某周热点投诉 TOP 榜（week 空 = 库内最新周）。"""
    week = week or latest_week(db)
    if not week:
        return {"week": "", "items": [], "total": 0}

    pw = prev_week(week)
    wow = scene_wow(db, week)

    # 在办/候选问题关联（该场景有未闭环问题则展示）
    prob_rows = db.execute(text(
        "SELECT category_l2, problem_no, status, title FROM pmwb_complaint_problem "
        "WHERE status IN ('candidate','open','resolving')"
    )).fetchall()
    open_problems: Dict[str, List[Dict[str, str]]] = {}
    for l2, pno, st, title in prob_rows:
        open_problems.setdefault(l2 or "", []).append(
            {"problem_no": pno, "status": st, "title": title})

    # 已闭环问题（反弹检测 + 复盘入口）
    closed_rows = db.execute(text(
        "SELECT category_l2, problem_no FROM pmwb_complaint_problem WHERE status = 'closed'"
    )).fetchall()
    closed_map: Dict[str, str] = {l2 or "": pno for l2, pno in closed_rows}

    # 一级性质快照（场景 → l1，取该场景最新工单的 l1）
    l1_rows = db.execute(text(
        "SELECT category_l2, category_l1 FROM pmwb_complaint_ticket "
        "WHERE category_l2 IS NOT NULL AND category_l2 <> '' AND category_l1 IS NOT NULL "
        "GROUP BY category_l2, category_l1"
    )).fetchall()
    l1_map: Dict[str, str] = {}
    for l2, l1 in l1_rows:
        l1_map.setdefault(l2 or "", l1 or "")

    # 代表工单：本周该场景最新 2 条
    rep_rows = db.execute(text(
        "SELECT category_l2, ticket_no FROM pmwb_complaint_ticket "
        "WHERE week = :w AND category_l2 IS NOT NULL AND category_l2 <> '' "
        "ORDER BY created_time DESC"
    ), {"w": week}).fetchall()
    rep_map: Dict[str, List[str]] = {}
    for l2, tno in rep_rows:
        lst = rep_map.setdefault(l2 or "", [])
        if len(lst) < 2:
            lst.append(tno)

    total = sum(v["cur"] for v in wow.values())
    items: List[Dict[str, Any]] = []
    for l2, v in sorted(wow.items(), key=lambda kv: (-kv[1]["cur"], kv[0]))[:top_n]:
        cur, prev = v["cur"], v["prev"]
        if prev == 0:
            flag = "new"
        elif cur > prev:
            flag = "up"
        elif cur < prev:
            flag = "down"
        else:
            flag = "flat"
        rebound = False
        if l2 in closed_map and cur >= max(prev, 1):
            rebound = True
        items.append({
            "l2": l2,
            "l1": l1_map.get(l2, ""),
            "cur": cur,
            "prev": prev,
            "wow": v["wow"],
            "flag": flag,
            "rebound": rebound,
            "closed_problem_no": closed_map.get(l2),
            "open_problems": open_problems.get(l2, []),
            "sample_tickets": rep_map.get(l2, []),
        })

    return {
        "week": week,
        "prev_week": pw,
        "weeks": list(reversed(recent_weeks(week, 8))),  # 周切换选项（最新在前）
        "total": int(total),
        "items": items,
        "quiet_weeks": C.PROBLEM_CLOSE_QUIET_WEEKS,
    }
