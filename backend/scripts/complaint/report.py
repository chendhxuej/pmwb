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

from scripts.complaint import config as C

ECHARTS_SRC = Path(r"D:\项目\个人工作台系统\frontend\node_modules\echarts\dist\echarts.min.js")


def _pct(v: Optional[float], dash: str = "—") -> str:
    return dash if v is None else f"{v}%"


def _wow_text(m: Dict) -> str:
    if m["wow_pct"] is None:
        if m["prev_partial"]:
            return f'<span class="tag t-gray">不可比</span> 上周数据仅覆盖 {m["prev_days"]} 天（{m["prev_total"]} 单），不做环比结论'
        return '<span class="tag t-gray">无基线</span> 上周无数据'
    v = m["wow_pct"]
    cls = "t-red" if v > 0 else ("t-green" if v < 0 else "t-gray")
    arrow = "↑" if v > 0 else ("↓" if v < 0 else "→")
    return f'<span class="tag {cls}">{arrow} {abs(v)}%</span> 上周 {m["prev_total"]} 单'


def _conclusions(m: Dict) -> List[str]:
    """按数据生成结论（不写死话术）。"""
    out: List[str] = []
    tot = m["total"]

    l1 = m["by_l1"]
    if l1:
        top = l1[0]
        out.append(f'<b>结构</b>：{top["name"]} 占 <b>{top["cnt"]} 单（{top["pct"]}%）</b>，为本周第一大类；'
                   f'前两类合计占 {round(sum(x["pct"] for x in l1[:2]), 1)}%。')

    b = m["batch"]
    if b["cluster_count"]:
        if b["fix_rate"] < 50:
            out.append(f'<b>批量异常</b>：{b["cluster_count"]} 个簇、{b["ticket_cnt"]} 单（{b["ticket_pct"]}%），'
                       f'但<b>组织修复率仅 {b["fix_rate"]}%</b>——同源故障仍在逐单兜底，未升级为故障处置。')
        else:
            out.append(f'<b>批量异常</b>：{b["cluster_count"]} 个簇、{b["ticket_cnt"]} 单（{b["ticket_pct"]}%），'
                       f'组织修复率 {b["fix_rate"]}%，已具备批量处置动作。')
    else:
        out.append('<b>批量异常</b>：本周未出现同场景单日 ≥5 单的批量簇。')

    e = m["efficiency"]
    risks = []
    if e["rework_pct"] >= 15:
        risks.append(f'首轮返工 {e["rework_pct"]}%（{e["rework"]} 单）')
    if e["repeat_dispatch_pct"] >= 10:
        risks.append(f'重复派单 {e["repeat_dispatch_pct"]}%（{e["repeat_dispatch"]} 单）')
    if e["unclosed_pct"] >= 50:
        risks.append(f'未结单率 {e["unclosed_pct"]}%（{e["unclosed"]} 单）')
    if e["pushout_pct"] >= 5:
        risks.append(f'互推外部 {e["pushout_pct"]}%（{e["pushout"]} 单）')
    if risks:
        out.append("<b>效率损耗</b>：" + "、".join(risks) + "，属流程与话术可治理范围，不依赖开发。")

    r = m["recur"]
    if r["cnt"]:
        names = "、".join(f'{x["name"]}（{x["cnt"]}）' for x in r["tops"][:3])
        out.append(f'<b>复发预警</b>：{r["cnt"]} 单（{r["pct"]}%）发生在措施生效后，集中在 {names}——'
                   f'说明前期措施未真正见效，需回退核查。')
    else:
        out.append('<b>复发预警</b>：本周无"措施生效后同类再现"工单（当前措施台账为空或未到验证期）。')
    return out


def _rows(items: List[Dict], cols: List[tuple]) -> str:
    if not items:
        return '<tr><td colspan="%d" style="text-align:center;color:#98a6ba">暂无数据</td></tr>' % len(cols)
    out = []
    for it in items:
        tds = "".join(f"<td>{fn(it)}</td>" for _, fn in cols)
        out.append(f"<tr>{tds}</tr>")
    return "".join(out)


def render_html(m: Dict) -> str:
    l1 = m["by_l1"]
    pie_data = [{"value": x["cnt"], "name": x["name"]} for x in l1]
    trend_weeks = [t["week"].split("-")[1] for t in m["trend"]]
    trend_total = [t["total"] for t in m["trend"]]
    trend_batch = [t["batch"] for t in m["trend"]]
    daily_keys = [k[5:] for k in m["daily"].keys()]
    daily_vals = list(m["daily"].values())

    concl = "".join(f"<li>{c}</li>" for c in _conclusions(m))

    action_rows = _rows(m["actions"], [
        ("措施编号", lambda a: f'<b>{a["action_no"]}</b>'),
        ("针对场景", lambda a: a["category_l2"] or "—"),
        ("责任人", lambda a: a["owner"] or "—"),
        ("要求完成", lambda a: str(a["due_date"] or "—")),
        ("生效日", lambda a: str(a["go_live_date"] or "—")),
        ("基线/目标", lambda a: f'{a["baseline_cnt"] or "—"} / 降{a["target_drop_pct"] or 50}%'),
        ("状态", lambda a: a["status"]),
    ]) if m["actions"] else (
        '<tr><td colspan="7" style="color:#98a6ba;text-align:center">'
        '本周尚未登记改进措施——请将结论中的 P0/P1 项落为运营工单并登记到措施台账，'
        '否则下周无法回答"措施做了没有、有没有用"</td></tr>'
    )

    cluster_rows = _rows(m["batch"]["clusters"], [
        ("场景", lambda c: f'<b>{c["l2"]}</b>'),
        ("发现日", lambda c: c["date"]),
        ("单量", lambda c: f'<b style="color:#c0392b">{c["cnt"]}</b>'),
        ("涉及地市", lambda c: c["cities"] or "—"),
        ("组织修复", lambda c: '<span class="tag t-green">已批量处置</span>' if c["fixed"]
            else '<span class="tag t-red">逐单兜底</span>'),
        ("代表单号", lambda c: f'<span style="font-size:11px;color:#5a6b85">{c["tickets"]}</span>'),
    ])

    e = m["efficiency"]
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>客诉工单专题分析 {m['week']}</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:#f5f7fa;color:#1f2d3d;padding:30px 0;line-height:1.7}}
  .wrap{{width:min(1080px,94%);margin:0 auto}}
  h1{{font-size:24px;margin-bottom:4px}}
  .sub{{color:#7a8ba3;font-size:13px;margin-bottom:22px}}
  .card{{background:#fff;border-radius:12px;padding:22px 26px;margin-bottom:18px;box-shadow:0 1px 4px rgba(31,45,61,.08);break-inside:avoid}}
  h2{{font-size:17px;margin-bottom:14px;border-left:4px solid #2f6fed;padding-left:10px}}
  .kpi{{display:grid;grid-template-columns:repeat(6,1fr);gap:11px}}
  .kpi .item{{background:#f0f5ff;border-radius:10px;padding:13px 10px;text-align:center}}
  .kpi .num{{font-size:23px;font-weight:800;color:#2f6fed;font-family:Consolas,monospace}}
  .kpi .lbl{{font-size:11.5px;color:#5a6b85;margin-top:3px}}
  .chart{{width:100%;height:300px}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  th{{background:#f0f4fa;text-align:left;padding:8px 10px;border-bottom:2px solid #dfe7f2}}
  td{{padding:7px 10px;border-bottom:1px solid #eef2f7;vertical-align:top}}
  .tag{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600}}
  .t-red{{background:#fde8e8;color:#c0392b}}.t-orange{{background:#fff2e0;color:#d97706}}
  .t-blue{{background:#e8f1ff;color:#2f6fed}}.t-green{{background:#e5f7ed;color:#1e9e5a}}
  .t-gray{{background:#eef1f5;color:#5a6b85}}
  .note{{background:#f0f7ff;border-left:4px solid #2f6fed;padding:12px 15px;border-radius:6px;margin:10px 0;font-size:13px}}
  ul{{padding-left:20px}}li{{font-size:13.5px;line-height:1.9}}
  .foot{{color:#98a6ba;font-size:12px;text-align:center;margin-top:8px}}
</style>
</head>
<body>
<div class="wrap">
  <h1>商客客诉工单专题分析（{m['week']}）</h1>
  <div class="sub">统计区间 {m['range']}｜数据源：小信工单导出（逐单入库）｜口径：docs/客诉工单分析体系规范.md｜Vicky2号 {m['week']}</div>

  <div class="card">
    <h2>一、核心指标</h2>
    <div class="kpi">
      <div class="item"><div class="num">{m['total']}</div><div class="lbl">本周总量</div></div>
      <div class="item"><div class="num">{m['daily_avg']}</div><div class="lbl">日均单量</div></div>
      <div class="item"><div class="num">{m['batch']['cluster_count']}</div><div class="lbl">批量异常簇</div></div>
      <div class="item"><div class="num">{e['repeat_dispatch_pct']}%</div><div class="lbl">重复派单率</div></div>
      <div class="item"><div class="num">{e['rework_pct']}%</div><div class="lbl">首轮返工率</div></div>
      <div class="item"><div class="num">{e['unclosed_pct']}%</div><div class="lbl">未结单率</div></div>
    </div>
    <div class="note">环比：{_wow_text(m)}</div>
  </div>

  <div class="card">
    <h2>二、本周结论</h2>
    <ul>{concl}</ul>
  </div>

  <div class="card">
    <h2>三、问题性质结构</h2>
    <div id="pie" class="chart"></div>
    <table>
      <thead><tr><th>一级问题性质</th><th>单量</th><th>占比</th></tr></thead>
      <tbody>
      {''.join(f'<tr><td>{x["name"]}</td><td><b>{x["cnt"]}</b></td><td>{x["pct"]}%</td></tr>' for x in l1)
       or '<tr><td colspan="3" style="text-align:center;color:#98a6ba">暂无数据</td></tr>'}
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>四、问题场景 TOP12（改进措施的落点）</h2>
    <table>
      <thead><tr><th>#</th><th>二级问题场景</th><th>所属性质</th><th>单量</th><th>占比</th></tr></thead>
      <tbody>
      {''.join(f'<tr><td>{i+1}</td><td><b>{x["name"]}</b></td><td>{x["l1"]}</td><td>{x["cnt"]}</td><td>{x["pct"]}%</td></tr>'
               for i, x in enumerate(m['by_l2'])) or '<tr><td colspan="5" style="text-align:center;color:#98a6ba">暂无数据</td></tr>'}
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>五、批量数据异常专题（压降主战场）</h2>
    <div class="note">判定口径：同一二级场景 + 同一自然日 ≥ {C.BATCH_DAILY_THRESHOLD} 单 → 批量异常簇。
      本周 <b>{m['batch']['cluster_count']}</b> 个簇、<b>{m['batch']['ticket_cnt']}</b> 单（占 {m['batch']['ticket_pct']}%），
      组织修复率 <b>{m['batch']['fix_rate']}%</b>。
      注意：「批量转派」属逐单流转，不计为组织修复。</div>
    <table>
      <thead><tr><th>场景</th><th>发现日</th><th>单量</th><th>涉及地市</th><th>组织修复</th><th>代表单号</th></tr></thead>
      <tbody>{cluster_rows}</tbody>
    </table>
  </div>

  <div class="card">
    <h2>六、支撑时效与效率</h2>
    <table>
      <thead><tr><th>指标</th><th>本周值</th><th>口径说明</th></tr></thead>
      <tbody>
        <tr><td>平均经手环节</td><td><b>{e['avg_opinions']}</b> 条/单</td><td>处理意见条数，反映流转长度</td></tr>
        <tr><td>长链条工单（≥{C.LONG_CHAIN_OPINIONS}条）</td><td>{e['long_chain']} 单（{e['long_chain_pct']}%）</td><td>单笔走 5 个以上环节</td></tr>
        <tr><td>重复派单</td><td>{e['repeat_dispatch']} 单（{e['repeat_dispatch_pct']}%）</td><td>派单次数 &gt; 1，一次未解决</td></tr>
        <tr><td>首轮返工</td><td>{e['rework']} 单（{e['rework_pct']}%）</td><td>首个回复即索要素材/截图</td></tr>
        <tr><td>互推外部</td><td>{e['pushout']} 单（{e['pushout_pct']}%）</td><td>首轮回复即转网络部/走审批</td></tr>
        <tr><td>挂起待流程</td><td>{e['pending']} 单（{e['pending_pct']}%）</td><td>回复"预计 N 个工作日"</td></tr>
        <tr><td>超期未结单</td><td><b>{e['retention']}</b> 单</td><td>创建 &gt; {C.RETENTION_DAYS} 天且状态非"关闭"</td></tr>
        <tr><td>未结单合计</td><td>{e['unclosed']} 单（{e['unclosed_pct']}%）</td><td>状态非"关闭"（"已回复"不计结单）</td></tr>
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>七、措施跟踪与复发监测</h2>
    <table>
      <thead><tr><th>措施编号</th><th>针对场景</th><th>责任人</th><th>要求完成</th><th>生效日</th><th>基线/目标</th><th>状态</th></tr></thead>
      <tbody>{action_rows}</tbody>
    </table>
    <div class="note">复发判定：措施台账中该场景已过生效日，本周仍出现同类工单 →
      本周复发 <b>{m['recur']['cnt']}</b> 单（{m['recur']['pct']}%）。
      措施完成率 <b>{m['action_stats']['completion_pct']}%</b>（已验证有效 {m['action_stats']['by_status'].get('effective', 0)} / 共 {m['action_stats']['total']} 项）。</div>
  </div>

  <div class="card">
    <h2>八、趋势（近 8 周）</h2>
    <div id="trend" class="chart"></div>
    <div class="note">实线为总量，柱为批量簇工单量。趋势判断以完整周为准，数据缺失周（值为 0）不计入趋势结论。</div>
  </div>

  <div class="foot">本报告由 scripts/complaint 流水线自动生成｜指标口径唯一来源：scripts/complaint/metrics.py｜
   分类口径唯一来源：pmwb_complaint_category 字典表｜{m['week']}</div>
</div>

<script src="assets/echarts.min.js"></script>
<script>
echarts.init(document.getElementById('pie')).setOption({{
  tooltip:{{trigger:'item',formatter:'{{b}}：{{c}} 单（{{d}}%）'}},
  legend:{{orient:'vertical',right:16,top:'middle',textStyle:{{fontSize:12}}}},
  series:[{{type:'pie',radius:['38%','64%'],center:['34%','52%'],
    data:{json.dumps(pie_data, ensure_ascii=False)},
    label:{{formatter:'{{b}}\\n{{c}}单 {{d}}%',fontSize:11}}}}]
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


def write_report(m: Dict, out_dir: Optional[Path] = None) -> Path:
    """写出 HTML 与图表资源，返回 HTML 路径。"""
    out_dir = Path(out_dir or C.REPORT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    assets = out_dir / "assets"
    assets.mkdir(exist_ok=True)
    target_js = assets / "echarts.min.js"
    if ECHARTS_SRC.exists() and (not target_js.exists() or target_js.stat().st_size != ECHARTS_SRC.stat().st_size):
        shutil.copy2(ECHARTS_SRC, target_js)

    html_path = out_dir / f"客诉周报_{m['week']}.html"
    html_path.write_text(render_html(m), encoding="utf-8")
    return html_path
