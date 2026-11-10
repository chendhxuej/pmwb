"""投诉现状看板 · 口径一致性回归（2026-11-10）。

针对老大反馈的两处「数字对不上」：
  1. TOP 缺陷类：排序键 == 展示字段 == 下钻字段，且统计周 == 页面选周；
  2. 已知问题（按本周命中单量）：表格 cnt == 下钻明细数 == 导出行数。

同时守住「旧口径确实不等」这一事实，避免回归退化成假绿。

用法（真实 HTTP，需后端已加载新代码）：
  PMWB_BASE=http://127.0.0.1:8000 PMWB_AUTH_USER=chendh PMWB_AUTH_PW=*** \
    python scripts/verify_complaint_dashboard_consistency.py
  # 可指定周：PMWB_WEEKS=2026-W44,2026-W45
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from urllib.parse import urlencode

BASE = os.environ.get("PMWB_BASE", "http://127.0.0.1:8000")
USER = os.environ.get("PMWB_AUTH_USER", "chendh")
PW = os.environ.get("PMWB_AUTH_PW", "")
WEEKS = [w.strip() for w in os.environ.get("PMWB_WEEKS", "2026-W45,2026-W46").split(",") if w.strip()]

PASS = 0
FAIL = 0
FAILED: list[str] = []


def ok(name: str, cond: bool, extra: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}" + (f"  {extra}" if extra else ""))
    else:
        FAIL += 1
        FAILED.append(name)
        print(f"  FAIL  {name}" + (f"  {extra}" if extra else ""))


def login() -> str:
    req = urllib.request.Request(
        BASE + "/api/v1/auth/login",
        data=json.dumps({"username": USER, "password": PW}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())["data"]["token"]


TOKEN = login()


def raw(path: str, params: dict):
    url = BASE + path + (("?" + urlencode(params)) if params else "")
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + TOKEN})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.headers, r.read()


def api(path: str, params: dict | None = None):
    _, body = raw(path, params or {})
    return json.loads(body)["data"]


def ticket_total(params: dict) -> int:
    return api("/api/v1/complaint/tickets",
               {**params, "page": 1, "page_size": 1})["total"]


def export_rows(params: dict) -> int:
    headers, _ = raw("/api/v1/complaint/tickets/export", params)
    v = headers.get("X-Export-Rows")
    return int(v) if v and v.isdigit() else -1


print("=" * 68)
print("投诉现状看板 · 口径一致性回归")
print(f"BASE={BASE}  WEEKS={','.join(WEEKS)}")
print("=" * 68)

for w in WEEKS:
    print(f"\n▶ {w} · TOP 缺陷类（展示/排序/下钻/导出同源）")
    cls = api("/api/v1/complaint/module-problem/classes",
              {"include_consult": "false", "week": w})
    items = cls.get("items") or []
    ok(f"{w} classes 返回缺陷类", len(items) > 0, f"count={len(items)}")
    ok(f"{w} stat_week 与页面选周一致",
       all(x.get("stat_week") == w for x in items),
       f"stat_week={items[0].get('stat_week') if items else '-'}")
    top = [x for x in items if (x.get("week_cnt") or 0) > 0][:6]
    vals = [x["week_cnt"] for x in top]
    ok(f"{w} TOP 有数据且单量严格降序", bool(vals) and vals == sorted(vals, reverse=True),
       str(vals))
    # 排序键必须就是展示字段：名次靠前的 week_cnt 不得小于靠后的
    ok(f"{w} 首名单量 >= 末名单量", bool(vals) and vals[0] >= vals[-1],
       f"{vals[0] if vals else '-'} >= {vals[-1] if vals else '-'}")
    for c in top:
        mid = c["module_problem_id"]
        cond = {"week": w, "module_problem_id": mid}
        t = ticket_total(cond)
        e = export_rows(cond)
        ok(f"{w} {mid} 显示 {c['week_cnt']} = 下钻 {t}", t == c["week_cnt"])
        ok(f"{w} {mid} 导出 {e} = 显示 {c['week_cnt']}", e == c["week_cnt"])

    print(f"\n▶ {w} · 已知问题（本周命中 = 下钻 = 导出）")
    m = api("/api/v1/complaint/metrics", {"week": w})
    k = m.get("known") or {}
    kp = k.get("known_problems") or []
    ok(f"{w} 已知问题表有数据", len(kp) > 0, f"rows={len(kp)}")
    ok(f"{w} 命中合计 = known_cnt", sum(x["cnt"] for x in kp) == k.get("known_cnt"),
       f"sum={sum(x['cnt'] for x in kp)} known_cnt={k.get('known_cnt')}")
    old_diff = 0
    for p in kp:
        cond = {"week": w, "known_flag": 1, "known_problem_no": p["problem_no"]}
        t = ticket_total(cond)
        e = export_rows(cond)
        ok(f"{w} {p['problem_no']} 命中 {p['cnt']} = 下钻 {t}", t == p["cnt"])
        ok(f"{w} {p['problem_no']} 导出 {e} = 命中 {p['cnt']}", e == p["cnt"])
        # 旧口径（problem_no）确实不等，才说明这次修的是真问题而非假绿
        if ticket_total({"week": w, "problem_no": p["problem_no"]}) != p["cnt"]:
            old_diff += 1
    if w == "2026-W45":
        ok("W45 旧 problem_no 口径确实存在偏差（回归防假绿）", old_diff > 0,
           f"{old_diff}/{len(kp)} 条不等")

    print(f"\n▶ {w} · 新增问题下钻口径（known_flag=0）")
    nc = [x for x in (k.get("new_clusters") or []) if x.get("rootcause_no")]
    if nc:
        r = nc[0]
        t = ticket_total({"week": w, "known_flag": 0, "rootcause_no": r["rootcause_no"]})
        ok(f"{w} 新增簇 {r['rootcause_no']} cnt {r['cnt']} = 下钻 {t}", t == r["cnt"])
    else:
        ok(f"{w} 无带簇新增项（跳过）", True)

print("\n" + "=" * 68)
print(f"结果：{PASS} 通过 / {FAIL} 失败")
if FAILED:
    for n in FAILED:
        print("  ✗ " + n)
    print("HAS_FAILURE")
    sys.exit(1)
print("ALL_PASS")
