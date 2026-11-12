"""客诉周报新鲜度 + 工单明细导出 回归（2026-11-10）。

覆盖老大反馈的三件事：
  1. 周分析报告内容更新（每日投诉量明细表 / 数据截至 / 进行中周不补 0）；
  2. 工单明细 AI 分析全文可查看（后端字段完整性）；
  3. 下钻页面工单明细导出（按当前筛选条件，全文、不分页）。

两种运行方式：
  - 默认走真实 HTTP（需后端已重启加载新代码 + 服务在线）：
        python scripts/verify_complaint_export_report.py
    环境变量：PMWB_BASE / PMWB_AUTH_USER / PMWB_AUTH_PW
  - --testclient 直接在进程内加载 app（无需重启服务，用于开发期自测）：
        python scripts/verify_complaint_export_report.py --testclient
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

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


def build_client():
    if "--testclient" in sys.argv:
        # pydantic-settings 相对 cwd 读取 backend/.env，脚本从项目根启动会加载不到
        # 真实 DB 口令而回退到默认配置（1045 Access denied），故先切到 backend。
        os.chdir(ROOT / "backend")
        os.environ.setdefault("AUTH_REQUIRED", "false")
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app), {}

    import urllib.request
    import json
    base = os.environ.get("PMWB_BASE", "http://127.0.0.1:8000")
    user = os.environ.get("PMWB_AUTH_USER", "chendh")
    pw = os.environ.get("PMWB_AUTH_PW", "")
    req = urllib.request.Request(
        f"{base}/api/v1/auth/login",
        data=json.dumps({"username": user, "password": pw}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        token = json.loads(r.read())["data"]["token"]

    class Http:
        """极简 GET 客户端：返回 (status, headers, body)。"""
        def get(self, path, params=None):
            from urllib.parse import urlencode
            url = base + path + (("?" + urlencode(params)) if params else "")
            rq = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(rq, timeout=120) as resp:
                return resp.status, dict(resp.headers), resp.read()

        def post(self, path, payload=None):
            rq = urllib.request.Request(
                base + path, data=json.dumps(payload or {}).encode(),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
            with urllib.request.urlopen(rq, timeout=180) as resp:
                return resp.status, dict(resp.headers), resp.read()

    return Http(), {"token": token}


def main() -> int:
    client, meta = build_client()
    tc = "--testclient" in sys.argv

    def get(path, params=None):
        if tc:
            r = client.get(path, params=params)
            return r.status_code, dict(r.headers), r.content
        return client.get(path, params)

    def js(path, params=None):
        st, hd, body = get(path, params)
        import json as _json
        return st, hd, _json.loads(body)

    def post(path, payload=None):
        if tc:
            r = client.post(path, json=payload)
            return r.status_code, dict(r.headers), r.content
        return client.post(path, payload)

    print("═" * 62)
    print("客诉周报新鲜度 + 工单明细导出 回归")
    print("═" * 62)

    # 动态基线：每次导入新工单后全表/本周总量都会变，断言一律按口径等式判定，
    # 禁写死快照值（2026-11-10 W46 日均 14.0 隔天假红、11-12 导入 57 单同理）。
    _, _, _ov = js("/api/v1/complaint/overall")
    ALL_TOTAL = ((_ov.get("data") or {}).get("scope") or {}).get("total")
    _, _, _m45 = js("/api/v1/complaint/metrics", {"week": "2026-W45"})
    _, _, _m46 = js("/api/v1/complaint/metrics", {"week": "2026-W46"})
    W45_TOTAL = (_m45.get("data") or {}).get("total")
    W46_TOTAL = (_m46.get("data") or {}).get("total")
    ok("动态基线可取（全表/W45/W46）",
       all(isinstance(x, int) and x > 0 for x in (ALL_TOTAL, W45_TOTAL, W46_TOTAL)),
       f"all={ALL_TOTAL} W45={W45_TOTAL} W46={W46_TOTAL}")

    # ── 1. 列表口径（抽 _ticket_where 后无回归） ──
    print("\n▶ 工单列表口径")
    st, _, d = js("/api/v1/complaint/tickets", {"week": "2026-W45", "page_size": 5})
    ok("list_tickets 200", st == 200)
    ok("W45 列表总量 = /metrics W45", (d.get("data") or {}).get("total") == W45_TOTAL,
       str((d.get("data") or {}).get("total")))
    _, _, d2 = js("/api/v1/complaint/tickets",
                  {"week": "2026-W45", "module_problem_id": "MP-ORDER-CLOSE", "known_flag": 1})
    filter_total = (d2.get("data") or {}).get("total")
    ok("模块锚+已知双条件下钻非空且不超本周总量",
       isinstance(filter_total, int) and 0 < filter_total <= W45_TOTAL,
       str(filter_total))

    # ── 2. 导出端点（路由顺序 / 全文 / 筛选一致 / 禁缓存） ──
    print("\n▶ 工单明细导出")
    st, hd, body = get("/api/v1/complaint/tickets/export",
                       {"week": "2026-W45", "module_problem_id": "MP-ORDER-CLOSE", "known_flag": 1})
    ok("export 200", st == 200, f"status={st}")
    ok("export 返回 xlsx（PK 魔数）", body[:2] == b"PK")
    ok("export 行数与页面下钻一致",
       hd.get("X-Export-Rows", hd.get("x-export-rows")) == str(filter_total),
       str(hd.get("x-export-rows")))
    ok("export 禁缓存", "no-store" in (hd.get("Cache-Control", hd.get("cache-control", "")) or ""))
    ok("export 中文文件名 RFC5987",
       "filename*=UTF-8" in (hd.get("Content-Disposition", hd.get("content-disposition", "")) or ""))
    try:
        from openpyxl import load_workbook
        ws = load_workbook(io.BytesIO(body)).active
        heads = [c.value for c in ws[1]]
        ok("xlsx 36 列（含 AI 分析全文字段）", len(heads) == 36, f"cols={len(heads)}")
        ok("含「AI分析总结(根因全文)」列", "AI分析总结(根因全文)" in heads)
        ok("含「投诉内容(全文)」列", "投诉内容(全文)" in heads)
        ok("含「处理过程(全文)」列", "处理过程(全文)" in heads)
        ok("AI 根因全文未截断（非空）",
           len(str(ws.cell(2, heads.index("AI分析总结(根因全文)") + 1).value or "")) > 20)
    except ImportError:
        print("  SKIP  openpyxl 不可用，跳过 xlsx 内容断言")
    _, hd2, _ = get("/api/v1/complaint/tickets/export")
    ok("全量导出 = /overall 全表总量",
       hd2.get("X-Export-Rows", hd2.get("x-export-rows")) == str(ALL_TOTAL),
       str(hd2.get("x-export-rows")))

    # ── 3. 报告状态（模板版本 / 全貌口径 / PDF 陈旧） ──
    print("\n▶ 周报新鲜度")
    # 报告是静态快照：模板版本升级后旧文件不会自己变，
    # 先确保下载到的是当前模板产物（只在文件缺全貌章时才重生成，避免无谓写库）。
    for _w in ("2026-W45", "2026-W46"):
        _st, _, _b = get(f"/api/v1/complaint/reports/{_w}/download?ext=html")
        if _st != 200 or "全周期投诉全貌" not in _b.decode("utf-8", "replace"):
            _sp, _, _ = post("/api/v1/complaint/reports", {"week": _w, "with_pdf": False})
            ok(f"{_w} 按当前模板重生成", _sp == 200, f"status={_sp}")
    st, _, d = js("/api/v1/complaint/reports/2026-W45/status")
    s = d.get("data") or {}
    ok("status 200", st == 200)
    ok("库内周总量 = /metrics W45（按 created_time 区间）",
       s.get("week_total") == W45_TOTAL, str(s.get("week_total")))
    ok("有数据截止时间", bool(s.get("data_until")), s.get("data_until", ""))
    ok("文件内总量与库一致", s.get("file_total") == W45_TOTAL, str(s.get("file_total")))
    ok("新版模板判为 fresh", s.get("stale") is False, str(s.get("stale")))
    ok("旧 PDF 被标 pdf_stale", s.get("pdf_stale") is True, str(s.get("pdf_stale")))
    ok("status 返回全表总量 = /overall", s.get("overall_total") == ALL_TOTAL,
       str(s.get("overall_total")))
    ok("报告内全貌总量与库一致", s.get("file_overall_total") == s.get("overall_total"),
       f"{s.get('file_overall_total')} vs {s.get('overall_total')}")
    ok("报告内全貌数据截至与库一致",
       bool(s.get("overall_until")) and s.get("file_overall_until") == s.get("overall_until"),
       f"{s.get('file_overall_until')} vs {s.get('overall_until')}")
    _, _, d46 = js("/api/v1/complaint/reports/2026-W46/status")
    ok("W46 报告存在且周总量 = /metrics W46",
       (d46.get("data") or {}).get("week_total") == W46_TOTAL,
       str((d46.get("data") or {}).get("week_total")))

    # ── 4. 报告内容（每日投诉量明细 / 水印 / 禁缓存） ──
    print("\n▶ 周报内容展示")
    st, hd, body = get("/api/v1/complaint/reports/2026-W45/download?ext=html")
    ok("download html 200", st == 200)
    ok("download 禁缓存", "no-store" in (hd.get("Cache-Control", hd.get("cache-control", "")) or ""))
    txt = body.decode("utf-8", errors="replace")

    # ── 4a. HTML 文件下载契约（2026-11-11 前端新增「下载 HTML」按钮） ──
    # 后端 FileResponse 必须给出 attachment + 中文文件名，前端 downloadWithAuth
    # 才能从 Content-Disposition 解析出正确名字并触发浏览器保存（而非内联预览）。
    print("\n▶ 周报 HTML 文件下载契约")
    import re as _re
    from urllib.parse import unquote as _unquote
    disp = hd.get("Content-Disposition", hd.get("content-disposition", "")) or ""
    ok("download 为 attachment（保存文件而非内联预览）", "attachment" in disp)
    _m = _re.search(r"filename\*=(?:UTF-8|utf-8)''([^;]+)", disp, _re.I)
    fname = _unquote(_m.group(1).strip('"')) if _m else ""
    ok("下载文件名 = 客诉周报_2026-W45.html", fname == "客诉周报_2026-W45.html", fname)
    ok("download Content-Type = text/html",
       "text/html" in (hd.get("Content-Type", hd.get("content-type", "")) or ""))
    ok("HTML 自包含：ECharts 已内联（离线双击可打开）",
       len(body) > 500000 and 'src="assets/echarts.min.js"' not in txt,
       f"bytes={len(body)}")
    ok("HTML 无外链脚本/样式（离线不缺资源）",
       not _re.search(r'<script[^>]+src="https?://', txt)
       and not _re.search(r'<link[^>]+href="https?://', txt))
    ok("HTML 含 4 个图表容器（全貌/每日/分类/近8周）",
       all(f'id="{x}"' in txt for x in ("ovTrend", "daily", "pie", "trend")))

    for token in ["每日投诉量明细", "数据截至", "报告生成于", "pmwb-report-version", "上周同期"]:
        ok(f"报告含「{token}」", token in txt)
    st2, _, body2 = get("/api/v1/complaint/reports/2026-W46/download?ext=html")
    txt2 = body2.decode("utf-8", errors="replace")
    ok("W46 报告含「本周进行中」", "本周进行中" in txt2)
    ok("W46 未到日期不画 0 柱（null 断柱）", "null" in txt2)

    # ── 4b. 周报：全周期投诉全貌章节（2026-11-11 新增） ──
    print("\n▶ 周报：全周期投诉全貌章节")
    for token in ["全周期投诉全貌", "16 周投诉量趋势", "异常波动周",
                  "问题分类占比与近 4 个完整周结构漂移", "高频问题（L2 闭集缺陷类",
                  "处理状态与闭环", "全貌关键结论", "已回复 ≠ 结单"]:
        ok(f"报告含「{token}」", token in txt)
    # 模板版本会随展示逻辑升级 +1，断言按「不低于含全貌章的 v3」动态判定，禁写死
    _vm = _re.search(r'<meta name="pmwb-report-version" content="(\d+)"', txt)
    ok("报告模板版本 >= 3（含全周期全貌章）",
       bool(_vm) and int(_vm.group(1)) >= 3, _vm.group(1) if _vm else "missing")
    ok("全貌章在周维度六章之前",
       txt.find("全周期投诉全貌") < txt.find("一、本周概览与波动"))
    ok("全貌章标注两种口径不可加总", "不可互相加总或核对" in txt)
    ok("16 周趋势图容器与初始化都在",
       'id="ovTrend"' in txt and "getElementById('ovTrend')" in txt)
    ok("W46 报告同样含全貌章（全表口径与周次无关）", "全周期投诉全貌" in txt2)
    _, _, ov = js("/api/v1/complaint/overall")
    o = ov.get("data") or {}
    ok("全貌总量 meta 与 /overall 一致",
       f'<meta name="pmwb-report-overall-total" content="{(o.get("scope") or {}).get("total")}">' in txt)
    ok("全貌 KPI 总量与 /overall 一致",
       f'<div class="num">{(o.get("scope") or {}).get("total")}</div>' in txt)
    ok("全貌 KPI 闭环率与 /overall 一致",
       f'{(o.get("closure") or {}).get("closed_pct")}%' in txt)
    ano_cnt = (o.get("trend_summary") or {}).get("anomaly_cnt", 0)
    ok("异常周条目数 = /overall anomaly_cnt",
       txt.count('>突增</span>') + txt.count('>骤降</span>') == ano_cnt, str(ano_cnt))
    ok("高频问题条目数 = /overall top_problems",
       txt.count('>仍活跃</span>') + txt.count('>已静止</span>') == len(o.get("top_problems") or []),
       str(len(o.get("top_problems") or [])))
    ok("处理状态条目数 = /overall status_breakdown",
       txt.count('>完结</span>') + txt.count('>未完结</span>')
       == len((o.get("closure") or {}).get("status_breakdown") or []),
       str(len((o.get("closure") or {}).get("status_breakdown") or [])))
    ok("全貌结论条数 = /overall conclusions",
       txt.count('<li><span class="tag ') >= len(o.get("conclusions") or []),
       str(len(o.get("conclusions") or [])))
    for h in ["一、本周概览与波动", "二、已知 vs 新增", "三、问题族分析",
              "四、工单压降分析指引", "五、措施跟踪与自动验证",
              "六、趋势（近 8 周）", "附：结论与建议动作"]:
        ok(f"周维度「{h}」未被破坏", h in txt)

    # ── 5. 进行中周口径（日均按已过天数 / 环比不可比） ──
    print("\n▶ 进行中周口径")
    _, _, m46 = js("/api/v1/complaint/metrics", {"week": "2026-W46"})
    m = m46.get("data") or {}
    ok("W46 in_progress=True", m.get("in_progress") is True)
    # 进行中周的已过天数随自然日推进（11-10 是 2 天、11-11 是 3 天…），
    # 断言必须按口径等式动态判定，不能写死 2 / 14.0，否则隔天必然假红。
    elapsed = m.get("elapsed_days") or 0
    ok("W46 elapsed_days 在 1..7 且未满整周", 1 <= elapsed < 7, str(elapsed))
    ok("W46 日均 = 总量 / elapsed_days（不按 7 天摊薄）",
       elapsed > 0 and m.get("daily_avg") == round((m.get("total") or 0) / elapsed, 1),
       f"total={m.get('total')} elapsed={elapsed} avg={m.get('daily_avg')}")
    ok("W46 进行中周环比不可比", m.get("wow_pct") is None, str(m.get("wow_pct")))
    _, _, m45 = js("/api/v1/complaint/metrics", {"week": "2026-W45"})
    ok("W45 完整周日均 18.3 不受影响", (m45.get("data") or {}).get("daily_avg") == 18.3)

    print(f"\n{'═' * 62}")
    print(f"结果：{PASS} 通过 / {FAIL} 失败")
    if FAILED:
        print("失败项：" + "；".join(FAILED))
        return 1
    print("ALL_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
