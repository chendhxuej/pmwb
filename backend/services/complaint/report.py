"""客诉周报渲染 —— HTML + PDF（模板固定 8 章，数据全部来自 metrics.collect）。

设计要点：
  - 模板只做展示，不做计算（指标一律来自 metrics，杜绝第二份口径）；
  - 结论段由数据驱动生成（不写死话术），数据变了结论跟着变；
  - 图表用本地 echarts，导 PDF 时先按打印宽度重绘再打印（避免图表被裁切）。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from services.complaint import config as C

ECHARTS_SRC = Path(r"D:\项目\个人工作台系统\frontend\node_modules\echarts\dist\echarts.min.js")

_ECHARTS_INLINE: Dict[str, str] = {}


def _echarts_tag() -> str:
    """图表库内联标签：周报 HTML 通过下载端点只回传单文件，
    外链 assets/echarts.min.js 在本地打开时缺失导致图表全空白（2026-10-27 事故），
    故内联为单文件自包含；读不到 JS 时降级保留外链（服务端 PDF 链路仍可用）。"""
    if "js" not in _ECHARTS_INLINE:
        try:
            _ECHARTS_INLINE["js"] = ECHARTS_SRC.read_text(encoding="utf-8").replace(
                "</script", "<\\/script")  # 防 HTML 提前闭合（JS 字符串内 \/ 等价 /）
        except OSError:
            _ECHARTS_INLINE["js"] = ""
    if _ECHARTS_INLINE["js"]:
        return f"<script>{_ECHARTS_INLINE['js']}</script>"
    return '<script src="assets/echarts.min.js"></script>'


def _pct(v: Optional[float], dash: str = "—") -> str:
    return dash if v is None else f"{v}%"


def _rows(items: List[Dict], cols: List[tuple]) -> str:
    if not items:
        return '<tr><td colspan="%d" style="text-align:center;color:#98a6ba">暂无数据</td></tr>' % len(cols)
    out = []
    for it in items:
        tds = "".join(f"<td>{fn(it)}</td>" for _, fn in cols)
        out.append(f"<tr>{tds}</tr>")
    return "".join(out)


_L1_MEANING = {
    "系统问题": "系统缺陷，需研发修复",
    "流程优化": "流程或规则不合理，需改造",
    "数据异常": "数据不一致/错误，需批量修复",
    "规则咨询": "客户对政策资费有疑问，解释即可化解",
    "操作咨询": "客户不熟悉操作，指引或代办即可化解",
}

_FIX_ACTION = {
    "批量修复": "出数据修复脚本，一次性回溯存量错误数据",
    "系统改造": "提需求排期改造（评估版本窗口）",
    "规则调整": "调整校验规则/配置口径，无需改代码",
    "逐单处理": "无法批量，只能逐单兜底（不产生压降空间）",
    "解释指引": "完善指引话术，压降重复咨询",
}

_REPORT_STYLE = """
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:#f5f7fa;color:#1f2d3d;padding:30px 0;line-height:1.7}
  .wrap{width:min(1080px,94%);margin:0 auto}
  h1{font-size:24px;margin-bottom:4px}
  .sub{color:#7a8ba3;font-size:13px;margin-bottom:22px}
  .card{background:#fff;border-radius:12px;padding:22px 26px;margin-bottom:18px;box-shadow:0 1px 4px rgba(31,45,61,.08);break-inside:avoid}
  h2{font-size:17px;margin-bottom:14px;border-left:4px solid #2f6fed;padding-left:10px}
  .kpi{display:grid;grid-template-columns:repeat(6,1fr);gap:11px}
  .kpi .item{background:#f0f5ff;border-radius:10px;padding:13px 10px;text-align:center}
  .kpi .num{font-size:23px;font-weight:800;color:#2f6fed;font-family:Consolas,monospace}
  .kpi .lbl{font-size:11.5px;color:#5a6b85;margin-top:3px}
  .heroline{display:grid;grid-template-columns:1.1fr 1fr 1fr 1fr;gap:14px;margin-bottom:14px}
  .hero{background:linear-gradient(135deg,#2f6fed,#4b8bff);border-radius:12px;padding:18px 20px;color:#fff}
  .hero .num{font-size:40px;font-weight:800;font-family:Consolas,monospace;line-height:1.1}
  .hero .lbl{font-size:12.5px;opacity:.9;margin-top:2px}
  .hero .desc{font-size:11.5px;opacity:.85;margin-top:6px}
  .mini{background:#f7f9fc;border-radius:10px;padding:14px 16px;text-align:center}
  .mini .num{font-size:26px;font-weight:800;font-family:Consolas,monospace;color:#1f2d3d}
  .mini .lbl{font-size:11.5px;color:#5a6b85}
  .chart{width:100%;height:300px}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th{background:#f0f4fa;text-align:left;padding:8px 10px;border-bottom:2px solid #dfe7f2}
  td{padding:7px 10px;border-bottom:1px solid #eef2f7;vertical-align:top}
  .tag{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600}
  .t-red{background:#fde8e8;color:#c0392b}.t-orange{background:#fff2e0;color:#d97706}
  .t-blue{background:#e8f1ff;color:#2f6fed}.t-green{background:#e5f7ed;color:#1e9e5a}
  .t-gray{background:#eef1f5;color:#5a6b85}
  .note{background:#f0f7ff;border-left:4px solid #2f6fed;padding:12px 15px;border-radius:6px;margin:10px 0;font-size:13px}
  .warn{background:#fff8ec;border-left:4px solid #e8a33d}
  ul{padding-left:20px}li{font-size:13.5px;line-height:1.9}
  .foot{color:#98a6ba;font-size:12px;text-align:center;margin-top:8px}
  .sub-h{font-size:14px;font-weight:700;margin:18px 0 8px;color:#1f2d3d}
"""

def render_html(m: Dict, problems: Optional[List[Dict]] = None) -> str:
    """渲染周分析报告（6 章，2026-11-04 重构为「分析」而非「统计」）。

    叙事主线（老大定的核心诉求）：
      本周多少单 → 是不是已知问题 → 是什么问题（五类+簇）→ 能压多少 → 治了没有。
    统计口径纪律：
      - 已知率分母 = 已判定单量（不是总单量），未分析的单不稀释指标；
      - 根因分布分母 = 已根因分析单量（信息不足单单独成桶，不进分母）；
      - 基期数据残缺时明确标「不可比」，绝不显示 0 充数。
    """
    l1 = m["by_l1"]
    pie_data = [{"value": x["cnt"], "name": x["name"]} for x in l1]
    trend_weeks = [t["week"].split("-")[1] for t in m["trend"]]
    trend_total = [t["total"] for t in m["trend"]]
    trend_batch = [t["batch"] for t in m["trend"]]
    daily_keys = [k[5:] for k in m["daily"].keys()]
    daily_vals = list(m["daily"].values())

    k = m.get("known") or {}
    rc = m.get("rootcause") or {}
    e = m["efficiency"]
    echarts_tag = _echarts_tag()

    known_rate = float(k.get("known_rate") or 0)
    known_cnt = int(k.get("known_cnt") or 0)
    new_cnt = int(k.get("new_cnt") or 0)
    unknown_cnt = int(k.get("unknown_cnt") or 0)
    consult_cnt = int(k.get("consult_cnt") or 0)
    judged = int(k.get("judged") or 0)
    pot_known = int(k.get("potential_known_cnt") or 0)

    # ── 一、概览与波动 ──
    if m.get("prev_partial"):
        wow_cell = f'<div class="num" style="font-size:17px">不可比</div>'
        wow_note = (f'<div class="note warn">上周（{m["prev_week"]}）仅有 {m["prev_days"]} 天数据，'
                    f'周环比不可比，本报告不给出环比结论。补导历史工单后自动恢复。</div>')
    elif m.get("wow_pct") is None:
        wow_cell = '<div class="num">—</div>'
        wow_note = '<div class="note warn">缺少可比基期数据，暂不给出环比结论。</div>'
    else:
        v = m["wow_pct"]
        color = "#c0392b" if v > 0 else "#1e9e5a"
        wow_cell = f'<div class="num" style="color:{color}">{v:+.1f}%</div>'
        wow_note = ""

    # ── 二、已知 vs 新增 ──
    known_rows = _rows(k.get("known_problems") or [], [
        ("问题编号", lambda x: f'<b>{x["problem_no"]}</b>'),
        ("在办问题（根因摘要）", lambda x: f'<b>{x["title"] or "—"}</b>'),
        ("责任人", lambda x: x.get("owner") or "—"),
        ("本周命中", lambda x: f'<b style="color:#c0392b">{x["cnt"]}</b> 单'),
        ("状态", lambda x: {"open": '<span class="tag t-blue">在办</span>',
                            "resolving": '<span class="tag t-orange">处理中</span>'}
            .get(x.get("status") or "", '<span class="tag t-gray">—</span>')),
    ]) if k.get("known_problems") else (
        '<tr><td colspan="5" style="color:#98a6ba;text-align:center">'
        '本周没有命中在办问题的工单——即没有一单能被「已在处理的问题」解释</td></tr>')

    new_cluster_rows = _rows((k.get("new_clusters") or [])[:12], [
        ("新增问题（根因簇）", lambda x: f'<b>{x["title"] or x["rootcause_no"] or "未归簇"}</b>'),
        ("系统", lambda x: x.get("fault_system") or "—"),
        ("环节", lambda x: x.get("fault_stage") or "—"),
        ("单量", lambda x: f'<b style="color:#c0392b">{x["cnt"]}</b>'),
        ("已提候选", lambda x: (
            f'<span class="tag t-blue">{x["cand_problem_no"]}</span>' if x.get("in_candidate")
            else '<span class="tag t-orange">待入账</span>')),
    ]) if k.get("new_clusters") else (
        '<tr><td colspan="5" style="color:#98a6ba;text-align:center">本周无新增问题</td></tr>')

    # ── 三、问题族（业务链路）+ 五类汇总 ──
    th = m.get("themes") or {}
    th_rows_data = th.get("themes") or []
    _wow_basis = (f"环比按日均对比（本周 {th.get('week_days', 0)} 天 / 上周 {th.get('prev_days', 0)} 天）"
                  if th.get("wow_basis") == "daily_avg" else "环比按周总量对比")

    def _wow_cell(x: Dict) -> str:
        v = x.get("wow")
        if v is None:
            # 本周无单 / 上周无单 / 上周数据不足：一律给「—」，绝不硬算成 -100%
            note = x.get("wow_note") or "不可比"
            return f'<span style="color:#98a6ba" title="{note}">—</span>'
        color = "#c0392b" if v > 0 else "#1f8a5c"
        tag = ' <span style="color:#98a6ba;font-size:11px">样本小</span>' if x.get("low_sample") else ""
        return f'<b style="color:{color}">{v:+.1f}%</b>{tag}'

    theme_rows = _rows(th_rows_data, [
        ("问题族（业务链路）", lambda x: ('<b>' + x["name"] + '</b>' +
                                    (' <span style="color:#c0392b;font-size:11px">本周新增</span>'
                                     if x.get("is_new") else ""))),
        ("本周", lambda x: f'<b style="color:#c0392b">{x["week_cnt"]}</b>'),
        ("本周日均", lambda x: str(x.get("avg", "—"))),
        ("上周日均", lambda x: str(x.get("prev_avg", "—"))),
        ("日均环比", _wow_cell),
        ("累计", lambda x: str(x.get("total_cnt", 0))),
        ("涉及问题簇", lambda x: str(x.get("problem_cluster_cnt", 0))),
        ("主要问题（累计 TOP3）", lambda x: '<br>'.join(
            f'{c["cnt"]} 单·{c["title"]}' for c in (x.get("top_clusters") or [])) or "—"),
    ]) if th_rows_data else (
        '<tr><td colspan="8" style="color:#98a6ba;text-align:center">暂无问题族数据</td></tr>')

    _cases = th.get("cases") or {}
    _unattr = th.get("unattributed") or {}
    case_note = (
        f'另有 <b>{_cases.get("cluster_cnt", 0)}</b> 个一次性个案（共 {_cases.get("ticket_cnt", 0)} 单，'
        f'仅出现 1 次、无同类可比），不计入族汇总；本周新增 {th.get("new_case_cnt", 0)} 个。'
    )
    if _unattr.get("cnt"):
        case_note += f' 未归因工单 {_unattr["cnt"]} 单（根因分析未完成），未摊入任何族。'

    l1_rows = "".join(
        f'<tr><td><b>{x["name"]}</b></td><td>{_L1_MEANING.get(x["name"], "—")}</td>'
        f'<td><b>{x["cnt"]}</b></td><td>{x["pct"]}%</td></tr>'
        for x in l1
    ) or '<tr><td colspan="4" style="color:#98a6ba;text-align:center">暂无数据</td></tr>'

    cluster_rows = _rows([x for x in (rc.get("clusters") or []) if int(x.get("cnt") or 0) >= 5][:15], [
        ("重点根因簇（累计 ≥5 单）", lambda x: f'<b>{x["title"]}</b>'),
        ("系统", lambda x: x.get("fault_system") or "—"),
        ("环节", lambda x: x.get("fault_stage") or "—"),
        ("缺陷性质", lambda x: x.get("fault_type") or "—"),
        ("责任归属", lambda x: x.get("own_party") or "—"),
        ("单量", lambda x: f'<b style="color:#c0392b">{x["cnt"]}</b>'),
        ("占比", lambda x: f'{x["pct"]}%'),
    ]) if rc.get("clusters") else (
        '<tr><td colspan="7" style="color:#98a6ba;text-align:center">本周尚无根因数据</td></tr>')

    # ── 四、压降指引 ──
    batch = rc.get("batch") or []
    win_cnt = sum(int(x.get("cnt") or 0) for x in batch)
    win_pct = round(win_cnt / int(rc.get("covered") or 1) * 100, 1) if rc.get("covered") else 0.0
    guide_rows = _rows(batch, [
        ("根因（改这里即可整批消掉）", lambda x: f'<b>{x["title"]}</b>'),
        ("系统", lambda x: x.get("fault_system") or "—"),
        ("责任方", lambda x: x.get("own_party") or "—"),
        ("覆盖单量", lambda x: f'<b style="color:#c0392b">{x["cnt"]}</b>'),
        ("处置方式", lambda x: x.get("fix_mode") or "—"),
        ("建议动作", lambda x: _FIX_ACTION.get(x.get("fix_mode") or "", "逐单核实后再定")),
    ]) if batch else (
        f'<tr><td colspan="6" style="color:#98a6ba;text-align:center">'
        f'本周未出现同根因簇 ≥{C.RC_BATCH_WEEK_MIN} 单的批量问题，没有可整批压降的空间</td></tr>')

    # ── 五、措施跟踪与验证 ──
    action_rows = _rows(m["actions"], [
        ("措施编号", lambda a: f'<b>{a["action_no"]}</b>'),
        ("所属问题", lambda a: (f'<b>{a["problem_no"]}</b>' if a.get("problem_no") else "—")),
        ("责任人", lambda a: a["owner"] or "—"),
        ("生效日", lambda a: str(a["go_live_date"] or "—")),
        ("基线/本周", lambda a: f'{a["baseline_cnt"] if a["baseline_cnt"] is not None else "—"} / '
                             f'{a["last_week_cnt"] if a["last_week_cnt"] is not None else "—"}'),
        ("实际降幅", lambda a: (f'<b style="color:{"#1e9e5a" if (a["actual_drop_pct"] or 0) >= 0 else "#c0392b"}">'
                            f'{a["actual_drop_pct"]:+.1f}%</b>'
                            if a["actual_drop_pct"] is not None else "待基线")),
        ("状态", lambda a: a["status"]),
    ]) if m["actions"] else (
        '<tr><td colspan="7" style="color:#98a6ba;text-align:center">'
        '本周尚未登记改进措施——问题不入账、不挂措施，下周的已知率仍会是 0</td></tr>')

    problem_rows = _rows(problems or [], [
        ("问题编号", lambda p: f'<b>{p["problem_no"]}</b>'),
        ("问题（根因摘要）", lambda p: f'<b>{p.get("title") or "—"}</b>'),
        ("状态", lambda p: p.get("status") or "—"),
        ("首见周", lambda p: p.get("first_week") or "—"),
        ("在办周", lambda p: str(p.get("active_weeks") if p.get("active_weeks") is not None else "—")),
        ("当周/累计", lambda p: f'{p.get("week_cnt") if p.get("week_cnt") is not None else "—"} / {p.get("total_cnt") or 0}'),
        ("措施", lambda p: f'{p.get("effective_cnt") or 0} / {p.get("action_cnt") or 0}'),
    ]) if problems is not None else (
        '<tr><td colspan="7" style="color:#98a6ba;text-align:center">—</td></tr>')

    # ── 结论（四问式）──
    concl_items = []
    if judged:
        concl_items.append(
            f"本周新增 <b>{m['total']}</b> 单，其中判为<b>已知问题</b> {known_cnt} 单"
            f"（已知率 <b>{known_rate}%</b>），<b>新增问题</b> {new_cnt} 单"
            + (f"，其余 {consult_cnt} 单为使用咨询（非缺陷）。" if consult_cnt else "。"))
    if not known_cnt and new_cnt:
        concl_items.append(
            "全部工单都不是在办问题能解释的——说明台账里几乎没有在办问题，"
            f"AI 已识别出 {pot_known} 单本应入账的问题（{k.get('inflight_problem_cnt', 0)} 个在办问题），"
            "**确认入账是本周最该做的一件事**。")
    if batch:
        concl_items.append(
            f"可整批压降空间：<b>{len(batch)}</b> 个根因簇、<b>{win_cnt}</b> 单"
            f"（占已分析单量的 {win_pct}%），修掉这些簇是压降主力。")
    if rc.get("insufficient"):
        concl_items.append(
            f"另有 {rc['insufficient']} 单工单信息不足（AI 已尽力，缺关键报错/处理意见），"
            "已单列不进统计分母——要提升根因质量需从工单填写侧补事实。")
    if not m["actions"]:
        concl_items.append("本周无措施在跟踪，压降闭环未启动。")
    concl = "".join(f"<li>{c}</li>" for c in concl_items) or "<li>本周无可分析数据。</li>"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>客诉工单专题分析 {m['week']}</title>
<style>{_REPORT_STYLE}</style>
</head>
<body>
<div class="wrap">
  <h1>商客客诉工单专题分析（{m['week']}）</h1>
  <div class="sub">统计区间 {m['range']}｜数据源：小信工单导出（逐单入库）｜
    根因与已知判定均为 AI 自动完成，人工只在问题入账时确认一次｜Vicky2号</div>

  <div class="card">
    <h2>一、本周概览与波动</h2>
    <div class="kpi">
      <div class="item"><div class="num">{m['total']}</div><div class="lbl">本周新增（单）</div></div>
      <div class="item"><div class="num">{m['daily_avg']}</div><div class="lbl">日均（单）</div></div>
      <div class="item">{wow_cell.replace('class="num"', 'class="num"').replace('<div class="num"', '<div class="num"')}<div class="lbl">周环比</div></div>
      <div class="item"><div class="num">{known_rate}%</div><div class="lbl">已知问题率</div></div>
      <div class="item"><div class="num">{rc.get('coverage_pct', 0)}%</div><div class="lbl">根因分析覆盖</div></div>
      <div class="item"><div class="num">{rc.get('cluster_cnt', 0)}</div><div class="lbl">涉及根因簇</div></div>
    </div>
    {wow_note}
    <div id="daily" class="chart" style="height:260px;margin-top:10px"></div>
    <div class="note">波动判断口径：以<b>完整自然周</b>为基期；基期不足 5 天一律标「不可比」，
      不用残缺数据硬算环比（会把周末导入的数据算成暴跌）。</div>
  </div>

  <div class="card">
    <h2>二、已知 vs 新增（核心指标）</h2>
    <div class="heroline">
      <div class="hero">
        <div class="num">{known_rate}%</div>
        <div class="lbl">已知问题率</div>
        <div class="desc">本周工单中能被「在办问题」解释的占比</div>
      </div>
      <div class="mini"><div class="num" style="color:#c0392b">{known_cnt}</div><div class="lbl">已知问题（单）</div></div>
      <div class="mini"><div class="num" style="color:#2f6fed">{new_cnt}</div><div class="lbl">新增问题（单）</div></div>
      <div class="mini"><div class="num">{judged}/{k.get('total', m['total'])}</div><div class="lbl">已判定/总量</div></div>
    </div>
    <div class="note">判定口径：工单 →（根因簇 / 功能模块问题）是否被<b>在办问题（open/resolving）</b>收纳。
      已识别但<b>未确认入账</b>的候选不计为已知——没进台账就等于组织还没认账。
      本周有 <b>{pot_known}</b> 单属于「AI 已识别待入账」，入账后已知率会上升。
      {f'另有 {consult_cnt} 单为使用咨询（非缺陷），不计入已知率分子分母。' if consult_cnt else ''}
      {f'另有 {unknown_cnt} 单无法判定，不计入分母。' if unknown_cnt else ''}</div>
    <div class="sub-h">已知问题（按本周命中单量）</div>
    <table><thead><tr><th>问题编号</th><th>在办问题（根因摘要）</th><th>责任人</th><th>本周命中</th><th>状态</th></tr></thead>
    <tbody>{known_rows}</tbody></table>
    <div class="sub-h">新增问题（本周出现、台账未收纳）</div>
    <table><thead><tr><th>新增问题（根因簇）</th><th>系统</th><th>环节</th><th>单量</th><th>已提候选</th></tr></thead>
    <tbody>{new_cluster_rows}</tbody></table>
  </div>

  <div class="card">
    <h2>三、问题族分析（业务链路）</h2>
    <div class="note">为什么先看族：根因簇是个案粒度（很多簇只有 1 单，标题精确到订单号），
      直接列表会又散又不准。按业务链路归并后才能看出「哪条链路在恶化」。{_wow_basis}</div>
    <table><thead><tr><th>问题族</th><th>本周</th><th>本周日均</th><th>上周日均</th><th>日均环比</th><th>累计</th><th>涉及问题簇</th><th>主要问题</th></tr></thead>
    <tbody>{theme_rows}</tbody></table>
    <div class="note" style="margin-top:8px">环比「—」= 本周该链路无单、或上周无单/数据不足 5 天，不做强行计算（避免把"本周没发生"误读成"已清零"）。</div>
    <div class="note" style="margin-top:10px">{case_note}</div>

    <div class="sub-h">按投诉性质看（五类，分母 = 已根因分析 {rc.get('covered', 0)} 单）</div>
    <table><thead><tr><th>一级性质</th><th>含义</th><th>单量</th><th>占比</th></tr></thead>
    <tbody>{l1_rows}</tbody></table>
    <div id="pie" class="chart" style="height:280px;margin-top:12px"></div>
    <div class="sub-h">重点根因簇（累计 ≥5 单，可直接立项修复）</div>
    <table><thead><tr><th>根因簇</th><th>系统</th><th>环节</th><th>缺陷性质</th><th>责任归属</th><th>单量</th><th>占比</th></tr></thead>
    <tbody>{cluster_rows}</tbody></table>
  </div>

  <div class="card">
    <h2>四、工单压降分析指引</h2>
    <div class="kpi" style="grid-template-columns:repeat(4,1fr)">
      <div class="item"><div class="num" style="color:#c0392b">{win_cnt}</div><div class="lbl">可整批压降单量</div></div>
      <div class="item"><div class="num">{win_pct}%</div><div class="lbl">占已分析单量</div></div>
      <div class="item"><div class="num">{len(batch)}</div><div class="lbl">可修复根因簇</div></div>
      <div class="item"><div class="num">{rc.get('quick_win_cnt', 0)}</div><div class="lbl">可批量修复/改造单量</div></div>
    </div>
    <div class="note">逻辑：同根因簇 ≥{C.RC_BATCH_WEEK_MIN} 单 → 修一处可整批消掉，是压降主战场；
      处置方式为「逐单处理」的簇不产生压降空间，只做兜底。
      按覆盖单量降序排，逐条落成措施即可（措施挂问题、绑簇、自动验证）。</div>
    <table><thead><tr><th>根因（改这里即可整批消掉）</th><th>系统</th><th>责任方</th><th>覆盖单量</th><th>处置方式</th><th>建议动作</th></tr></thead>
    <tbody>{guide_rows}</tbody></table>
  </div>

  <div class="card">
    <h2>五、措施跟踪与自动验证</h2>
    <div class="note">验证口径：措施绑定根因簇 → 按<b>簇单量</b>算降幅（不是按二级场景，否则一桶多缺陷会把降幅稀释）。
      基线只取<b>完整周</b>，基线不可得不给降幅、不流转状态——宁可不结论，也不产出假结论。</div>
    <table><thead><tr><th>措施编号</th><th>所属问题</th><th>责任人</th><th>生效日</th><th>基线/本周</th><th>实际降幅</th><th>状态</th></tr></thead>
    <tbody>{action_rows}</tbody></table>
    <div class="sub-h">在办问题台账（{len(problems or [])} 条）</div>
    <table><thead><tr><th>问题编号</th><th>问题（根因摘要）</th><th>状态</th><th>首见周</th><th>在办周</th><th>当周/累计</th><th>措施(有效/总)</th></tr></thead>
    <tbody>{problem_rows}</tbody></table>
  </div>

  <div class="card">
    <h2>六、趋势（近 8 周）</h2>
    <div id="trend" class="chart"></div>
    <div class="note">实线总量、柱为批量簇工单量。数据缺失周不计入趋势结论。</div>
  </div>

  <div class="card">
    <h2>附：结论与建议动作</h2>
    <ul>{concl}</ul>
    <div class="note">支撑时效（不影响压降结论，仅作运营质量参考）：长链条 <b>{e['long_chain']}</b> 单
      （{e['long_chain_pct']}%）、重复派单 <b>{e['repeat_dispatch']}</b> 单（{e['repeat_dispatch_pct']}%）、
      返工 <b>{e['rework']}</b> 单（{e['rework_pct']}%）、周内未结 <b>{e['unclosed']}</b> 单（{e['unclosed_pct']}%）。</div>
  </div>

  <div class="foot">本报告由客诉流水线自动生成｜指标口径唯一来源 services/complaint/metrics.py｜
    已知判定唯一来源 services/complaint/known.py｜分类口径唯一来源 pmwb_complaint_category 字典表｜{m['week']}</div>
</div>

{echarts_tag}
<script>
echarts.init(document.getElementById('pie')).setOption({{
  tooltip:{{trigger:'item',formatter:'{{b}}：{{c}} 单（{{d}}%）'}},
  legend:{{orient:'vertical',right:16,top:'middle',textStyle:{{fontSize:12}}}},
  series:[{{type:'pie',radius:['38%','64%'],center:['34%','52%'],
    data:{json.dumps(pie_data, ensure_ascii=False)},
    label:{{formatter:'{{b}}\\n{{c}}单 {{d}}%',fontSize:11}}}}]
}});
echarts.init(document.getElementById('daily')).setOption({{
  tooltip:{{trigger:'axis'}},
  grid:{{top:30,bottom:34,left:48,right:24}},
  xAxis:{{type:'category',data:{json.dumps(daily_keys)}}},
  yAxis:{{type:'value',name:'单'}},
  series:[{{name:'当日单量',type:'bar',data:{json.dumps(daily_vals)},barMaxWidth:34,
    itemStyle:{{color:'#2f6fed',borderRadius:[3,3,0,0]}},
    label:{{show:true,position:'top',fontSize:11}}}}]
}});
echarts.init(document.getElementById('trend')).setOption({{
  tooltip:{{trigger:'axis'}},
  legend:{{data:['总量','批量簇工单'],top:0,right:10,textStyle:{{fontSize:12}}}},
  grid:{{top:44,bottom:34,left:48,right:24}},
  xAxis:{{type:'category',data:{json.dumps(trend_weeks)}}},
  yAxis:{{type:'value',name:'单'}},
  series:[
    {{name:'批量簇工单',type:'bar',data:{json.dumps(trend_batch)},barMaxWidth:26,
      itemStyle:{{color:'#e8a33d',borderRadius:[3,3,0,0]}}}},
    {{name:'总量',type:'line',smooth:true,symbolSize:7,data:{json.dumps(trend_total)},
      itemStyle:{{color:'#2f6fed'}},lineStyle:{{width:2.5}}}}
  ]
}});
</script>
</body>
</html>"""


def write_report(m: Dict, out_dir: Optional[Path] = None,
                 problems: Optional[List[Dict]] = None) -> Path:
    """写出 HTML 与图表资源，返回 HTML 路径。"""
    out_dir = Path(out_dir or C.REPORT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    assets = out_dir / "assets"
    assets.mkdir(exist_ok=True)
    target_js = assets / "echarts.min.js"
    if ECHARTS_SRC.exists() and (not target_js.exists() or target_js.stat().st_size != ECHARTS_SRC.stat().st_size):
        shutil.copy2(ECHARTS_SRC, target_js)

    html_path = out_dir / f"客诉周报_{m['week']}.html"
    html_path.write_text(render_html(m, problems), encoding="utf-8")
    return html_path
