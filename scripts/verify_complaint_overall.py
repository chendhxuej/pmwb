"""客诉「整体投诉全貌」· 全量口径一致性回归（2026-11-11）。

守住新增整体视图的每一处可核对等式（老大对「数字对不上」零容忍）：
  · 全量范围：Σ周单量 = Σ分类 = Σ状态 = 闭环分子+分母 = /tickets 不传 week 的总数；
  · 跨周期规则：不完整周不参与周均/异常判定；异常周只落在完整周；
    低基数环比（基准周本身异常）不得把「回到常态」误判成暴涨；
  · 展示=下钻=导出：分类 / 高频问题 / 处理状态 / 未归类 / 未闭环 逐条核对；
  · 周维度未被破坏：/metrics?week=... 与既有下钻仍可用，/overall 不接 week 参数。

用法（真实 HTTP，需后端已加载新代码）：
  PMWB_BASE=http://127.0.0.1:8000 PMWB_AUTH_USER=chendh PMWB_AUTH_PW=*** \
    python scripts/verify_complaint_overall.py
"""
from __future__ import annotations

import json
import os
import urllib.request
from urllib.parse import urlencode

BASE = os.environ.get("PMWB_BASE", "http://127.0.0.1:8000")
USER = os.environ.get("PMWB_AUTH_USER", "chendh")
PW = os.environ.get("PMWB_AUTH_PW", "")

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


def api(path: str, params: dict | None = None) -> dict:
    url = BASE + path + (("?" + urlencode(params)) if params else "")
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"Authorization": "Bearer " + TOKEN}), timeout=60
    ) as r:
        return json.loads(r.read())["data"]


def tickets_total(params: dict | None = None) -> int:
    q = {"page": 1, "page_size": 1, **(params or {})}
    return api("/api/v1/complaint/tickets", q)["total"]


def export_rows(params: dict | None = None) -> int:
    url = BASE + "/api/v1/complaint/tickets/export" + (
        ("?" + urlencode(params)) if params else "")
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"Authorization": "Bearer " + TOKEN}), timeout=120
    ) as r:
        return int(r.headers.get("X-Export-Rows", "-1"))


print("=" * 72)
print(f"整体投诉全貌回归  BASE={BASE}")
print("=" * 72)

d = api("/api/v1/complaint/overall")
s, ts, cl = d["scope"], d["trend_summary"], d["closure"]
pc = d["problem_coverage"]
total = s["total"]
trend = d["trend"]

print("\n── 一、全量范围与聚合等式 ──")
ok("scope.total 等于 /tickets 不传 week 的全量总数", total == tickets_total(),
   f"overall={total} tickets={tickets_total()}")
ok("Σ trend.total == 总量", sum(t["total"] for t in trend) == total,
   f"{sum(t['total'] for t in trend)} vs {total}")
ok("Σ categories.cnt == 总量", sum(c["cnt"] for c in d["categories"]) == total)
ok("Σ status_breakdown.cnt == 总量", sum(x["cnt"] for x in cl["status_breakdown"]) == total)
ok("闭环 + 未闭环 == 总量", cl["closed"] + cl["open"] == total,
   f"{cl['closed']}+{cl['open']}")
ok("闭环率分母为总量", cl["closed_pct"] == round(cl["closed"] / total * 100, 1))
ok("归集覆盖 + 未归类 == 总量", pc["classified"] + pc["unclassified"] == total,
   f"{pc['classified']}+{pc['unclassified']}")
ok("完整周 + 不完整周 == 总周数",
   s["complete_weeks"] + len(s["incomplete_weeks"]) == s["weeks"])
ok("近 4 完整周单量合计 == trend_summary.recent_total",
   sum(t["total"] for t in trend if t["week"] in s["recent_complete_weeks"]) == ts["recent_total"],
   str(ts["recent_total"]))
ok("Σ categories.recent_cnt == 近 4 完整周总量",
   sum(c["recent_cnt"] for c in d["categories"]) == ts["recent_total"])
ok("完整周周均 = 完整周总量 / 完整周数",
   ts["avg_week"] == round(sum(t["total"] for t in trend if t["complete"]) / s["complete_weeks"], 1),
   str(ts["avg_week"]))
ok("peak_week 为完整周最大单量周",
   ts["peak_week"] == max((t for t in trend if t["complete"]), key=lambda x: x["total"])["week"],
   ts["peak_week"])
ok("last_complete_week 为最后一个完整周",
   ts["last_complete_week"] == [t["week"] for t in trend if t["complete"]][-1])
ok("进行中周落在不完整周里", (not s["in_progress_week"]) or
   s["in_progress_week"] in s["incomplete_weeks"], s["in_progress_week"])

print("\n── 二、跨周期 / 异常波动规则 ──")
inc = [t for t in trend if not t["complete"]]
ok("不完整周全部未参与异常判定", all(t["anomaly"] is None for t in inc),
   str([t["week"] for t in inc]))
ok("异常周全部是完整周", all(
   next(t for t in trend if t["week"] == a["week"])["complete"] for a in ts["anomaly_weeks"]))
ok("异常周数 == anomaly_cnt", len(ts["anomaly_weeks"]) == ts["anomaly_cnt"],
   str(ts["anomaly_cnt"]))
ok("每个异常周满足 |z|≥阈值 或 有效环比≥阈值", all(
   (a["z"] is not None and abs(a["z"]) >= ts["sigma_threshold"]) or
   (a["wow_pct"] is not None and abs(a["wow_pct"]) >= ts["wow_threshold"])
   for a in ts["anomaly_weeks"]), str([(a["week"], a["z"], a["wow_pct"]) for a in ts["anomaly_weeks"]]))
# 防假绿：W37 是异常骤降，W38 只是「从异常低点回到常态」（低于周均），不得判突增
ok("低基数环比不产生假突增（W38 不在异常周）",
   "2026-W38" not in [a["week"] for a in ts["anomaly_weeks"]],
   str([a["week"] for a in ts["anomaly_weeks"]]))
ok("W38 实际低于周均（假信号前提仍成立）",
   next((t["total"] for t in trend if t["week"] == "2026-W38"), 0) < ts["avg_week"])
ok("识别到 W43 突增", any(a["week"] == "2026-W43" and a["type"] == "spike"
                       for a in ts["anomaly_weeks"]))
ok("识别到 W37 骤降", any(a["week"] == "2026-W37" and a["type"] == "dip"
                       for a in ts["anomaly_weeks"]))
ok("trend 每项含 days/complete/anomaly 字段", all(
   {"days", "complete", "anomaly"} <= set(t) for t in trend))

print("\n── 三、展示 = 下钻 = 导出（逐条）──")
for c in d["categories"]:
    ok(f"分类「{c['name']}」展示 {c['cnt']} == 下钻", tickets_total({"l1": c["name"]}) == c["cnt"],
       f"下钻={tickets_total({'l1': c['name']})}")
for p in d["top_problems"][:5]:
    q = {"module_problem_id": p["module_problem_id"]}
    n, e = tickets_total(q), export_rows(q)
    ok(f"高频问题「{p['name'][:12]}」展示 {p['cnt']} == 下钻", n == p["cnt"], f"下钻={n}")
    ok(f"  └ 导出同口径", e == p["cnt"], f"导出={e}")
for st in cl["status_breakdown"]:
    ok(f"状态「{st['name']}」展示 {st['cnt']} == 下钻",
       tickets_total({"status": st["name"]}) == st["cnt"])
ok("未归类结论 == 下钻 unclassified=1", tickets_total({"unclassified": 1}) == pc["unclassified"],
   f"{pc['unclassified']} 单")
ok("未闭环 KPI == 下钻 unclosed=1", tickets_total({"unclosed": 1}) == cl["open"])
ok("批量投诉 == 下钻 is_batch=1", tickets_total({"is_batch": 1}) == cl["batch"])
ok("滞留 == 下钻 retention=1", tickets_total({"retention": 1}) == cl["retention"])
all_rows = export_rows()
ok("全量导出行数 == 总量", all_rows == total, f"{all_rows} vs {total}")
ok("峰值周下钻 == trend 该周单量",
   tickets_total({"week": ts["peak_week"]}) == ts["peak_total"])

print("\n── 四、关键结论摘要与周维度兼容 ──")
cs = d["conclusions"]
ok("结论条数 ≥ 10 且非空", len(cs) >= 10, str(len(cs)))
ok("每条结论含 text / filters / level", all(
   c.get("text") and isinstance(c.get("filters"), dict) and c.get("level") for c in cs))
ok("含异常波动结论", any(c["kind"] == "anomaly" for c in cs))
ok("含闭环结论且明确「已回复 ≠ 结单」", any(
   "已回复 ≠ 结单" in c["text"] for c in cs))
ok("含进行中周提示", any(c["kind"] == "in_progress" for c in cs))
ok("含未归类（待自动补跑，不转人工）", any(
   "待自动补跑" in c["text"] and c["filters"].get("unclassified") == 1 for c in cs))
ok("结论 filters 均可下钻出单量 > 0", all(
   tickets_total(c["filters"]) > 0 for c in cs if c["filters"]),
   str([(c["kind"], c["filters"]) for c in cs if not tickets_total(c["filters"])]))
ok("/overall 固定全表口径：传 week 参数不改变结果",
   api("/api/v1/complaint/overall", {"week": "2026-W45"})["scope"]["total"] == total)
m = api("/api/v1/complaint/metrics", {"week": "2026-W45"})
ok("周维度 /metrics 未被破坏", m.get("week") == "2026-W45" and m.get("total", 0) > 0,
   f"W45 total={m.get('total')}")
ok("周维度下钻仍带周口径", tickets_total({"week": "2026-W45"}) == m["total"])

print("\n" + "=" * 72)
print(f"结果：{PASS} 通过 / {FAIL} 失败")
if FAILED:
    print("失败项：" + " | ".join(FAILED))
print(("ALL_PASS" if FAIL == 0 else "HAS_FAILURE"))
raise SystemExit(1 if FAIL else 0)
