# -*- coding: utf-8 -*-
"""客诉历史归类核查 + 三层管理使用规范报告生成（纯离线，读 coverage json）。

用法: backend/venv/Scripts/python.exe scripts/complaint_history_management_report.py
输出: data/complaint_history_management.html
"""
import json
import os
from datetime import datetime
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "complaint_history_coverage.json")
OUT = os.path.join(ROOT, "data", "complaint_history_management.html")

d = json.load(open(SRC, encoding="utf-8"))
c = d["coverage"]
T = c["total"]


def pct(n, base=T):
    return "%.1f%%" % (n / base * 100) if base else "—"


def tbl(headers, rows):
    h = "".join("<th>%s</th>" % escape(str(x)) for x in headers)
    b = "".join("<tr>" + "".join("<td>%s</td>" % x for x in r) + "</tr>" for r in rows)
    return "<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (h, b)


def kv(k, v):
    return '<div class="kpi"><div class="kv">%s</div><div class="kl">%s</div></div>' % (v, k)


# ── 四链覆盖表 ──────────────────────────────────────────────
cov_rows = [
    ["主要投诉点（L2 闭集）", "ticket_module", "1639 / 100%",
     "auto 1343 · low 248 · override 1", "<b class='warn'>unclassified 47</b>（其中 43 条带 suggested_id 建议类）",
     "vL2-2", "11-13 13:04~13:38"],
    ["问题点（v4.2 一句话）", "problem_point", "1639 / 100%",
     "ok 1262（%s）" % pct(1262), "<b class='warn'>unclassified 376</b> · pending_auto_rerun 1",
     "v4.2-20261104", "<b class='warn'>11-12 15:51（未动）</b>"],
    ["判定闸门", "problem_gate", "1639 / 100%",
     "matched 1138 + matched_second 14", "<b class='warn'>unclassified 486</b> · pending 1",
     "v4.2-20261104", "—"],
    ["根因归纳（每单）", "ticket.root_cause", "1639 / 100%",
     "ai 1593（%s）" % pct(1593), "insufficient 46", "—", "—"],
    ["根因库簇", "pmwb_complaint_rootcause", "1139 簇", "—", "—", "—", "—"],
    ["已知 / 新增", "ticket.known_flag", "已判定 1091（%s）" % pct(1091),
     "已知 927 · 新增 164", "NULL 548（<b>设计内</b>，无锚单不进分母）", "—", "—"],
    ["问题台账", "pmwb_complaint_problem", "43 行（在册 14）",
     "open 7 · resolving 6 · closed 1", "merged 22 · ignored 7（墓碑留痕）", "—", "—"],
    ["措施", "pmwb_complaint_action", "7 行",
     "in_progress 4 · effective 1", "cancelled 2", "—", "—"],
]
cov_tbl = tbl(["链路", "落库表", "有行 / 主表", "有效归类", "自动隔离 / 未判定", "策略版本", "最后更新"], cov_rows)

# ── 批次交叉 ────────────────────────────────────────────────
batch_rows = [[escape(x["batch"]), x["total"], x["point_ok"], x["point_unclassified"],
               x["module_unclassified"], x["rc_insufficient"], x["known_unevaluated"]]
              for x in d["by_batch_point"]]
batch_tbl = tbl(["导入批次", "工单数", "point ok", "point 未归类",
                 "module 未归类", "rc insufficient", "known NULL"], batch_rows)

# ── 台账旧名对照 ────────────────────────────────────────────
old_rows = []
for x in d["ledger_title_compare"]:
    fuzzy = "/" in (x["title"] or "")
    old_rows.append([
        escape(x["problem_no"]),
        "<span class='%s'>%s</span>" % ("old" if fuzzy else "keep", escape(x["title"] or "")),
        escape(x["std_name"] or "（无模块锚，仅根因簇）"),
        x["status"], x["total_cnt"] or 0,
    ])
old_tbl = tbl(["问题编号", "当前标题（历史快照）", "对应的主要投诉点标准名", "状态", "累计单量"], old_rows)

# ── HTML ────────────────────────────────────────────────────
kpis = "".join([
    kv("历史工单 / 覆盖周", "%d 单 / %s 周" % (T, d["ticket_time"]["weeks"])),
    kv("四链有行率", "100%%（%d/%d）" % (c["has_module"], T)),
    kv("问题点有效归类", "%s（1262）" % pct(1262)),
    kv("自动未归类（point）", "376 单 / %s" % pct(376)),
    kv("在册台账 / 措施", "14 行 / 7 条"),
    kv("台账旧斜杠标题", "<span class='bad'>12 行</span>"),
])

html = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>客诉专题 · 历史归类核查与三层管理使用规范</title>
<style>
:root{--bg:#0f1319;--panel:#171d26;--line:#2a3340;--txt:#e6edf5;--sub:#9aa9bb;--acc:#5eb0ff;--ok:#4ed6a1;--warn:#ffc46b;--bad:#ff7d7d}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);font:14px/1.75 "Segoe UI","Microsoft YaHei",sans-serif;padding:32px 5vw 80px}
h1{font-size:26px;margin:0 0 6px}h2{font-size:19px;margin:38px 0 14px;padding-left:11px;border-left:4px solid var(--acc)}
h3{font-size:15px;margin:24px 0 10px;color:var(--acc)}
.meta{color:var(--sub);font-size:12px;margin-bottom:24px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:22px 0}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.kv{font-size:22px;font-weight:700;color:var(--acc)}.kl{font-size:12px;color:var(--sub);margin-top:3px}
table{width:100%;border-collapse:collapse;margin:12px 0 18px;font-size:13px;background:var(--panel)}
th,td{border:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
th{background:#1d2632;color:var(--sub);font-weight:600;white-space:nowrap}
tbody tr:nth-child(even){background:#141a23}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 20px;margin:14px 0}
.hero{border-left:4px solid var(--warn)}
.hero b{color:var(--warn)}
.bad,.warn,.old{color:var(--bad)}.warn{color:var(--warn)}.ok{color:var(--ok)}
.keep{color:var(--sub)}
code{background:#202a36;color:#a8d5ff;padding:1px 5px;border-radius:4px;font-size:12px}
pre{background:#111721;border:1px solid var(--line);border-radius:8px;padding:13px 16px;overflow:auto;color:#c8d6e5;font-size:12.5px;line-height:1.65}
ul,ol{padding-left:22px}li{margin:5px 0}
.note{color:var(--sub);font-size:12.5px}
.foot{margin-top:44px;border-top:1px solid var(--line);padding-top:16px;color:var(--sub);font-size:12px}
.tag{display:inline-block;background:#233348;color:var(--acc);border-radius:4px;padding:1px 7px;font-size:11px;margin-right:5px}
</style></head><body>
<h1>客诉专题 · 历史归类核查与三层管理使用规范</h1>
<div class="meta">核查时间 __TIME__ ｜ 数据源：本机 MySQL 生产库（<b>只读</b>）｜ 口径：pmwb_complaint_ticket 全表 __TOTAL__ 单，__SPAN__，__WEEKS__ 个自然周，5 个导入批次</div>

<div class="kpis">__KPIS__</div>

<h2>一、正面结论：历史工单<b>没有</b>「全部重新归类」</h2>
<div class="panel hero">
<p><b>① 本轮 v2 改的是「名字」，不是「判定」。</b> 20 条标准类名 + 落库快照已发布，但判定式信号
（<code>objects / natures / exclude / priority</code>）一字未动。今天 13:04~13:38 对
<code>ticket_module</code> 全表 1639 行做过一次重算，dry-run 已证明 <b>20 类单量逐条零漂移</b>——
这是「重算」，不是「重判」。所以不存在「按新标准把历史工单重新归类」这回事。</p>
<p><b>② 四条链只有一条今天动过。</b> <code>module_problem</code> / <code>ticket_module</code> 的
<code>updated_at</code> 是 11-13 13:38；<code>problem_point</code> 全部停在 <b>11-12 15:51</b>，
策略版本仍是 <code>v4.2-20261104</code>；台账、根因、known 均未因 v2 重跑。</p>
<p><b>③ 但现存「未归类」不是漏跑，是设计内的自动隔离。</b> 5 个导入批次、16 个周均匀分布，
不是某一批忘了补链。<code>known.py:17</code> 明确：既无根因簇又无模块归类的单 →
<code>known_flag=NULL</code>、不进已知率分母。按 v4.2 铁律，<b>禁用「其他」兜底压未归类率</b>。</p>
<p><b>④ 真正待补的三件事：</b>1 条 <code>pending_auto_rerun</code> 悬挂；11-12 最后一次
<code>problem_run</code> 被 <code>card_complete</code> 一票否决、<code>publish=0</code> 未发布；
台账 <b>12 行旧斜杠标题</b>快照未同步（上一轮交付的遗漏）。</p>
</div>

<h2>二、四条链路真实覆盖率（分母 = 主表 __TOTAL__ 单）</h2>
__COV__
<p class="note">⚠ 「有行率 100%」只说明每单都生成了占位记录，<b>不等于归类有效</b>。
问题点有效归类 1262/1639（__PCT_OK__），闸门有效匹配 1152/1639（__PCT_GATE__）。
另 <code>problem_no</code>（旧列）仅 150 单有值，<code>rootcause_no</code> 1639 单全有值——
46 条 <code>rc_status=insufficient</code> 的单也被赋了簇号，属需关注的强制归类痕迹。</p>

<h3>2.1 按导入批次交叉：确认不是「某一批漏跑」</h3>
__BATCH__
<p class="note">未归类在 5 个批次中按单量成比例分布（约 17%~30%），周维度同样分散在 W31~W46，
因此结论是「口径自动隔离」，不是「某次导入后补链漏了」。这与项目里
「每次导入后必补三条独立落库链」的要求是两回事——后者是为了让新单进得了闭集和已知判定，
不是为了让未归类率归零。</p>

<h2>三、问题台账与措施（建工单）现状</h2>
__LEDGER_TBL__
<p class="note">在册 14 行（已排除 merged 22 / ignored 7 墓碑行）。其中 <b>12 行标题仍是旧斜杠堆叠名</b>，
<b>4 行 total_cnt=0</b> 为零单量空壳；上一轮虽已在「归因锚点」列展示 <code>module_problem_name</code> 标准名，
但第 71 行「问题（根因摘要）」列读的是 <code>title</code> 历史快照，旧名仍会出现在页面、周报与导出里。</p>

<h3>3.1 关联键与断链实测</h3>
__CHAIN_TBL__
<div class="panel">
<p><b>「建工单」建的是运营问题工单，不是开发工单</b>：<code>pmwb_dev_ticket</code> 当前 <b>0 行</b>；
7 条措施的 <code>issue_no</code> 有 6 条能在 <code>pmwb_operation_issue</code>（153 行）找到，
1 条（<code>CACT-2026W45-01 → COMP-20261104-332</code>）失配，该措施已是 cancelled，只标不改。</p>
<p><b>⚠ 措施主表没有 <code>problem_no</code> 外键</b>，台账↔措施必须走第三张关联表
<code>pmwb_complaint_problem_action(problem_no, action_no, is_primary)</code>。
现网 5 条链接覆盖 4 个台账 / 5 条措施，仅 1 条 primary；
<b>在册 14 行里只有 4 行挂了措施</b>，另 10 行无任何措施；7 条措施中 2 条未关联台账。</p>
<p><b>效果可验证性严重不足</b>：7 条措施只有 1 条有 <code>baseline_cnt</code> / <code>go_live_date</code> /
<code>actual_drop_pct</code>（effective，降幅 100%），其余 6 条无基线、无生效日，
因此「措施有没有打中投诉」目前只有 1 条算得出来。</p>
</div>

<h2>四、日后怎么管理使用</h2>

<h3>4.1 三层职责边界（谁产生、谁能改、禁止什么）</h3>
__ROLE_TBL__
<p class="note">一句话记法：<b>L1 是系统判的「是什么问题」，L2 是组织认的「要不要管」，L3 是人做的「怎么改、改没改」</b>。
三层不要互相倒推——不能用簇名反推单条工单，也不能用措施结果去改历史归类。</p>

<h3>4.2 关联键（唯一，禁第二份实现）</h3>
<pre>工单 → 主要投诉点   ticket_module.module_problem_id          （一单一类，1639/1639）
主要投诉点 → 台账     problem.module_problem_id                （另有 rootcause_nos 簇锚，簇优先）
台账 → 措施           problem_action(problem_no, action_no, is_primary)
措施 → 运营工单       action.issue_no → operation_issue.issue_no
措施 → 关联投诉明细   operation_issue.context_tickets (JSON)</pre>
<p class="note">台账锚点目前仍是<b>双轨</b>：<code>module_problem_id</code> 19/43、
<code>rootcause_no</code> 24/43、<code>rootcause_nos</code> 32/43；在册 14 行里
<code>CPB-2026W42-01</code>、<code>CPB-2026W45-09</code> 只有根因簇锚。
按 <code>known.py</code> 口径「两锚任一命中在办即已知，簇锚优先」，这是设计内，但
<b>措施必须挂台账 problem_no，不要直接挂簇号</b>——簇会合并、会迁移锚点，挂簇必断链。</p>

<h3>4.3 每次导入后必跑的 5 步（顺序不可换）</h3>
<pre>1) run_weekly &lt;file&gt; --no-pdf                # CLI 同步跑主链；禁走页面 API（异步 daemon 会被 CLI 退出杀掉）
2) problem_pipeline.run_full(force=False)      # 增量生成 v4.2 问题点（pipeline.run 不覆盖）
3) module_aggregate.run_aggregate(dry_run=False)  # 全量重建 L2 闭集（不补则新单进不了闭集）
4) known.mark(db)                              # 全量重判已知/新增
5) 用当前代码重生成 W45/W46 周报快照            # 模板/数据变更后必须重生成，否则下载到旧快照</pre>
<p class="note">原因：<code>pipeline.run</code> 与 <code>ingest._post_import_async</code> 只覆盖
LLM 分类 → 派生指标 → 根因归纳/簇归并 → 台账 <code>after_import</code> → <b>按周</b> <code>known.mark</code>；
<b>不覆盖第 2、3、4 步</b>。跳过任一步，下游看板数字必漏。本轮 11-13 只执行了第 3 步的等价重算。</p>

<h3>4.4 日常使用 SOP（按频率）</h3>
<ol>
<li><b>每次导入后</b>：按 4.3 跑完 5 步；再看 <code>GET /problem-v42/status</code> 的最近验收结论与待自动补跑规模，
有 pending 走 <code>POST /problem-v42/rerun-pending</code>（默认 dry_run，显式关才落库）。</li>
<li><b>每周一看板</b>：<code>GET /problems/candidates</code> 逐条确认
<code>open</code>（入账）/ <code>merge</code>（合并，归因改写+计数吸收）/ <code>ignore</code>（忽略）。
<b>人工闸门只存在于「组织是否认账」这一层</b>，不参与工单归类。</li>
<li><b>需要整改时</b>：台账行点「建工单」或详情页「建立运营工单」，
后端 <code>POST /actions</code> 带 <code>create_issue=true + problem_nos</code>，
自动完成三表联动：建 <code>operation_issue</code>（自动代入 issue-context 的 summary + 关联投诉工单明细进
<code>context_tickets</code>）→ 建 <code>action</code> → 写 <code>problem_action</code> 关联。
<span class="warn">务必带上 problem_nos</span>，否则又是断链措施（现网已有 2 条）。</li>
<li><b>措施生命周期</b>：<code>planned</code> → 上线后 <code>POST /actions/{no}/go-live</code> 绑基线
（生效日前 N 周该场景周均单量）→ 观察期 <code>verify_weeks</code> →
<code>POST /actions/verify</code> 自动定论 <code>effective / ineffective</code> →
<code>GET /problems/closure-suggestions</code> → <b>人工确认</b>后 <code>closed</code>。
<span class="warn">不走 go-live 就没有基线，效果永远算不出来</span>（现网 6/7 条卡在这里）。</li>
<li><b>闭环回收</b>：merged / ignored 留行追溯但列表默认排除；簇数由后端一次返 live/merged，
前端只显示不推导；展示字段 = 排序字段 = 下钻字段 = 同一周。</li>
</ol>

<h3>4.5 四条禁止（v4.2 最高约束，不可绕过）</h3>
<ul>
<li><b>数据分析不得依赖人</b>：禁人工确认 / 复核 / 判定卡 / 盲评进生产链路；
人只在过程外定口径、事后调口径。人工动作只允许出现在「台账认账」「措施闭环」两处业务决策。</li>
<li><b>通道不可用 → 自动进未归类并标「待自动补跑」</b>：禁转人工、禁降级关键词、
禁用「其他 / 兜底类」压未归类率。376 条 point 未归类、47 条 module 未归类应如实单列。</li>
<li><b>单一真相源</b>：口径 / 枚举 / 映射只留一处，禁另造排除清单、禁在前端二次推导簇数或口径。</li>
<li><b>归类 ≠ 定责</b>：词库只描述「哪类失效」，不判定投诉是否成立、不做责任归属、不评价客服个人；
涉赔涉诉涉舆情升级必须人工核实介入。</li>
</ul>

<h3>4.6 质量门禁的价值边界（必须对内说清）</h3>
<div class="panel">
<p>现有回归（字典 12 条 / DOM 24+26 条 / 看板一致性 130 条）验的是<b>数字一致性与展示结构</b>，
<b>不是归类正确性</b>。43 单分层抽样实测：旧体系严格准确率 44.2%、失真 55.8%——
这个数在 v2 改名后<b>没有变化</b>，因为判定式没动。</p>
<p>库里 <code>pmwb_complaint_problem_goldset</code> 66 行只有
<code>ticket_no / source=auto / policy_version / added_at</code>，是<b>自动抽样的代表性工单集</b>，
没有人工标签，<b>不能当独立金标、不能算准确率真值</b>。要接真 LLM 语义通道，仍缺三项外部输入：
① 授权外部 LLM 调用；② 业务侧标注 ≥100 单独立金标（标注者与规则设计隔离）；
③ 裁定 3 条口径边界争议。在此之前不对外承诺任何准确率。</p>
</div>

<h2>五、待办清单（按优先级，均<b>未执行</b>）</h2>
__TODO__
<p class="note">本轮为<b>只读核查 + 规范输出</b>，未写任何生产表、未改运行态代码、未联网、未重启服务。
上表第 1、2 项可直接执行（其中第 1 项需你先拍板 A/B 方案），其余按依赖顺序推进。</p>

<div class="foot">
生成：__GEN__ ｜ 脚本：<code>scripts/complaint_history_coverage_audit.py</code>（只读核查）、
<code>scripts/complaint_history_management_report.py</code>（本报告）｜
数据：<code>data/complaint_history_coverage.json</code><br>
边界：归类不等于定责；投诉是否成立、责任归属、涉赔涉诉涉舆情升级须人工核实介入；
不评价客服个人、不做个人排名。本报告所有数字均来自本机生产库实时只读查询，未使用估算行数。
</div>
</body></html>"""

role_rows = [
    ["<b>L1 主要投诉点</b>", "哪个环节 · 什么对象 · 怎么失效",
     "<code>module_problem</code>(20) + <code>ticket_module</code>(1639)",
     "<code>module_problem_id</code>", "系统自动（module_aggregate 全量重建）",
     "只改闭集字典并发版发布", "禁自由文本、禁业务侧改名、禁把在途/已结单写进名称"],
    ["<b>L2 问题台账</b>", "组织认不认账、谁负责、在不在办",
     "<code>pmwb_complaint_problem</code>(43 / 在册 14)",
     "<code>problem_no</code>", "候选自动扫描（R1-R4 / 模块种子），<b>人工确认入账</b>",
     "状态 / 责任人 / 标题 / 结论", "禁自动入账、禁物理删除（留 merged/ignored 墓碑）、禁一场景多开"],
    ["<b>L3 措施 + 建工单</b>", "怎么改、改没改、有没有效",
     "<code>action</code>(7) + <code>problem_action</code>(5) + <code>operation_issue</code>(153)",
     "<code>action_no</code> / <code>issue_no</code>", "人在台账页点「建工单」，系统三表联动",
     "措施字段与状态流转", "禁无 problem_no 单独建措施、禁无基线直接判有效、禁事后编基线"],
]
role_tbl = tbl(["层", "回答什么", "实体 / 表", "唯一键", "产生方式", "谁能改", "禁止"], role_rows)

chain_rows = [
    ["在册台账", "14 行", "open 7 · resolving 6 · closed 1", "merged 22 / ignored 7 已排除"],
    ["台账旧斜杠标题", "<b class='bad'>12 / 14 行</b>", "title 为历史快照", "上轮只改字典与锚点列"],
    ["零单量空壳台账", "<b class='warn'>4 行</b>", "CPB-2026W32-03 / -06 / -11、CPB-2026W39-01", "total_cnt=0，需核查是否该 ignore"],
    ["台账挂措施", "<b class='warn'>4 / 14 行</b>", "problem_action 5 链接 / 4 台账 / 5 措施 / 1 primary", "10 行在办问题无任何措施"],
    ["措施关联台账", "5 / 7 条", "2 条未关联（均 cancelled）", "措施表本身无 problem_no 外键"],
    ["措施 → 运营工单", "6 / 7 条", "operation_issue 153 行", "1 条 issue_no 失配（已 cancelled）"],
    ["措施基线 / 生效 / 效果", "<b class='bad'>1 / 7 条</b>", "仅 CACT-2026W43-01 effective（降幅 100%）", "其余 6 条无 baseline_cnt / go_live_date"],
    ["开发工单", "0 行", "pmwb_dev_ticket 为空", "「建工单」= 建运营问题工单"],
]
chain_tbl = tbl(["核查项", "实测", "明细", "说明"], chain_rows)

todo_rows = [
    ["1", "<b>台账 12 行旧斜杠标题</b>",
     "页面/周报/导出仍会出现「订单结单/回单卡单/在途」",
     "二选一：<b>A（建议）留痕迁移</b>——原标题写入 note，title 取 <code>std_name</code>；<b>B</b> 前端标题列优先显示 <code>module_problem_name</code>。A 更彻底，B 不动数据但周报/导出仍可能带旧名",
     "改库需 dry-run + 备份；需你先拍板"],
    ["2", "1 条 pending_auto_rerun",
     "problem_point / problem_gate 各 1 条",
     "<code>POST /problem-v42/rerun-pending</code>（默认 dry_run）",
     "通道可用即自动补，不可用原样保留，不排队等人"],
    ["3", "11-12 problem_run 被否决",
     "<code>publish=0</code>；card_complete=98.15、desc_concrete=98.15、head_rerun=0、drift_rerun=0",
     "修 4 项门禁后重跑 <code>problem_pipeline.run_full</code>",
     "<b>禁放宽门禁阈值</b>；需 LLM 通道"],
    ["4", "措施锚与基线缺口",
     "2 条措施无台账关联、6 条无基线/生效日",
     "补 <code>problem_nos</code>；已上线的走 <code>go-live</code> 绑基线",
     "禁事后编基线"],
    ["5", "4 行零单量空壳台账",
     "total_cnt=0，仍在在册列表",
     "核查后走 <code>ignore</code>（留墓碑）",
     "禁物理删除"],
    ["6", "措施 issue_no 1 条失配",
     "<code>CACT-2026W45-01 → COMP-20261104-332</code>",
     "核对运营工单是否被删，只标注不回填",
     "该措施已 cancelled"],
    ["7", "W45/W46 周报静态快照旧类名",
     "上轮遗留；<code>report.py:264</code> 表头也未同步",
     "按当前代码重生成两份周报（需 <code>REPORT_VERSION+1</code>）",
     "需后端加载新模板后执行"],
]
todo_tbl = tbl(["#", "事项", "现状", "动作", "风险 / 前置"], todo_rows)

html = (html
        .replace("__TIME__", d["checked_at"])
        .replace("__TOTAL__", str(T))
        .replace("__SPAN__", "%s ~ %s" % (d["ticket_time"]["first_t"][:10], d["ticket_time"]["last_t"][:10]))
        .replace("__WEEKS__", str(d["ticket_time"]["weeks"]))
        .replace("__GEN__", datetime.now().strftime("%Y-%m-%d %H:%M"))
        .replace("__KPIS__", kpis)
        .replace("__COV__", cov_tbl)
        .replace("__BATCH__", batch_tbl)
        .replace("__LEDGER_TBL__", old_tbl)
        .replace("__CHAIN_TBL__", chain_tbl)
        .replace("__ROLE_TBL__", role_tbl)
        .replace("__TODO__", todo_tbl)
        .replace("__PCT_OK__", pct(1262))
        .replace("__PCT_GATE__", pct(1152)))

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print("OUT", OUT)
print("size", os.path.getsize(OUT), "bytes")
print("ledger_fuzzy", d["ledger_fuzzy_cnt"], "ledger_empty", d["ledger_empty_cnt"],
      "live_with_action", d["live_with_action"])
