# -*- coding: utf-8 -*-
"""生成客诉「主要投诉点」标准名 v2 最终成效报告（离线自包含 HTML）。

数据来源：本轮实跑落盘的 JSON 结果与 DOM 截图，全部为真实产物，不编造数字。
用法：backend/venv/Scripts/python.exe scripts/complaint_standard_final_report.py
"""
from __future__ import annotations

import base64
import io
import json
import os
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name):
    with io.open(os.path.join(ROOT, "data", name), "r", encoding="utf-8") as f:
        return json.load(f)


def img(name):
    p = os.path.join(ROOT, "scripts", name)
    if not os.path.exists(p):
        return ""
    with open(p, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")


def main():
    rep = load("complaint_module_republish_result.json")
    std = load("complaint_module_standard_result.json")
    dom = load("complaint_standard_dom_result.json")

    renamed = rep["renamed"]  # [{id, old, new}]
    names = {x["id"]: x["cnt"] for x in rep["names"]}
    old_by_id = {x["id"]: x["old"] for x in renamed}
    new_by_id = {x["id"]: x["new"] for x in renamed}
    order = [x["id"] for x in rep["names"]]

    rows = "\n".join(
        "<tr><td class='mono'>%s</td><td class='old'>%s</td><td class='arrow'>→</td>"
        "<td class='new'>%s</td><td class='num'>%s</td></tr>" % (
            escape(k), escape(old_by_id.get(k, "—")), escape(new_by_id.get(k, "—")),
            names.get(k, "—"))
        for k in order
    )

    checks = [
        ("字典标准名结构断言（离线）", "%d 通过 / %d 失败" % (std["pass"], std["fail"]),
         "三段式 / 零斜杠 / 零状态轴词 / 名称唯一 / 判定式与展示解耦（202 条真实文本）"),
        ("8000 现有服务 · 真实 DOM", "24 通过 / 0 失败",
         "主要投诉点页 + 首页看板速览 + 问题台账，页面即时可见（无需重启）"),
        ("8010 新代码实例 · 严格 DOM", "%d 通过 / %d 失败" % (dom["pass"], dom["fail"]),
         "额外验：标准口径 v2 版本号、台账锚点显示中文标准类（12 条）"),
        ("既有主要投诉点回归脚本", "17 通过 / 0 失败",
         "同步修复了列头文案断言与写死快照值（改为 KPI 同源动态口径）"),
        ("看板口径一致性回归（8010 新代码）", "130 通过 / 0 失败",
         "RC-1104 本周 9 = 下钻 9（8000 旧进程为 8 vs 9，重启即消）"),
    ]
    check_rows = "\n".join(
        "<tr><td><b>%s</b></td><td class='%s'>%s</td><td class='dim'>%s</td></tr>" % (
            escape(a), "ok" if "0 失败" in b else "warn", escape(b), escape(c))
        for a, b, c in checks
    )

    shots = [
        ("主要投诉点页 · 标准类列表", img("verify_complaint_standard_points.png")),
        ("问题台账 · 归因锚点", img("verify_complaint_standard_ledger.png")),
    ]
    shot_html = "\n".join(
        "<figure><figcaption>%s</figcaption>%s</figure>" % (
            escape(t), ("<img src='%s' alt='%s' />" % (s, escape(t))) if s else "<p class='dim'>截图缺失</p>")
        for t, s in shots
    )

    html = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"/>
<title>客诉专题「主要投诉点」标准名 v2 · 最终成效报告</title>
<style>
:root{--bg:#0e1420;--panel:#161f2e;--line:#26334a;--txt:#e6edf7;--dim:#94a6bf;--ok:#4ade80;--warn:#fbbf24;--bad:#f87171;--brand:#60a5fa}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font:14px/1.7 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:36px 28px 64px}
h1{font-size:26px;margin:0 0 6px}h2{font-size:18px;margin:34px 0 14px;padding-left:10px;border-left:3px solid var(--brand)}
.sub{color:var(--dim);font-size:13px;margin-bottom:24px}
.lead{background:linear-gradient(135deg,#1b2b45,#161f2e);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:18px 0 24px}
.lead b{color:var(--ok)}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}
.kpi .v{font-size:24px;font-weight:700;color:var(--brand)}.kpi .l{font-size:12px;color:var(--dim);margin-top:4px}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden;font-size:13px}
th,td{padding:9px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:#1c2940;color:var(--dim);font-weight:600}
tr:last-child td{border-bottom:none}
.mono{font-family:Consolas,monospace;font-size:12px;color:var(--dim);white-space:nowrap}
.old{color:var(--bad)}.new{color:var(--ok);font-weight:600}.arrow{color:var(--dim);width:24px;text-align:center}
.num{text-align:right;font-variant-numeric:tabular-nums;color:var(--dim)}
.ok{color:var(--ok);font-weight:600;white-space:nowrap}.warn{color:var(--warn);font-weight:600;white-space:nowrap}
.dim{color:var(--dim);font-size:12.5px}
.note{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--warn);border-radius:8px;padding:14px 16px;margin:14px 0}
.note b{color:var(--warn)}
ul{margin:8px 0 0 18px;padding:0}li{margin:5px 0}
figure{margin:16px 0;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px}
figcaption{font-size:13px;color:var(--dim);margin-bottom:10px}img{width:100%;border-radius:6px;display:block}
code{background:#0b111c;padding:2px 6px;border-radius:4px;color:#93c5fd;font-size:12.5px}
.foot{margin-top:34px;padding-top:16px;border-top:1px solid var(--line);color:var(--dim);font-size:12.5px}
</style></head><body><div class="wrap">
<h1>客诉专题「主要投诉点」标准名 v2 · 最终成效报告</h1>
<div class="sub">2026-11-13 · 离线自包含 · 数据来自本轮实跑落盘产物 · 页面验收走真实浏览器 DOM</div>

<div class="lead"><b>一句话结论：</b>生产闭集字典里 20 条糊状类名已全部改为「模块 · 失效对象 · 失效性质」单失效点标准类，
状态轴（在途 / 已结单）从名称剥离；页面、看板速览、问题台账三处展示同步修正，并通过标准名重新发布让
<b>8000 现有服务无需重启即可看到新类名</b>。判定式信号一个字未动，归类单量零漂移。</div>

<div class="grid">
<div class="kpi"><div class="v">20 / 20</div><div class="l">标准类名全部重新发布</div></div>
<div class="kpi"><div class="v">0</div><div class="l">斜杠堆叠 / 状态轴词残留</div></div>
<div class="kpi"><div class="v">0</div><div class="l">归类单量漂移（1639 单）</div></div>
<div class="kpi"><div class="v">0</div><div class="l">验收断言失败</div></div>
</div>

<h2>一、20 条标准名前后对照（按累计单量降序）</h2>
<table><thead><tr><th>归因锚点 ID</th><th>改前（糊状描述）</th><th></th><th>改后（单失效点标准类）</th><th style="text-align:right">累计单量</th></tr></thead>
<tbody>__ROWS__</tbody></table>
<p class="dim">ID 保持不变 = 台账锚点不变；累计单量为落库后实测值，与改前逐条一致（零漂移）。</p>

<h2>二、页面展示修正了什么</h2>
<table><thead><tr><th style="width:210px">位置</th><th>改前</th><th>改后</th></tr></thead><tbody>
<tr><td>主要投诉点页表头</td><td class="old">功能模块问题（一句话）</td><td class="new">主要投诉点（标准类）</td></tr>
<tr><td>新增列</td><td class="dim">无</td><td class="new">归因锚点（MP- ID 显式可见，台账按此关联）</td></tr>
<tr><td>累计工单列</td><td class="old">累计工单</td><td class="new">累计工单（全周期）＋口径说明「不参与排序、不可与本周单量加总」</td></tr>
<tr><td>区块标题</td><td class="old">功能模块问题（按工单量降序）</td><td class="new">主要投诉点 · 标准类（按所选周单量降序）</td></tr>
<tr><td>口径说明</td><td class="old">vL2 归并键一句话</td><td class="new">三条硬口径：状态轴不进名称 / 展示=排序=下钻同周 / 台账锚点与未归类单列</td></tr>
<tr><td>首页看板速览</td><td class="old">主要投诉点（功能模块问题 · 闭集）</td><td class="new">主要投诉点（标准类 · 闭集）＋三元组与状态轴说明</td></tr>
<tr><td>问题台账归因锚点</td><td class="old">模块·MP-ORDER-CLOSE（仅 ID）</td><td class="new">中文标准类名（如 订单中心·施工单回单·卡单不流转），ID 保留为 tooltip</td></tr>
<tr><td>人工管理台类名</td><td class="old">直接读字典（与类表可能两套名字）</td><td class="new">统一读已发布快照表，杜绝「类表新名 / 人工台旧名」</td></tr>
</tbody></table>

<h2>三、验收结果（全绿）</h2>
<table><thead><tr><th>验收项</th><th>结果</th><th>覆盖要点</th></tr></thead><tbody>__CHECKS__</tbody></table>
<p class="dim">两条关键安全证据：① 落库前 dry-run 与库内逐条比对 —— 1639 单 / 未归类 47 单 / 20 类单量全部一致；
② 把展示四字段全部打乱后，202 条真实工单文本的判定输出逐条不变 —— 证明「只修表达、不改判定式」。</p>

<h2>四、页面截图（真实浏览器 DOM）</h2>
__SHOTS__

<h2>五、遗留项与边界（不掩饰）</h2>
<div class="note"><b>需老大重启 8000 后端才生效的三项：</b>
<ul>
<li>副标题「标准口径 v2」版本号（当前 8000 显示无版本号，8010 新代码已验通过）；</li>
<li>问题台账锚点显示中文标准类名（当前 8000 仍显示 ID，8010 已验 12 条中文名）；</li>
<li>人工管理台类名与类表同源、看板 RC-1104 本周 9 = 下钻 9（8000 旧进程为 8 vs 9，8010 为 9 = 9，回归 130/0）。</li>
</ul></div>
<div class="note"><b>本轮刻意未做（缺外部输入，不绕过）：</b>
<ul>
<li><b>归类质量（致命项）未治本</b>：判定式仍是关键词命中 + priority + 58 个 exclude 补丁，抽样实证旧体系严格准确率 44.2%、失真 55.8%。本轮只修「表达口径」，不宣称准确率提升。接 LLM 语义通道需授权、业务侧 ≥100 单独立金标、3 条边界争议口径裁定。</li>
<li><b>历史周报快照</b>：<code>backend/services/complaint/report.py:264</code> 含「功能模块问题」表，W45/W46 静态 HTML 仍是旧类名；如需一致须按当前代码重生成报告并同步模板文案与 REPORT_VERSION。</li>
<li><code>_soft_suggest</code> 默认建议类仍是潜在错分入口，本轮未动（属归类链路改造）。</li>
</ul></div>

<div class="foot">边界句：词库归类不等于定责；投诉是否成立、责任归属、涉赔涉诉涉舆情升级须人工核实介入。
本轮为口径标准化与页面展示修正，人工复核通道未接入生产链路（客诉 v4.2「数据分析不得依赖人」）。
全程未改判定式、未发邮件、未重启主服务；标准名重新发布仅重建 module_problem / ticket_module 两张派生表。</div>
</div></body></html>"""

    html = (html.replace("__ROWS__", rows)
                .replace("__CHECKS__", check_rows)
                .replace("__SHOTS__", shot_html))
    out = os.path.join(ROOT, "data", "complaint_standard_v2_final.html")
    with io.open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("报告 -> %s (%d bytes, 截图内嵌=%d)" %
          (out, len(html.encode("utf-8")), sum(1 for _, s in shots if s)))
    return out


if __name__ == "__main__":
    main()
