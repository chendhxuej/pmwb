"""AI总结提示词构造 —— 深度分析 + 下期重点计划，面向管理汇报。"""
from __future__ import annotations

import json
from typing import Any, Dict

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
- requirement（需求与交付）：items 为每条需求明细；buckets 为本期需求生命周期分桶（added 新增跟踪 / evaluated 完成评估 / dev_start 启动开发 / delivered 完成开发交付 / ongoing 进行中）；po_risk 为 PO 级交付风险清单。
- operation_issue（运营支撑）：by_category 各子类工单量；by_status 状态分布；by_impact 影响等级分布；by_handler 各处理人（总量/已办/超期）；high_sensitivity 为高敏（P0/P1）工单清单。
- dev_ticket（开发工单）：by_status 状态分布。
- meeting（会议）：本期会议列表（主题/时间/纪要摘要/主持人）。
- meeting_action（会议行动项）：total/done/completion_rate 完成率。
- todo（个人待办）：total/done/completion_rate/overdue 超期数/by_category/by_priority。
- knowledge（知识中心）：total 本期维护条目数/by_category。

# 撰写要求（深度分析，禁止流水账）
一、需求与交付：按 buckets 分桶叙述——新增了哪些需求、完成了哪些需求的评估、哪些需求启动开发、哪些需求完成了开发交付（交付类必须写「完成了【需求名称】需求的开发部署工作，核心实现了【具体功能/服务流程】，体现了【业务价值】」）。单独用一小节「PO 级交付风险」列出 po_risk 中风险，提示卡点。
二、运营支撑：按 by_category 简述各子类工单处置情况，单列「高敏工单（P0/P1）处理进展」盯办结果，单列「处理人时效」对各 handler 的已办/超期做简短点评。
三、会议与协同：提炼各会议的价值（从纪要摘要/主题提炼达成了什么结论或决议），单列「会议行动项完成率」并点出未闭环重点项。
四、个人待办：单独分析我个人待办完成情况（完成率/超期），不与他人混淆。
五、知识中心：说明本期知识维护情况（条目数/分类）；若数据为空，注明「本期暂无知识沉淀」。
六、下期重点计划：{next_req}

输出纯 Markdown，使用二级/三级标题分区，要点用列表，语言精炼、面向管理汇报。"""

# 各类报告对「六、下期重点计划」的具体要求
_NEXT_PERIOD_REQ = {
    "daily": "日报写「明日关注」：基于本期未完成待办/超期项，列出明日需推进的 1-3 件事。",
    "weekly": "周报写「六、下周重点计划」：基于本期 po_risk、未闭环会议行动项、超期待办，给出下周需推进的具体事项（含责任判断与预期产出）。",
    "monthly": "月报写「六、下月重点工作与趋势研判」：既列下月重点事项，也对本期数据做趋势研判（如需求交付节奏、工单高发类别、风险收敛情况），给出下月策略建议。",
    "custom": "自定义报告写「六、下阶段重点」：基于本期风险与未完成项，给出下阶段重点事项。",
}

TYPE_PROMPTS = {
    "daily": "这是日报，聚焦当天进展与明日关注，篇幅适中。",
    "weekly": "这是周报，按周复盘需求/运营/会议/待办的深度进展，交付类需求必须写「完成【需求】开发部署，核心实现【功能】，体现【价值】」，末尾必须包含「六、下周重点计划」。",
    "monthly": "这是月报，做月度总结与趋势研判，交付类需求必须写「完成【需求】开发部署，核心实现【功能】，体现【价值】」，末尾必须包含「六、下月重点工作与趋势研判」（含趋势判断与下月策略）。",
    "custom": "这是自定义区间报告，按区间复盘进展，末尾包含「六、下阶段重点」。",
}

_TYPE_LABELS = {"daily": "日", "weekly": "周", "monthly": "月", "custom": "自定义"}


def build_system_prompt(report_type: str) -> str:
    title_label = _TITLE_LABELS.get(report_type, "工作日报")
    next_req = _NEXT_PERIOD_REQ.get(report_type, _NEXT_PERIOD_REQ["custom"])
    prompt = SYSTEM_PROMPT_COMMON.format(type=title_label, next_req=next_req)
    return prompt + "\n\n" + TYPE_PROMPTS.get(report_type, "")


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
