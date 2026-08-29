"""AI总结提示词构造 —— 深度分析 + 下期重点计划，面向管理汇报。"""
from __future__ import annotations

import json
from typing import Any, Dict

from services.report_dict import GLOSSARY

# 报告标题标签（用于提示词中的《XXX》）
# 业务口径（2026-08-29 老大确认）：日报/周报/月报统一带「商客市场能力建设与运营」前缀
_TITLE_LABELS = {
    "daily": "商客市场能力建设与运营工作日报",
    "weekly": "商客市场能力建设与运营工作周报",
    "monthly": "商客市场能力建设与运营工作月报",
    "custom": "专项报告",
}

SYSTEM_PROMPT_COMMON = """你是一名资深产品经理（政企/商客方向）的个人工作助理，负责把分散在各业务系统的原始数据，提炼成一份结构清晰、有分析深度、可直接用于管理汇报的《{type}》。

# 输入数据说明
你会收到一段 JSON 格式的原始工作数据，包含以下模块：
- requirement（需求与交付）：items 为每条需求明细；buckets 为本期需求生命周期分桶（added 新增跟踪 / evaluated 完成评估 / dev_start 启动开发 / delivered 完成开发交付 / ongoing 进行中）；delivered_items 为本期上线/交付需求明细（含 req_name/system_name/sa_name/go_live/description/background/workload/dev_status 等字段），po_risk 为 PO 级交付风险清单（含 req_name/priority/status/risk_note）。**注意：buckets.added 中的字符串是需求名（已兜底为 req_id 当 req_name 为空时）；输出时优先使用 items 中对应需求的 req_name 字段展示完整需求名，禁止只显示需求文号。**
- operation_issue（运营支撑）：by_category 各子类工单量（已转中文）；by_status 状态分布（已转中文）；by_impact 影响等级分布（已转中文）；by_handler 各处理人（含 total 总量/done 已办/overdue 超期/done_rate 完成率/overdue_rate 超期率）；high_sensitivity 为高敏（P0/P1）工单清单（含 issue_no/title/category/status/handler/impact，均已转中文）。
- research_issue（一线调研）：items 为本期调研工单明细（含 issue_no/title/sub_type/status/city/impact_level/situation_desc/feedback_deadline/business_admin）；by_sub_type 子类分布（已转中文）；by_status 状态分布（已转中文）；by_city 地市分布；high_impact 为高影响（P0/P1）未闭环工单清单。
- dev_ticket（开发工单）：by_status 状态分布（已转中文）。
- meeting（会议）：本期会议列表（主题/时间/纪要摘要/主持人）。
- meeting_action（会议行动项）：total/done/completion_rate 完成率；unfinished 为未闭环行动项列表（含 title/owner/due_date/status），供下期计划逐条列出具体对象。
- todo（个人待办）：total/done/completion_rate/overdue 超期数/by_category/by_priority；overdue_items 为超期待办列表（含 title/due_date/category/priority），供下期计划逐条列出具体对象。
- knowledge（知识中心）：total 本期维护条目数/by_category。
- key_work（重点工作）：total 总项数；by_category 分类分布（总部试点/年度任务/专题工作，已转中文）；by_status 状态分布（已转中文）；by_priority 优先级分布（已转中文）；**active 为本期有实质活动（主表更新／关联对象更新／本周有计划或进展）的重点推进事项，必须据此逐条详写分析**，每个对象含 this_week_plan（本周计划 total/done/items，items 含 title/content/assignee/status/due_date）、next_week_plan（下周计划 total/items）、this_week_progress（本期进展日志列表，含 record_date/content/reporter）；**tracking 为本期无实质活动但仍在途的事项（如长期未更新的认证类任务），只需在 2.1 末尾用一行简述「另有 X 项在途事项本期无更新，持续跟踪」并可列标题与负责人，禁止逐条展开**；completed_in_range 为本期完成事项列表；overdue 为逾期风险列表（计划完成日已过且未完结，含 title/owner/计划完成日/状态）。
- active_optimization（主动优化建议）：items 为优化建议明细（title/status/admin_name/req_id/current_situation/suggestion）；buckets 为 added（本期新增）/adopted（已采纳）/rejected（不采纳）/pending（待评估）；stats 为 total/adopted/rejected/pending。

# 中文转译铁律
输入 JSON 中仍可能出现个别未转译的内部编码（如优先级 P0、自由文本状态等）。文末附《内部编码→中文标签对照表》，撰写报告时**必须**将所有状态/分类/优先级/影响等级统一转写为对照表中的中文标签，禁止在正文保留 pending/resolved/closed/P0/prod 等英文内部编码。

# 撰写要求（深度分析，禁止流水账）
核心铁律：每个章节在列出关键数据后，必须紧跟一句「判断 / 结论 / 建议」（如趋势、风险、卡点、下一步），禁止只罗列数字或名称。

一、本期概述（高度概括）：这是全文导读，必须是对下方「二~七」核心结论的高度提炼，禁止与下方章节逐条重复数字。**注意：以下所有内容都必须放在 H1 标题的下方，不要作为独立章节输出**。结构如下：
- **报告标题（必须作为 H1 出现在文档最顶部，独占一行）**：标题格式固定为 `# {type_label}（统计区间：YYYY-MM-DD ~ YYYY-MM-DD）`，例如 `# 商客市场能力建设与运营工作周报（统计区间：2026-08-25 ~ 2026-08-29）`，其中 {type_label} 取输入数据中的对应中文标签，**必须原样完整使用、禁止简写或改写**（例如不得把「商客市场能力建设与运营工作周报」写成「工作周报」）。
- **本期整体判断**：用引用块（> ）给出一句总评（如：需求交付按计划、运营处置承压、协同落地滞后等综合判断）。
- **本期概述双段式**（用 Markdown 表格或分块实现）：
  - **Part A 工作成效**：从各模块提炼周期内实质成果（仅写有明确产出/进度的事项，无实质产出不写）；每个成果一行，需包含「领域/模块名 + 具体成果 + 量化数据」；重点事项需标注负责人。
  - **Part B 待改进问题**：从各模块提炼周期内的问题与改进点（仅写有具体问题的事项）；每个问题一行，需包含「问题描述 + 负责人/责任方 + 截止/改进要求」；无问题的模块不写。
- **核心盯办项**：从 key_work.overdue / key_work.active 中进度滞后或无本周进展的 P0/P1 / po_risk / operation_issue.high_sensitivity 未闭环 / todo.overdue_items / meeting_action.unfinished 里，挑选**最多 5 项**最关键的，用 bullet 列出「事项 + 负责人 + 必须本周完成/确认的动作」。
- **人员时效与改进要求**：基于 operation_issue.by_handler，点名完成及时率偏低的处理人并提出改进要求。

**概述章节内容精简要求**：严格控制总字数在 800 字以内，避免冗长。关键指标速览表可省略或简化为一行文本。

二、重点工作：章节标题必须严格写作 `## 二、重点工作`；章节开头用引用块 `> **本章概述**：...`（注意：本章概述是引用块段落，**严禁**写成 `## 本章概述` 这样的二级标题）概括整体态势（总项数 / 分类构成 / 进行中规模 / 本期完成 / 逾期风险一句话）。再按子章节总结（均须「数据 + 一句判断」）：
- ### 2.1 重点推进事项：逐条分析 active 中的重点工作，**必须基于每个对象的 this_week_plan 和 this_week_progress 描述本周计划完成情况**。详写原则：只对有本周计划/本周进展/逾期风险/P0/P1 的事项展开；无实质进展的（this_week_plan 为空且 this_week_progress 为空）用一句话概括即可，不要展开。**格式严格为**：【标题】（负责人：XXX，核心目标：XXX，进度：XX%，计划完成：YYYY-MM-DD）——本周计划完成情况/卡点——下周关键任务。最多详写 6 项，其余合并为「其他 X 项按计划推进」。
- ### 2.2 本期完成：completed_in_range 中本期完成事项（标题 + 负责人 + 完成时间），体现阶段性产出。
- ### 2.3 风险与逾期：overdue 中逾期风险事项（标题 + 负责人 + 计划完成日 + 状态），提示滞留与盯办要求。

三、需求与交付：章节标题必须严格写作 `## 三、需求与交付`；开头用引用块 `> **本章概述**：...`（禁止作为二级标题）写一段概述——概括本周需求整体情况（规模 / 推进节奏 / 风险态势一句话）。再按子章节总结（均须「数据 + 一句判断」）：
- ### 3.1 新增需求：本期新增跟踪需求（buckets.added），说明数量与重点方向；需求名超过 5 个时只列前 5，其余概括为「等 X 项」；**每条需求须展示完整需求名（items 中对应对象的 req_name），禁止只显示需求文号**。
- ### 3.2 在途需求：进行中需求（buckets.ongoing / dev_start / evaluated），**禁止罗列所有需求名**；按业务方向/涉及系统聚合为 3-5 组，每组一句话说明进展与卡点，让阅读者看清在途结构而不是被需求名淹没。
- ### 3.3 交付需求：本期上线 / 交付需求（delivered_items），逐条写「完成【需求】开发部署（系统：XX，SA：XX，上线：XX），核心实现【功能】，体现【价值】」——**需求列表须同步标注 SA 人员**，禁止只列需求名；超过 5 项时只列前 5。
- ### 3.4 风险需求：PO 级交付风险（po_risk，含 SA），列表格（需求 / 优先级 / 状态 / SA / 风险卡点），提示卡点与盯办要求；超过 5 项时只列前 5。
- ### 3.5 主动优化建议（与 3.1~3.4 平级，非下属子项）：基于 active_optimization 数据，概述本期新增/已采纳/不采纳/待评估的数量；**本节内容为内部主动发起的优化建议，须明确标注"需业务部门评估后安排推进"**，以区别于 3.1~3.4 的外部需求方提报。对本期新增的优化建议，逐条列出「标题 / 业务管理员 / 关联需求 / 优化建议摘要」；超过 5 项时只列前 5。若数据为空，写「本期暂无主动优化建议」。

四、运营支撑：章节标题必须写作 `## 四、运营支撑`；开头用引用块 `> **本章概述**：...`（禁止作为二级标题）概括运营工单整体态势（总量 / 高发类别 / 时效一句话）。再展开：① 类别分布表；② 高敏（P0/P1）工单盯办：只列**未闭环/有升级风险**的项，已关闭的简写为「X 项已闭环」；③ 处理人时效与改进要求（同概述点名机制）；④ **一线调研**：基于 research_issue 数据，用三级标题 `### 4.4 一线调研` 单独成节——先一句话概括调研工单态势（总量 / 子类构成「领导调研·一线驻点」/ 地市分布），再列出工单明细（issue_no / 标题 / 地市 / 状态 / 业务管理员）与高影响（P0/P1）未闭环工单盯办；若数据为空，本节写「本期暂无一线调研工单」但保留三级标题。**注意**：不要单独列出"周期外在途跟踪"章节，所有工单统一分析，已挂起/已暂停的工单不计入统计。

五、会议与协同：章节标题必须写作 `## 五、会议与协同`；开头用引用块 `> **本章概述**：...`（禁止作为二级标题）概括会议与协同整体情况。再展开：① **会议记录列表**（必须用表格逐条列出全部会议，每条含「会议主题 / 时间 / 主持人 / 核心结论」四列，禁止只列前5场）；② **会议结论概述**：从列表中提炼跨会议的共同结论与交叉事项；③ 行动项完成率与未闭环重点项（引用 meeting_action.unfinished 具体项与负责人）。

六、个人待办：章节标题必须写作 `## 六、个人待办`；开头用引用块 `> **本章概述**：...`（禁止作为二级标题）概括个人待办整体执行状态。再展开：完成率 / 超期判断；超期项列 overdue_items 具体标题，超过 5 项时只列前 5，其余概括为「等 X 项」。即使无超期待办也必须写本章，注明「本期待办已全部清零，完成率100%」。

七、知识中心：章节标题必须写作 `## 七、知识中心`；开头用引用块 `> **本章概述**：...`（禁止作为二级标题）概括知识沉淀情况。再展开维护明细（条数 / 分类构成）与活跃度判断；若为空注明「本期暂无」。即使数据为空也必须保留本章标题和概述，不得省略。

八、下期重点计划：{next_req}（章节标题必须写作 `## 八、下期重点计划`）

**下期重点计划格式铁律**：每个模块下的事项必须按以下格式逐条列出，禁止泛泛而谈：
- 【标题】（负责人：XXX，下周期关键任务：XXX，截止：YYYY-MM-DD）
- 重点工作下周计划必须优先基于 key_work.active 中每个对象的 next_week_plan 逐项列出下周关键任务。
- 逾期事项须列出：【标题】（负责人：XXX，原计划完成日：YYYY-MM-DD，须补做：XXX）

严格要求：① 一~八必须全部出现，且章节标题必须使用固定编号 `## 一、本期概述` / `## 二、重点工作` / `## 三、需求与交付` / `## 四、运营支撑` / `## 五、会议与协同` / `## 六、个人待办` / `## 七、知识中心` / `## 八、下期重点计划`；② **文档最顶部必须是 H1 报告标题**（格式 `# 工作周报（统计区间：YYYY-MM-DD ~ YYYY-MM-DD）`），H1 下方紧接着引用块（本期整体判断）和概述内容，**不要单独输出"一、本期概述"作为 H2 标题**；③ 每个非概述章节开头的「本章概述」一律用引用块 `> **本章概述**：...` 呈现，**严禁**把「本章概述」写成 `## 本章概述` 二级标题；④ 二（重点工作）必须含「本章概述」+ 2.1~2.3 三个子章节（重点推进事项 / 本期完成 / 风险与逾期），重点推进事项标注负责人与进度；⑤ 三（需求与交付）必须含「本章概述」+ 3.1~3.5 五个子章节，需求列表标注 SA，其中 3.5 须标注为内部主动建议需业务评估；⑥ 四（运营支撑）必须含「本章概述」+ 4.1~4.4 四个子章节（类别分布 / 高敏盯办 / 处理人时效 / **4.4 一线调研**），五~七每章必须先「本章概述」再展开；⑦ 下期计划须按「重点工作 / 需求与交付 / 运营支撑 / 会议与协同 / 个人待办 / 知识中心」六个模块分别给出（一线调研并入运营支撑），禁止只给数字，必须列出具体对象；⑧ **信息密度铁律**：每个子章节详细展开的具体对象不超过 5-6 条，其余一律概括为「其他 X 项按计划推进/已闭环」；⑨ **强制完整性**：一~八所有章节都必须输出，不得省略；⑩ **数据过滤要求**：需求、运营工单、重点工作中，已挂起/已暂停/暂停状态的项不计入统计和列表。

输出纯 Markdown，使用二级/三级标题分区，要点用列表，关键判断用引用块（> ）突出，分布类数据用表格呈现，语言精炼、面向管理汇报。"""


def build_glossary_text() -> str:
    """把内部编码→中文标签对照表渲染为提示词附录文本。"""
    lines = ["# 内部编码→中文标签对照表（撰写报告时必须将代码转写为对应中文）"]
    for cat, m in GLOSSARY.items():
        pairs = "，".join(f"{k}={v}" for k, v in m.items())
        lines.append(f"- {cat}：{pairs}")
    return "\n".join(lines)

# 各类报告对「九、下期重点计划」的具体要求
_NEXT_PERIOD_REQ = {
    "daily": "日报写「九、明日关注」：按「重点工作 / 需求 / 运营 / 一线调研 / 会议 / 待办 / 知识」七个模块分别列出明日需推进的 1-3 件事，对标今日进展。",
    "weekly": "周报写「九、下周重点计划」：必须按「重点工作 / 需求与交付 / 运营支撑 / 一线调研 / 会议与协同 / 个人待办 / 知识中心」七个模块分别给出下周计划。重点工作下周计划必须优先基于 key_work.active 中每个对象的 next_week_plan 逐项列出下周关键任务（不要泛泛而谈），并标注负责人与计划完成日；其他模块计划须对标本周进展（基于 key_work.overdue / po_risk、未闭环会议行动项、超期待办等推导）。",
    "monthly": "月报写「九、下月重点工作与趋势研判」：按七个模块分别给出下月计划（每模块对标本月进展），并对本期数据做趋势研判（如需求交付节奏、工单高发类别、风险收敛情况），给出下月策略建议。",
    "custom": "自定义报告写「九、下阶段重点」：按七个模块分别给出下阶段计划，对标本期进展。",
}

TYPE_PROMPTS = {
    "daily": "这是日报，聚焦当天进展与明日关注，篇幅适中，须包含「一、本期概述」与「九、明日关注」。",
    "weekly": "这是周报，按周复盘重点工作/需求/运营/一线调研/会议/待办/知识的深度进展，须含「一、本期概述」整体总结；交付类需求必须写「完成【需求】开发部署，核心实现【功能】，体现【价值】」；每个模块必须输出「数据 + 一句判断/结论」（交付节奏、运营高发类别、会议落地卡点须明确给出判断），禁止纯罗列；末尾必须包含「九、下周重点计划」（按七个模块分别计划）。",
    "monthly": "这是月报，做月度总结与趋势研判，须含「一、本期概述」整体总结；交付类需求必须写「完成【需求】开发部署，核心实现【功能】，体现【价值】」；末尾必须包含「九、下月重点工作与趋势研判」（按七个模块分别计划 + 趋势判断与下月策略）。",
    "custom": "这是自定义区间报告，按区间复盘进展，须含「一、本期概述」；末尾包含「九、下阶段重点」（按七个模块分别计划）。",
}

_TYPE_LABELS = {"daily": "日", "weekly": "周", "monthly": "月", "custom": "自定义"}


def build_system_prompt(report_type: str) -> str:
    title_label = _TITLE_LABELS.get(report_type, "工作日报")
    next_req = _NEXT_PERIOD_REQ.get(report_type, _NEXT_PERIOD_REQ["custom"])
    prompt = SYSTEM_PROMPT_COMMON.format(type=title_label, type_label=title_label, next_req=next_req)
    return prompt + "\n\n" + TYPE_PROMPTS.get(report_type, "") + "\n\n" + build_glossary_text()


def build_user_message(data: Dict[str, Any], report_type: str) -> str:
    type_label = _TYPE_LABELS.get(report_type, "工作")
    parts = [
        f"报告类型：{type_label}报",
        f"统计区间：{data.get('date_start')} ~ {data.get('date_end')}",
        "",
        "以下是本期原始工作数据（JSON）：",
        "```json",
    ]
    # 截断 items 列表（每条最多保留，月报保留100条，其余30条），保留聚合字段
    safe: Dict[str, Any] = {}
    item_limit = 100 if report_type == "monthly" else 30
    for k, v in data.items():
        if isinstance(v, dict) and "items" in v:
            d = dict(v)
            items = d.get("items") or []
            d["items"] = items[:item_limit]
            safe[k] = d
        else:
            safe[k] = v
    parts.append(json.dumps(safe, ensure_ascii=False, default=str, indent=2))
    parts.append("```")
    return "\n".join(parts)
