"""AI总结提示词构造 —— 深度分析 + 下期重点计划，面向管理汇报。"""
from __future__ import annotations

import json
from typing import Any, Dict

from services.report_dict import GLOSSARY

# 报告标题标签（用于提示词中的《XXX》）
_TITLE_LABELS = {
    "daily": "工作日报",
    "weekly": "工作周报",
    "monthly": "工作月报",
    "custom": "专项报告",
}

SYSTEM_PROMPT_COMMON = """你是一名资深产品经理（政企/商客方向）的个人工作助理，负责把分散在各业务系统的原始数据，提炼成一份结构清晰、有分析深度、可直接用于管理汇报的《{type}》。

# 输入数据说明
你会收到一段 JSON 格式的原始工作数据，包含以下模块：
- requirement（需求与交付）：items 为每条需求明细；buckets 为本期需求生命周期分桶（added 新增跟踪 / evaluated 完成评估 / dev_start 启动开发 / delivered 完成开发交付 / ongoing 进行中）；delivered_items 为本期上线/交付需求明细（含 req_name/system_name/sa_name/go_live/description/background/workload/dev_status 等字段），po_risk 为 PO 级交付风险清单（含 req_name/priority/status/risk_note）。
- operation_issue（运营支撑）：by_category 各子类工单量（已转中文）；by_status 状态分布（已转中文）；by_impact 影响等级分布（已转中文）；by_handler 各处理人（含 total 总量/done 已办/overdue 超期/done_rate 完成率/overdue_rate 超期率）；high_sensitivity 为高敏（P0/P1）工单清单（含 issue_no/title/category/status/handler/impact，均已转中文）。
- dev_ticket（开发工单）：by_status 状态分布（已转中文）。
- meeting（会议）：本期会议列表（主题/时间/纪要摘要/主持人）。
- meeting_action（会议行动项）：total/done/completion_rate 完成率；unfinished 为未闭环行动项列表（含 title/owner/due_date/status），供下期计划逐条列出具体对象。
- todo（个人待办）：total/done/completion_rate/overdue 超期数/by_category/by_priority；overdue_items 为超期待办列表（含 title/due_date/category/priority），供下期计划逐条列出具体对象。
- knowledge（知识中心）：total 本期维护条目数/by_category。

# 中文转译铁律
输入 JSON 中仍可能出现个别未转译的内部编码（如优先级 P0、自由文本状态等）。文末附《内部编码→中文标签对照表》，撰写报告时**必须**将所有状态/分类/优先级/影响等级统一转写为对照表中的中文标签，禁止在正文保留 pending/resolved/closed/P0/prod 等英文内部编码。

# 撰写要求（深度分析，禁止流水账）
核心铁律：每个章节在列出关键数据后，必须紧跟一句「判断 / 结论 / 建议」（如趋势、风险、卡点、下一步），禁止只罗列数字或名称。

一、本期概述（高度概括 + 综合研判 + 人员时效）：这是全文导读，必须是对下方「二~六」各章节核心结论的**高度概括与综合研判**，禁止与下方章节逐条重复数字。结构如下：
1. 先用引用块（> ）给出「本期整体判断」一句总评（如：需求交付按计划、运营处置承压、协同落地滞后等综合判断）。
2. 「关键指标速览」表格（维度 / 本期指标两列，覆盖需求 / 运营 / 会议 / 待办 / 知识五模块）。
3. **人员时效与改进要求（重点）**：基于 operation_issue.by_handler（各处理人 total/done/overdue/done_rate/overdue_rate），计算各相关人员的工单完成及时率，识别出**完成及时率偏低、超期突出的处理人**，对其**明确提出改进要求**（如：要求压缩 XX 工单处置时长、限期闭环超期项）；若存在多名问题人员，逐一点名与要求。若人员时效整体良好，简要肯定。

二、需求与交付：先写一段「本章概述」——概括本周需求整体情况（规模 / 推进节奏 / 风险态势一句话）。再按子章节总结（均须「数据 + 一句判断」）：
- ### 2.1 新增需求：本期新增跟踪需求（buckets.added），说明数量与重点方向。
- ### 2.2 在途需求：进行中需求（buckets.ongoing / dev_start / evaluated），说明规模与推进节奏判断。
- ### 2.3 交付需求：本期上线 / 交付需求（delivered_items），逐条写「完成【需求】开发部署（系统：XX，SA：XX，上线：XX），核心实现【功能】，体现【价值】」——**需求列表须同步标注 SA 人员**，禁止只列需求名。
- ### 2.4 风险需求：PO 级交付风险（po_risk，含 SA），列表格（需求 / 优先级 / 状态 / SA / 风险卡点），提示卡点与盯办要求。

三、运营支撑：先写「本章概述」概括运营工单整体态势（总量 / 高发类别 / 时效一句话）。再展开：① 类别分布表；② 高敏（P0/P1）工单盯办（列 high_sensitivity 具体标题与处理人）；③ 处理人时效与改进要求（同概述点名机制）。

四、会议与协同：先写「本章概述」概括会议与协同整体情况。再展开：会议构成与结论提炼（非列标题）、行动项完成率与未闭环重点项（引用 meeting_action.unfinished 具体项与负责人）。

五、个人待办：先写「本章概述」概括个人待办整体执行状态。再展开：完成率 / 超期判断（超期项列 overdue_items 具体标题）、是否需优先清理。

六、知识中心：先写「本章概述」概括知识沉淀情况。再展开维护明细（条数 / 分类构成）与活跃度判断；若为空注明「本期暂无」。

七、下期重点计划：{next_req}

严格要求：① 一~七必须全部出现，缺模块保留标题并注明「本期暂无」，严禁省略任一模块；② 一（概述）必须是二~六的综合研判，并单列「人员时效与改进要求」点名问题处理人；③ 二（需求与交付）必须含「本章概述」+ 2.1~2.4 四个子章节，需求列表标注 SA；④ 三~六每章必须先「本章概述」再展开；⑤ 下期计划须按「需求与交付 / 运营支撑 / 会议与协同 / 个人待办 / 知识中心」五个模块分别给出，禁止只给数字，必须列出具体对象（高敏工单标题 / 未闭环行动项 / 超期待办标题 / 风险需求），对象清单见 high_sensitivity / meeting_action.unfinished / todo.overdue_items / po_risk / buckets.ongoing。

输出纯 Markdown，使用二级/三级标题分区，要点用列表，关键判断用引用块（> ）突出，分布类数据用表格呈现，语言精炼、面向管理汇报。"""


def build_glossary_text() -> str:
    """把内部编码→中文标签对照表渲染为提示词附录文本。"""
    lines = ["# 内部编码→中文标签对照表（撰写报告时必须将代码转写为对应中文）"]
    for cat, m in GLOSSARY.items():
        pairs = "，".join(f"{k}={v}" for k, v in m.items())
        lines.append(f"- {cat}：{pairs}")
    return "\n".join(lines)

# 各类报告对「六、下期重点计划」的具体要求
_NEXT_PERIOD_REQ = {
    "daily": "日报写「七、明日关注」：按「需求 / 运营 / 会议 / 待办 / 知识」五个模块分别列出明日需推进的 1-3 件事，对标今日进展。",
    "weekly": "周报写「七、下周重点计划」：必须按「需求与交付 / 运营支撑 / 会议与协同 / 个人待办 / 知识中心」五个模块分别给出下周计划，每模块计划须对标本周该模块进展（基于 po_risk、未闭环会议行动项、超期待办等推导）。",
    "monthly": "月报写「七、下月重点工作与趋势研判」：按五个模块分别给出下月计划（每模块对标本月进展），并对本期数据做趋势研判（如需求交付节奏、工单高发类别、风险收敛情况），给出下月策略建议。",
    "custom": "自定义报告写「七、下阶段重点」：按五个模块分别给出下阶段计划，对标本期进展。",
}

TYPE_PROMPTS = {
    "daily": "这是日报，聚焦当天进展与明日关注，篇幅适中，须包含「一、本期概述」与「七、明日关注」。",
    "weekly": "这是周报，按周复盘需求/运营/会议/待办/知识的深度进展，须含「一、本期概述」整体总结；交付类需求必须写「完成【需求】开发部署，核心实现【功能】，体现【价值】」；每个模块必须输出「数据 + 一句判断/结论」（交付节奏、运营高发类别、会议落地卡点须明确给出判断），禁止纯罗列；末尾必须包含「七、下周重点计划」（按五个模块分别计划）。",
    "monthly": "这是月报，做月度总结与趋势研判，须含「一、本期概述」整体总结；交付类需求必须写「完成【需求】开发部署，核心实现【功能】，体现【价值】」；末尾必须包含「七、下月重点工作与趋势研判」（按五个模块分别计划 + 趋势判断与下月策略）。",
    "custom": "这是自定义区间报告，按区间复盘进展，须含「一、本期概述」；末尾包含「七、下阶段重点」（按五个模块分别计划）。",
}

_TYPE_LABELS = {"daily": "日", "weekly": "周", "monthly": "月", "custom": "自定义"}


def build_system_prompt(report_type: str) -> str:
    title_label = _TITLE_LABELS.get(report_type, "工作日报")
    next_req = _NEXT_PERIOD_REQ.get(report_type, _NEXT_PERIOD_REQ["custom"])
    prompt = SYSTEM_PROMPT_COMMON.format(type=title_label, next_req=next_req)
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
    # 截断 items 列表（每条最多 30），保留聚合字段
    safe: Dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, dict) and "items" in v:
            d = dict(v)
            items = d.get("items") or []
            d["items"] = items[:30]
            safe[k] = d
        else:
            safe[k] = v
    parts.append(json.dumps(safe, ensure_ascii=False, default=str, indent=2))
    parts.append("```")
    return "\n".join(parts)
