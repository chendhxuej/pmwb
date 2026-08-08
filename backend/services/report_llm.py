"""AI总结 LLM 生成客户端 —— 复用底层 LLM（Kimi/Moonshot）。

LLM 不可用时自动降级到规则模板（render_rule_template），保证报告永远有内容。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from services.storygen_llm import _call_llm, check_llm_available

logger = logging.getLogger(__name__)

# 规则模板兜底标题（随报告类型）
_RULE_TITLE = {
    "daily": "工作日报",
    "weekly": "工作周报",
    "monthly": "工作月报",
    "custom": "专项报告",
}

# 下期重点计划小节标题（随报告类型）
_NEXT_TITLE = {
    "daily": "明日关注",
    "weekly": "下周重点计划",
    "monthly": "下月重点工作与趋势研判",
    "custom": "下阶段重点",
}


def llm_available() -> bool:
    try:
        st = check_llm_available()
        return bool(st.get("enabled")) and st.get("reachable") is True
    except Exception:  # noqa: BLE001
        return False


def generate_report_markdown(system_prompt: str, user_message: str) -> Tuple[str, bool]:
    """调用 LLM 生成报告正文，返回 (markdown, used_llm)。"""
    try:
        if not llm_available():
            return "", False
        raw = _call_llm(system_prompt, user_message)
        return (raw or "").strip(), True
    except Exception as e:  # noqa: BLE001
        logger.warning("AI总结 LLM 生成失败，将降级规则模板: %s", e)
        return "", False


def build_next_period_section(data: Dict[str, Any], report_type: str) -> str:
    """构造「下期重点计划」小节（规则模板与 LLM 兜底共用）。"""
    title = _NEXT_TITLE.get(report_type, "下阶段重点")
    lines = [f"## 六、{title}", ""]
    po = (data.get("requirement", {}) or {}).get("po_risk", []) or []
    ma = data.get("meeting_action", {}) or {}
    td = data.get("todo", {}) or {}
    added = 0
    for p in po[:5]:
        lines.append(
            f"- 推进 {p.get('req_name')}（{p.get('priority')}/{p.get('status')}，"
            f"风险：{p.get('risk_note') or '待补充'}）"
        )
        added += 1
    ma_total = ma.get("total") or 0
    ma_done = ma.get("done") or 0
    if ma_total and ma_done < ma_total:
        lines.append(f"- 闭环未完成的会议行动项（剩 {ma_total - ma_done} 项）")
        added += 1
    if td.get("overdue"):
        lines.append(f"- 处理超期个人待办（{td['overdue']} 项）")
        added += 1
    if added == 0:
        lines.append("- （本期无显著风险线索，建议按既定计划推进，可补充具体事项）")
    lines.append("")
    return "\n".join(lines)


def render_rule_template(data: Dict[str, Any], report_type: str = "daily") -> str:
    """LLM 不可用时的规则模板渲染（结构化汇总，含下期重点计划）。"""
    lines: list[str] = []
    ds, de = data.get("date_start"), data.get("date_end")
    title = _RULE_TITLE.get(report_type, "工作日报")
    lines.append(f"# {title}（{ds} ~ {de}）")
    lines.append("")

    req = data.get("requirement", {}) or {}
    lines.append("## 一、需求与交付")
    buckets = req.get("buckets", {}) or {}
    if buckets.get("delivered"):
        lines.append(f"- 完成开发交付：{'; '.join(buckets['delivered'])}")
    if buckets.get("dev_start"):
        lines.append(f"- 启动开发：{'; '.join(buckets['dev_start'])}")
    if buckets.get("evaluated"):
        lines.append(f"- 完成评估：{'; '.join(buckets['evaluated'])}")
    if buckets.get("added"):
        lines.append(f"- 新增跟踪：{'; '.join(buckets['added'])}")
    if buckets.get("ongoing"):
        lines.append(f"- 进行中：{'; '.join(buckets['ongoing'])}")
    po = req.get("po_risk", []) or []
    if po:
        lines.append("- PO 级交付风险：")
        for p in po[:10]:
            lines.append(
                f"  - {p.get('req_name')}（{p.get('priority')}/{p.get('status')}，"
                f"上线{p.get('go_live') or '未定'}）{p.get('risk_note') or ''}"
            )
    lines.append("")

    op = data.get("operation_issue", {}) or {}
    lines.append("## 二、运营支撑")
    if op.get("by_category"):
        lines.append(f"- 工单分类分布：{op['by_category']}")
    if op.get("high_sensitivity"):
        lines.append(f"- 高敏工单（P0/P1）{len(op['high_sensitivity'])} 条，需重点盯办。")
    if op.get("by_handler"):
        lines.append("- 处理人时效：")
        for h, v in list(op["by_handler"].items())[:10]:
            lines.append(f"  - {h}：总量{v['total']}/已办{v['done']}/超期{v['overdue']}")
    lines.append("")

    mt = data.get("meeting", {}) or {}
    ma = data.get("meeting_action", {}) or {}
    lines.append("## 三、会议与协同")
    if mt.get("items"):
        lines.append(f"- 本期会议 {mt['total']} 场：")
        for m in mt["items"][:10]:
            lines.append(f"  - {m.get('title')}（{(m.get('start_time') or '')[:10]}）")
    rate = ma.get("completion_rate") or 0
    lines.append(f"- 会议行动项完成率：{float(rate) * 100:.0f}%（{ma.get('done')}/{ma.get('total')}）")
    lines.append("")

    td = data.get("todo", {}) or {}
    lines.append("## 四、个人待办")
    lines.append(
        f"- 完成率：{float(td.get('completion_rate', 0)) * 100:.0f}%"
        f"（{td.get('done')}/{td.get('total')}），超期 {td.get('overdue', 0)} 条"
    )
    if td.get("by_category"):
        lines.append(f"- 分类分布：{td['by_category']}")
    lines.append("")

    kn = data.get("knowledge", {}) or {}
    lines.append("## 五、知识中心")
    if kn.get("total"):
        lines.append(f"- 本期维护知识 {kn['total']} 条：{kn.get('by_category')}")
    else:
        lines.append("- 本期暂无知识沉淀。")
    lines.append("")

    # 六、下期重点计划
    lines.append(build_next_period_section(data, report_type))
    return "\n".join(lines)
