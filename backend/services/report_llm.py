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
    """构造「下期重点计划」小节（按模块对齐本期进展，规则模板与 LLM 兜底共用）。"""
    title = _NEXT_TITLE.get(report_type, "下阶段重点")
    lines = [f"## 七、{title}", ""]
    req = data.get("requirement", {}) or {}
    op = data.get("operation_issue", {}) or {}
    ma = data.get("meeting_action", {}) or {}
    td = data.get("todo", {}) or {}
    hs = op.get("high_sensitivity", []) or []
    handlers = op.get("by_handler", {}) or {}
    overdue_h = [h for h, v in handlers.items() if (v.get("overdue") or 0) > 0]
    ma_total = ma.get("total") or 0
    ma_done = ma.get("done") or 0
    po = req.get("po_risk", []) or []
    ongoing = (req.get("buckets", {}) or {}).get("ongoing", []) or []

    lines.append("### 需求与交付")
    for p in po[:5]:
        lines.append(f"- 推进 {p.get('req_name')}（{p.get('priority')}/{p.get('status')}，风险：{p.get('risk_note') or '待补充'}）闭环上线")
    if ongoing:
        lines.append(f"- 继续推进进行中需求：{'; '.join(ongoing[:5])}")
    if not po and not ongoing:
        lines.append("- （本期无在途/风险需求，按计划推进既有需求）")
    lines.append("")

    lines.append("### 运营支撑")
    if hs:
        lines.append(f"- 盯办高敏工单（P0/P1）{len(hs)} 条闭环，防止升级")
    if overdue_h:
        lines.append(f"- 跟进超期处理人：{', '.join(overdue_h[:5])}，压缩处置时长")
    if not hs and not overdue_h:
        lines.append("- （本期运营平稳，维持常态化支撑）")
    lines.append("")

    lines.append("### 会议与协同")
    if ma_total and ma_done < ma_total:
        lines.append(f"- 闭环未完成的会议行动项（剩 {ma_total - ma_done} 项）")
    else:
        lines.append("- （本期会议行动项均已闭环，关注新决议落地）")
    lines.append("")

    lines.append("### 个人待办")
    if td.get("overdue"):
        lines.append(f"- 清理超期个人待办（{td['overdue']} 项）")
    else:
        lines.append("- （个人待办无超期，保持节奏）")
    lines.append("")

    lines.append("### 知识中心")
    lines.append("- 沉淀本期典型问题/交付经验到知识库，形成可复用资产")
    lines.append("")
    return "\n".join(lines)


def render_rule_template(data: Dict[str, Any], report_type: str = "daily") -> str:
    """LLM 不可用时的规则模板渲染（分析型兜底：数据 + 判断/结论，非纯数字罗列）。"""
    lines: list[str] = []
    ds, de = data.get("date_start"), data.get("date_end")
    title = _RULE_TITLE.get(report_type, "工作日报")
    lines.append(f"# {title}（{ds} ~ {de}）")
    lines.append("")

    req = data.get("requirement", {}) or {}
    op = data.get("operation_issue", {}) or {}
    mt = data.get("meeting", {}) or {}
    ma = data.get("meeting_action", {}) or {}
    td = data.get("todo", {}) or {}
    kn = data.get("knowledge", {}) or {}

    buckets = req.get("buckets", {}) or {}
    delivered = buckets.get("delivered") or []
    added = buckets.get("added") or []
    evaluated = buckets.get("evaluated") or []
    dev_start = buckets.get("dev_start") or []
    ongoing = buckets.get("ongoing") or []
    po = req.get("po_risk", []) or []

    op_cat = op.get("by_category") or {}
    op_total = sum(op_cat.values()) if isinstance(op_cat, dict) else 0
    hs = op.get("high_sensitivity", []) or []
    handlers = op.get("by_handler", {}) or {}
    mt_items = mt.get("items") or []
    mt_total = mt.get("total") or len(mt_items)
    td_total = td.get("total") or 0
    td_done = td.get("done") or 0
    td_rate = float(td.get("completion_rate", 0) or 0)
    td_overdue = td.get("overdue", 0) or 0
    kn_total = kn.get("total") or 0
    ma_total = ma.get("total") or 0
    ma_done = ma.get("done") or 0
    ma_rate = float(ma.get("completion_rate", 0) or 0)

    # 一、本期概述（分析型：整体判断领先）
    lines.append("## 一、本期概述")
    judge = []
    if delivered:
        judge.append(f"需求交付 {len(delivered)} 项，交付侧有实质产出")
    elif ongoing:
        judge.append(f"本期需求零交付，{len(ongoing)} 条仍在进行中，交付节奏后移")
    else:
        judge.append("本期无需求交付")
    if hs:
        judge.append(f"运营侧 {len(hs)} 条高敏（P0/P1）工单，处置压力突出")
    if ma_total and ma_done < ma_total:
        judge.append(f"会议行动项仅闭环 {ma_done}/{ma_total}（{ma_rate * 100:.0f}%），决议落地滞后")
    if td_overdue:
        judge.append(f"个人待办超期 {td_overdue} 项")
    elif td_total and td_rate < 1:
        judge.append(f"个人待办完成率 {td_rate * 100:.0f}%，仍有缺口")
    if po:
        judge.append(f"{len(po)} 项 PO 级交付风险待推进")
    overview = "；".join(judge) if judge else "本期各模块运行平稳，无突出风险"
    lines.append(f"- 本期整体判断：{overview}。")
    lines.append(
        f"- 关键数据：需求新增 {len(added)}/评估完成 {len(evaluated)}/启动开发 {len(dev_start)}/交付 {len(delivered)}；"
        f"运营工单 {op_total} 条（高敏 {len(hs)}）；会议 {mt_total} 场；"
        f"个人待办 {td_total} 项（完成率 {td_rate * 100:.0f}%）；知识维护 {kn_total} 条。"
    )
    lines.append("")

    # 二、需求与交付（分析型）
    lines.append("## 二、需求与交付")
    if delivered:
        tail = " 等" if len(delivered) > 5 else ""
        lines.append(f"- 交付：完成 {len(delivered)} 项需求开发交付（{'; '.join(delivered[:5])}{tail}），交付侧有实质产出。")
    else:
        lines.append(f"- 交付节奏：本期交付为 0，{len(ongoing)} 条需求仍处于进行中，交付压力后移，需关注排期与卡点。")
    if evaluated:
        tail = " 等" if len(evaluated) > 5 else ""
        lines.append(f"- 评估：完成 {len(evaluated)} 项需求评估（{'; '.join(evaluated[:5])}{tail}），需求侧进入方案细化阶段。")
    if added:
        tail = " 等" if len(added) > 3 else ""
        lines.append(f"- 新增跟踪：{len(added)} 项新需求进入跟踪（{'; '.join(added[:3])}{tail}）。")
    if dev_start:
        lines.append(f"- 启动开发：{len(dev_start)} 项需求启动开发。")
    if po:
        lines.append("- PO 级交付风险（需重点盯办）：")
        for p in po[:10]:
            lines.append(
                f"  - {p.get('req_name')}（{p.get('priority')}/{p.get('status')}，"
                f"上线{p.get('go_live') or '未定'}）：{p.get('risk_note') or '风险待补充'}"
            )
    else:
        lines.append("- PO 级交付风险：本期无在途 PO 级风险。")
    lines.append("")

    # 三、运营支撑（分析型）
    lines.append("## 三、运营支撑")
    if op_total:
        top = sorted(op_cat.items(), key=lambda x: -x[1])[:3]
        top_str = "、".join(f"{k} {v}" for k, v in top)
        lines.append(f"- 工单分布：本期共 {op_total} 条，高发类别为 {top_str}，建议针对高发类别建立常态化处置与知识沉淀。")
        if hs:
            hs_cats: Dict[str, int] = {}
            for h in hs:
                c = h.get("category") or "?"
                hs_cats[c] = hs_cats.get(c, 0) + 1
            lines.append(f"- 高敏工单（P0/P1）{len(hs)} 条（{'; '.join(f'{k} {v}' for k, v in hs_cats.items())}），已纳入重点盯办，防止升级投诉。")
        else:
            lines.append("- 高敏工单（P0/P1）：本期无。")
        backlog = sorted(handlers.items(), key=lambda x: -(x[1].get("total", 0) - x[1].get("done", 0)))[:3]
        if backlog:
            bstr = "；".join(f"{h} 积压 {v['total'] - v['done']} 条（已办 {v['done']}/{v['total']}）" for h, v in backlog)
            lines.append(f"- 处理人时效：处置压力集中在 {bstr}，需关注时效与分流。")
        overdue_h = [h for h, v in handlers.items() if v.get("overdue")]
        if overdue_h:
            lines.append(f"- 超期处理人：{', '.join(overdue_h)}，需压缩处置时长。")
    else:
        lines.append("- 本期无运营工单。")
    lines.append("")

    # 四、会议与协同（分析型）
    lines.append("## 四、会议与协同")
    if mt_total:
        topics = {"验收": 0, "方案": 0, "调研": 0, "交流": 0, "其他": 0}
        for m in mt_items:
            t = m.get("title") or ""
            if "验收" in t:
                topics["验收"] += 1
            elif "方案" in t:
                topics["方案"] += 1
            elif "调研" in t:
                topics["调研"] += 1
            elif "交流" in t:
                topics["交流"] += 1
            else:
                topics["其他"] += 1
        comp = "、".join(f"{k} {v} 场" for k, v in topics.items() if v)
        lines.append(f"- 会议构成：本期 {mt_total} 场（{comp}），协同推进验收、方案与调研等重点事项。")
        if ma_total:
            if ma_done < ma_total:
                lines.append(f"- 会议行动项完成率 {ma_rate * 100:.0f}%（{ma_done}/{ma_total}），闭环偏低，决议落地存在卡点，需指定责任人跟办未闭环项。")
            else:
                lines.append(f"- 会议行动项完成率 {ma_rate * 100:.0f}%（{ma_done}/{ma_total}），决议落地良好。")
        else:
            lines.append("- 本期无会议行动项跟踪。")
    else:
        lines.append("- 本期无会议。")
    lines.append("")

    # 五、个人待办（分析型）
    lines.append("## 五、个人待办")
    if td_total:
        if td_overdue:
            lines.append(f"- 个人待办 {td_total} 项，完成率 {td_rate * 100:.0f}%，超期 {td_overdue} 项——本周个人执行偏弱，需优先清理超期项。")
        elif td_rate < 1:
            lines.append(f"- 个人待办 {td_total} 项，完成率 {td_rate * 100:.0f}%，仍有 {td_total - td_done} 项在办，保持节奏推进。")
        else:
            lines.append(f"- 个人待办 {td_total} 项，完成率 100%，执行良好。")
        if td.get("by_category"):
            lines.append(f"- 待办分类：{td['by_category']}。")
    else:
        lines.append("- 本期无个人待办。")
    lines.append("")

    # 六、知识中心（分析型）
    lines.append("## 六、知识中心")
    if kn_total:
        topk = sorted(kn.get("by_category", {}).items(), key=lambda x: -x[1])[:3]
        lines.append(f"- 本期维护知识 {kn_total} 条，以 {'、'.join(f'{k} {v}' for k, v in topk)} 为主，知识沉淀活跃。")
        lines.append("- 建议：补充运营处置与系统平台类知识占比，形成可复用资产。")
    else:
        lines.append("- 本期暂无知识沉淀。")
    lines.append("")

    # 七、下期重点计划（按模块对齐本期进展，确定性版）
    lines.append(build_next_period_section(data, report_type))
    return "\n".join(lines)
