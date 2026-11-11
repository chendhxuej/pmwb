"""客诉「整体投诉全貌」——全量 / 跨周期聚合的**唯一实现**。

与 metrics.collect(db, week) 的分工：
  · metrics.collect  = 单周指标（本周概览、日走势、已知/新增、问题族、周报），按所选周；
  · overall.collect  = 全表跨周期指标（周趋势、异常波动、结构漂移、高频问题、闭环存量、
                       关键结论），不带 week 参数，口径固定为「库中全部工单」。

为什么只在这里算：全量口径若散落到前端（多次 /metrics + 分页 /tickets 拼装），
必然与列表 / 导出漂移。本模块一次批量取数 + Python 聚合，全程标准 SQL，
不使用 MySQL 专有函数（SQLite 测试库同样可跑），也不产生 N+1。

口径（2026-11-11 老大拍板）：
  · 全表 16 个自然周全部计入「总量 / 分类占比 / 闭环 / 高频问题」；
  · 有效天数 < 5 的周标「不完整」，不参与周均、异常波动、环比判定
    （W31 是导入起点只有 2 天、W46 是进行中周只有 2 天，直接算会把数据覆盖
      节奏误判成暴涨暴跌——与 metrics.collect 的「进行中周日均」同一原则）；
  · 闭环沿用 config.TERMINAL_STATUSES：「已回复 ≠ 结单」；
  · 关键结论全部由规则生成，不设人工确认队列、不调 LLM。
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.complaint.config import RETENTION_DAYS, TERMINAL_STATUSES
from services.complaint.metrics import week_bounds

# ── 整体视图规则常量（唯一源；调口径只改这里）──────────────────────
MIN_EFFECTIVE_DAYS = 5        # 一周至少覆盖 5 个有数据的自然日，才算完整周
ANOMALY_SIGMA = 1.5          # 偏离周均 ≥1.5σ 判异常
ANOMALY_WOW_PCT = 50.0       # 相邻两个完整周环比绝对值 ≥50% 判异常
RECENT_COMPLETE_WEEKS = 4    # 「近 4 周」结构漂移 / 是否仍活跃的窗口
TOP_PROBLEM_LIMIT = 8        # 高频问题榜条数


def _iso(d) -> str:
    return d.strftime("%Y-%m-%d") if d else ""


def _pct(n: int, total: int) -> float:
    return round(n / total * 100, 1) if total else 0.0


def collect(db: Session) -> Dict:
    # ── 一次批量取全表必要列（1582 行量级，Python 聚合比多次 SQL 更稳且跨库）──
    rows = db.execute(text("""
        SELECT ticket_no, week, created_time, status, category_l1, category_l2,
               is_batch, known_flag
        FROM pmwb_complaint_ticket
    """)).mappings().all()

    total = len(rows)
    if not total:
        return {"scope": {"total": 0, "weeks": 0}, "trend": [], "trend_summary": {},
                "categories": [], "top_problems": [], "problem_coverage": {},
                "closure": {}, "conclusions": []}

    created = [r["created_time"] for r in rows if r["created_time"]]
    first_dt, last_dt = min(created), max(created)

    # ── 周维度分组 ──────────────────────────────────────────────
    by_week: Dict[str, List] = defaultdict(list)
    for r in rows:
        if r["week"]:
            by_week[r["week"]].append(r)
    weeks = sorted(by_week)

    week_days = {
        w: len({r["created_time"].date() for r in rs if r["created_time"]})
        for w, rs in by_week.items()
    }
    complete_weeks = [w for w in weeks if week_days[w] >= MIN_EFFECTIVE_DAYS]
    incomplete_weeks = [w for w in weeks if w not in complete_weeks]
    # 进行中周：最后一个自然周且今天仍落在该周区间内（复用 metrics.week_bounds，
    # 与 metrics.collect 的 in_progress 判定同源，禁另造一套日期推算）
    today = date.today()
    in_progress_week = ""
    if weeks:
        s_w, e_w = week_bounds(weeks[-1])
        if s_w.date() <= today < e_w.date():
            in_progress_week = weeks[-1]

    vals = [len(by_week[w]) for w in complete_weeks]
    mu = sum(vals) / len(vals) if vals else 0.0
    sigma = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5 if vals else 0.0

    recent = complete_weeks[-RECENT_COMPLETE_WEEKS:]
    recent_set = set(recent)
    recent_total = sum(len(by_week[w]) for w in recent)

    z_map = ({w: round((len(by_week[w]) - mu) / sigma, 2) for w in complete_weeks}
             if sigma else {})
    trend: List[Dict] = []
    anomalies: List[Dict] = []
    for i, w in enumerate(weeks):
        cnt = len(by_week[w])
        batch = sum(1 for r in by_week[w] if r["is_batch"])
        is_complete = w in complete_weeks
        z, wow = z_map.get(w), None
        # 环比只在「相邻两个完整周」之间算，中间隔着不完整周则不比
        prev_w = weeks[i - 1] if i > 0 else ""
        if is_complete and prev_w in complete_weeks:
            prev_cnt = len(by_week[prev_w])
            if prev_cnt:
                wow = round((cnt - prev_cnt) / prev_cnt * 100, 1)
        # 低基数环比不可比：基准周本身若已判异常，环比会把「从异常低点回到常态」
        # 放大成暴涨（实测 W37=20 → W38=97 算出 +385%，但 W38 实际低于周均）。
        # 故只在基准周正常（|z| < 1.5σ）时启用环比判定，与 metrics「残缺周不可比」同源。
        base_normal = prev_w in z_map and abs(z_map[prev_w]) < ANOMALY_SIGMA
        wow_valid = wow is not None and base_normal
        spike = (z is not None and z >= ANOMALY_SIGMA) or (wow_valid and wow >= ANOMALY_WOW_PCT)
        dip = (z is not None and z <= -ANOMALY_SIGMA) or (wow_valid and wow <= -ANOMALY_WOW_PCT)
        anomaly = "spike" if spike else ("dip" if dip else None)
        if anomaly:
            anomalies.append({
                "week": w, "total": cnt, "type": anomaly, "z": z,
                "wow_pct": wow, "vs_avg_pct": round((cnt / mu - 1) * 100, 1) if mu else None,
            })
        trend.append({
            "week": w, "total": cnt, "batch": batch, "days": week_days[w],
            "complete": is_complete, "anomaly": anomaly, "z": z, "wow_pct": wow,
        })

    peak = max(complete_weeks, key=lambda w: len(by_week[w])) if complete_weeks else ""
    low = min(complete_weeks, key=lambda w: len(by_week[w])) if complete_weeks else ""
    wow_last = None
    if len(complete_weeks) >= 2:
        a, b = len(by_week[complete_weeks[-2]]), len(by_week[complete_weeks[-1]])
        wow_last = round((b - a) / a * 100, 1) if a else None

    trend_summary = {
        "avg_week": round(mu, 1), "sigma": round(sigma, 1),
        "complete_week_cnt": len(complete_weeks),
        "sigma_threshold": ANOMALY_SIGMA, "wow_threshold": ANOMALY_WOW_PCT,
        "peak_week": peak, "peak_total": len(by_week[peak]) if peak else 0,
        "low_week": low, "low_total": len(by_week[low]) if low else 0,
        "anomaly_weeks": anomalies, "anomaly_cnt": len(anomalies),
        "last_complete_week": complete_weeks[-1] if complete_weeks else "",
        "recent_complete_weeks": recent, "recent_total": recent_total,
        "wow_last_complete_pct": wow_last,
    }

    # ── 问题分类占比 + 近 4 完整周结构漂移（跨周期独有，非周维度饼图复刻）──
    l1_all = Counter(r["category_l1"] or "未分类" for r in rows)
    l1_recent = Counter(
        r["category_l1"] or "未分类" for w in recent for r in by_week[w]
    )
    categories = []
    for name, cnt in l1_all.most_common():
        rc = l1_recent.get(name, 0)
        all_pct, rc_pct = _pct(cnt, total), _pct(rc, recent_total)
        categories.append({
            "name": name, "cnt": cnt, "pct": all_pct,
            "recent_cnt": rc, "recent_pct": rc_pct,
            "drift_pp": round(rc_pct - all_pct, 1),
        })

    # ── 高频问题（L2 闭集缺陷类；按实时归集明细计数，展示=下钻=导出）──
    mp_rows = db.execute(text("""
        SELECT ticket_no, module_problem_id FROM pmwb_complaint_ticket_module
    """)).mappings().all()
    mp_of = {r["ticket_no"]: r["module_problem_id"] for r in mp_rows}
    live_cnt = Counter(
        mp_of.get(r["ticket_no"]) for r in rows if mp_of.get(r["ticket_no"])
    )
    unclassified = sum(1 for r in rows if not mp_of.get(r["ticket_no"]))
    consult_cnt = live_cnt.get("MP-CONSULT", 0)

    mp_dict = db.execute(text("""
        SELECT module_problem_id, name, is_defect, first_week, active_weeks
        FROM pmwb_complaint_module_problem
    """)).mappings().all()
    mp_meta = {m["module_problem_id"]: m for m in mp_dict}

    top_problems = []
    for mid, cnt in live_cnt.most_common():
        meta = mp_meta.get(mid)
        if not meta or meta["is_defect"] != 1:  # 使用咨询非缺陷，单列不计入重点问题榜
            continue
        last4 = sum(1 for w in recent for r in by_week[w] if mp_of.get(r["ticket_no"]) == mid)
        top_problems.append({
            "module_problem_id": mid, "name": meta["name"], "cnt": cnt,
            "pct": _pct(cnt, total), "first_week": meta["first_week"] or "",
            "active_weeks": meta["active_weeks"] or 0, "recent4_cnt": last4,
            "still_active": last4 > 0,
        })
        if len(top_problems) >= TOP_PROBLEM_LIMIT:
            break

    problem_coverage = {
        "classified": total - unclassified, "unclassified": unclassified,
        "classes": len(mp_dict), "defect_classes": sum(1 for m in mp_dict if m["is_defect"] == 1),
        "consult_cnt": consult_cnt, "consult_pct": _pct(consult_cnt, total),
    }

    # ── 处理状态 / 闭环（已回复 ≠ 结单）────────────────────────
    is_closed = lambda s: (s or "") in TERMINAL_STATUSES
    status_cnt = Counter(r["status"] or "未知" for r in rows)
    closed = sum(1 for r in rows if is_closed(r["status"]))
    open_cnt = total - closed
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    retention = sum(
        1 for r in rows
        if not is_closed(r["status"]) and r["created_time"] and r["created_time"] < cutoff
    )
    recent_open = sum(
        1 for w in recent for r in by_week[w] if not is_closed(r["status"])
    )
    status_breakdown = [
        {"name": k, "cnt": v, "pct": _pct(v, total), "closed": is_closed(k)}
        for k, v in status_cnt.most_common()
    ]
    flag_cnt = Counter("known" if r["known_flag"] == 1 else
                       "new" if r["known_flag"] == 0 else "undetermined" for r in rows)

    ledger = Counter(r[0] for r in db.execute(
        text("SELECT status FROM pmwb_complaint_problem")).fetchall())
    actions = Counter(r[0] for r in db.execute(
        text("SELECT status FROM pmwb_complaint_action")).fetchall())
    closed_problem_status = {"closed"}
    excluded_problem_status = {"merged", "ignored"}  # 墓碑行留痕，但不算在册
    ledger_live = sum(v for k, v in ledger.items() if k not in excluded_problem_status
                      and k not in closed_problem_status)

    closure = {
        "closed": closed, "open": open_cnt, "closed_pct": _pct(closed, total),
        "status_breakdown": status_breakdown,
        "replied_not_closed": status_cnt.get("已回复", 0),
        "retention": retention, "retention_days": RETENTION_DAYS,
        "recent4_open": recent_open,
        "batch": sum(1 for r in rows if r["is_batch"]),
        "known": flag_cnt["known"], "new": flag_cnt["new"],
        "undetermined": flag_cnt["undetermined"],
        "problem_ledger": {**dict(ledger), "live": ledger_live},
        "actions": dict(actions),
    }

    # ── 关键结论摘要：全部规则生成，无人工队列、无 LLM ────────────
    in_progress_days = week_days.get(in_progress_week, 0) if in_progress_week else 0
    conclusions = _conclusions(
        total=total, weeks=weeks, first_dt=first_dt, last_dt=last_dt,
        trend_summary=trend_summary, categories=categories,
        top_problems=top_problems, problem_coverage=problem_coverage,
        closure=closure, in_progress_week=in_progress_week,
        in_progress_days=in_progress_days, incomplete_weeks=incomplete_weeks,
    )

    return {
        "scope": {
            "total": total, "weeks": len(weeks),
            "first_date": _iso(first_dt), "last_date": _iso(last_dt),
            "data_until": last_dt.strftime("%Y-%m-%d %H:%M"),
            "complete_weeks": len(complete_weeks),
            "incomplete_weeks": incomplete_weeks,
            "in_progress_week": in_progress_week,
            "in_progress_days": week_days.get(in_progress_week, 0) if in_progress_week else 0,
            "min_effective_days": MIN_EFFECTIVE_DAYS,
            "recent_complete_weeks": recent,
        },
        "trend": trend,
        "trend_summary": trend_summary,
        "categories": categories,
        "top_problems": top_problems,
        "problem_coverage": problem_coverage,
        "closure": closure,
        "conclusions": conclusions,
    }


def _conclusions(*, total, weeks, first_dt, last_dt, trend_summary, categories,
                 top_problems, problem_coverage, closure, in_progress_week,
                 in_progress_days, incomplete_weeks) -> List[Dict]:
    out: List[Dict] = []

    def add(kind, level, text, filters=None, note=""):
        out.append({"kind": kind, "level": level, "text": text,
                    "filters": filters or {}, "note": note})

    s = trend_summary
    add("scale", "info",
        f"累计 {total} 单，覆盖 {len(weeks)} 个自然周（{_iso(first_dt)} ~ {_iso(last_dt)}）；"
        f"{s['complete_week_cnt']} 个完整周周均 {s['avg_week']} 单。",
        {}, "总量口径：库中全部工单，不含任何周筛选")

    if s["peak_week"]:
        ratio = round(s["peak_total"] / s["avg_week"], 1) if s["avg_week"] else 0
        add("peak", "warn",
            f"峰值 {s['peak_week']} {s['peak_total']} 单（约为周均 {ratio} 倍）；"
            f"最低 {s['low_week']} {s['low_total']} 单。",
            {"week": s["peak_week"]})

    if s["anomaly_cnt"]:
        parts = "、".join(
            f"{a['week']} {'突增' if a['type'] == 'spike' else '骤降'} {a['total']} 单"
            f"（偏离周均 {a['vs_avg_pct'] or 0:+}%）" for a in s["anomaly_weeks"]
        )
        add("anomaly", "danger",
            f"识别到 {s['anomaly_cnt']} 个异常波动周：{parts}。",
            {"week": s["anomaly_weeks"][0]["week"]},
            f"规则：完整周偏离周均 ≥{ANOMALY_SIGMA}σ 或相邻完整周环比 ≥{ANOMALY_WOW_PCT}%")
    else:
        add("anomaly", "success", "完整周单量未见显著异常波动。", {})

    if in_progress_week:
        add("in_progress", "info",
            f"{in_progress_week} 尚在进行中（当前仅 {in_progress_days} 天数据），"
            f"不参与周均、异常波动与环比判定。", {},
            "与周维度「进行中周日均按已过天数」同源")
    if incomplete_weeks:
        add("incomplete", "info",
            f"不完整周 {len(incomplete_weeks)} 个（{'、'.join(incomplete_weeks)}）："
            f"有效天数 < {MIN_EFFECTIVE_DAYS}，仅计入总量，不参与波动判定。", {})

    if categories:
        top1 = categories[0]
        drift = max(categories, key=lambda c: abs(c["drift_pp"]))
        add("structure", "info",
            f"分类占比以「{top1['name']}」最高（{top1['cnt']} 单 / {top1['pct']}%）；"
            f"「{drift['name']}」在近 {RECENT_COMPLETE_WEEKS} 个完整周占比 "
            f"{drift['recent_pct']}%，较全周期漂移 {drift['drift_pp']:+} pp。",
            {"l1": top1["name"]}, "漂移 = 近 4 完整周占比 − 全周期占比")
        add("consult", "warn",
            f"使用/操作/规则咨询 {problem_coverage['consult_cnt']} 单"
            f"（{problem_coverage['consult_pct']}%）属非缺陷，应走指引话术而非研发排期；"
            f"缺陷类 {problem_coverage['defect_classes']} 类才是改造落点。",
            {"module_problem_id": "MP-CONSULT"})

    if top_problems:
        head3 = top_problems[:3]
        sum3 = sum(x["cnt"] for x in head3)
        add("top", "warn",
            f"高频问题 TOP3（{'、'.join(x['name'] for x in head3)}）合计 {sum3} 单，"
            f"占总量 {_pct(sum3, total)}%；"
            f"其中 {sum(1 for x in top_problems if x['still_active'] and x['active_weeks'] >= 8)} "
            f"类持续 ≥8 周且近 4 周仍在发生，属久拖不决。",
            {"module_problem_id": head3[0]["module_problem_id"]},
            "高频 = 全周期累计（L2 闭集缺陷类），非本周单量")

    add("closure", "danger" if closure["open"] else "success",
        f"闭环率 {closure['closed_pct']}%（{closure['closed']}/{total} 单）；"
        f"未闭环 {closure['open']} 单中「已回复」{closure['replied_not_closed']} 单"
        f"——已回复 ≠ 结单；超 {closure['retention_days']} 天滞留 {closure['retention']} 单。",
        {"unclosed": 1}, "闭环口径取 config.TERMINAL_STATUSES")
    add("ledger", "info",
        f"问题台账在册 {closure['problem_ledger'].get('live', 0)} 条"
        f"（open {closure['problem_ledger'].get('open', 0)} / "
        f"resolving {closure['problem_ledger'].get('resolving', 0)}）；"
        f"措施 {sum(closure['actions'].values())} 条，"
        f"已生效 {closure['actions'].get('effective', 0)} 条。",
        {"unclosed": 0})

    if problem_coverage["unclassified"]:
        add("unclassified", "warn",
            f"L2 闭集归集覆盖 {problem_coverage['classified']}/{total} 单，"
            f"{problem_coverage['unclassified']} 单未归类（待自动补跑，不转人工）。",
            {"unclassified": 1})
    return out
