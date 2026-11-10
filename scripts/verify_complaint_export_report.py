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

    print("═" * 62)
    print("客诉周报新鲜度 + 工单明细导出 回归")
    print("═" * 62)

    # ── 1. 列表口径（抽 _ticket_where 后无回归） ──
    print("\n▶ 工单列表口径")
    st, _, d = js("/api/v1/complaint/tickets", {"week": "2026-W45", "page_size": 5})
    ok("list_tickets 200", st == 200)
    ok("W45 总量 128", (d.get("data") or {}).get("total") == 128,
       str((d.get("data") or {}).get("total")))
    _, _, d2 = js("/api/v1/complaint/tickets",
                  {"week": "2026-W45", "module_problem_id": "MP-ORDER-CLOSE", "known_flag": 1})
    ok("模块锚+已知双条件下钻 = 19", (d2.get("data") or {}).get("total") == 19,
       str((d2.get("data") or {}).get("total")))

    # ── 2. 导出端点（路由顺序 / 全文 / 筛选一致 / 禁缓存） ──
    print("\n▶ 工单明细导出")
    st, hd, body = get("/api/v1/complaint/tickets/export",
                       {"week": "2026-W45", "module_problem_id": "MP-ORDER-CLOSE", "known_flag": 1})
    ok("export 200", st == 200, f"status={st}")
    ok("export 返回 xlsx（PK 魔数）", body[:2] == b"PK")
    ok("export 行数与页面一致 = 19", hd.get("X-Export-Rows", hd.get("x-export-rows")) == "19",
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
    ok("全量导出 = 1582 单", hd2.get("X-Export-Rows", hd2.get("x-export-rows")) == "1582",
       str(hd2.get("x-export-rows")))

    # ── 3. 报告状态（模板版本 / 数据截止 / PDF 陈旧） ──
    print("\n▶ 周报新鲜度")
    st, _, d = js("/api/v1/complaint/reports/2026-W45/status")
    s = d.get("data") or {}
    ok("status 200", st == 200)
    ok("库内周总量 128（按 created_time 区间）", s.get("week_total") == 128, str(s.get("week_total")))
    ok("有数据截止时间", bool(s.get("data_until")), s.get("data_until", ""))
    ok("文件内总量与库一致 128", s.get("file_total") == 128, str(s.get("file_total")))
    ok("新版模板判为 fresh", s.get("stale") is False, str(s.get("stale")))
    ok("旧 PDF 被标 pdf_stale", s.get("pdf_stale") is True, str(s.get("pdf_stale")))
    _, _, d46 = js("/api/v1/complaint/reports/2026-W46/status")
    ok("W46 报告存在且 28 单", (d46.get("data") or {}).get("week_total") == 28)

    # ── 4. 报告内容（每日投诉量明细 / 水印 / 禁缓存） ──
    print("\n▶ 周报内容展示")
    st, hd, body = get("/api/v1/complaint/reports/2026-W45/download?ext=html")
    ok("download html 200", st == 200)
    ok("download 禁缓存", "no-store" in (hd.get("Cache-Control", hd.get("cache-control", "")) or ""))
    txt = body.decode("utf-8", errors="replace")
    for token in ["每日投诉量明细", "数据截至", "报告生成于", "pmwb-report-version", "上周同期"]:
        ok(f"报告含「{token}」", token in txt)
    st2, _, body2 = get("/api/v1/complaint/reports/2026-W46/download?ext=html")
    txt2 = body2.decode("utf-8", errors="replace")
    ok("W46 报告含「本周进行中」", "本周进行中" in txt2)
    ok("W46 未到日期不画 0 柱（null 断柱）", "null" in txt2)

    # ── 5. 进行中周口径（日均按已过天数 / 环比不可比） ──
    print("\n▶ 进行中周口径")
    _, _, m46 = js("/api/v1/complaint/metrics", {"week": "2026-W46"})
    m = m46.get("data") or {}
    ok("W46 in_progress=True", m.get("in_progress") is True)
    ok("W46 elapsed_days=2", m.get("elapsed_days") == 2, str(m.get("elapsed_days")))
    ok("W46 日均 14.0（不再 4.0）", m.get("daily_avg") == 14.0, str(m.get("daily_avg")))
    ok("W46 环比不可比（不再 -78.1%）", m.get("wow_pct") is None, str(m.get("wow_pct")))
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
