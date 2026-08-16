"""AI总结 LLM 生成客户端 —— 复用底层 LLM（Kimi/Moonshot）。

LLM 不可用时自动降级到规则模板（render_rule_template），保证报告永远有内容。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from services.llm_provider import call_best_available

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


def _build_delivered_item_summary(it: Dict[str, Any]) -> str:
    """把一条上线/交付需求明细写成「完成了XX开发部署，核心实现...，体现...」的标准句式。"""
    req_name = it.get("req_name") or "未命名需求"
    system = it.get("system_name") or ""
    sa = it.get("sa_name") or ""
    go_live = it.get("go_live") or "未定"
    desc = (it.get("description") or "").strip()
    bg = (it.get("background") or "").strip()
    clarification = (it.get("clarification") or "").strip()
    # 取最能说明「核心实现」的字段
    core = desc or clarification or bg or "具体功能待补充"
    # 业务价值：优先从背景/需求名+系统推导
    value = bg or f"支撑{system}相关业务能力提升" if system else "支撑相关业务落地"
    meta_parts = [p for p in [
        f"系统：{system}" if system else None,
        f"SA：{sa}" if sa else None,
        f"上线：{go_live}" if go_live else None,
    ] if p]
    meta = "（" + "，".join(meta_parts) + "）" if meta_parts else ""
    return f"  - 完成【{req_name}】开发部署{meta}：核心实现「{core}」，体现「{value}」"


def _md_table(headers: List[str], rows: List[Tuple[str, ...]]) -> str:
    """生成 GFM 表格字符串（无数据时返回空串）。"""
    if not rows:
        return ""
    lines = ["| " + " | ".join(headers) + " |",
             "| " + " | ".join(["---"] * len(headers)) + " |"]
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(lines)


def generate_report_markdown(db, system_prompt: str, user_message: str):
    """调用 LLM 生成报告正文，返回 (markdown, used_llm, provider_name, notice)。

    底层走多模型注册表（services.llm_provider），按优先级 fallback；
    全部不可用时返回 ("", False, None, notice)，由上层降级到规则模板。
    """
    try:
        res = call_best_available(db, system_prompt, user_message)
        return res["text"], res["used_llm"], res["provider_name"], res["notice"]
    except Exception as e:  # noqa: BLE001
        logger.warning("AI总结 LLM 生成失败，将降级规则模板: %s", e)
        return "", False, None, f"LLM 调用异常：{str(e)[:200]}"


def build_next_period_section(data: Dict[str, Any], report_type: str) -> str:
    """构造「下期重点计划」小节（按模块对齐本期进展，规则模板与 LLM 兜底共用）。

    关键改进：计划段逐一列出具体对象（高敏工单标题 / 未闭环行动项 / 超期待办），
    不再只给数字；对象清单来自采集器补抛的 high_sensitivity / meeting_action.unfinished /
    todo.overdue_items / requirement.po_risk / requirement.buckets.ongoing。
    """
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
    ma_unfinished = ma.get("unfinished") or []
    po = req.get("po_risk", []) or []
    ongoing = (req.get("buckets", {}) or {}).get("ongoing", []) or []
    td_overdue_items = td.get("overdue_items") or []

    # 需求与交付
    lines.append("### 需求与交付")
    if po:
        lines.append("- **PO 级风险需求闭环**（需重点盯办）：")
        for p in po[:5]:
            lines.append(f"  - 推进【{p.get('req_name')}】（{p.get('priority')}/{p.get('status')}）"
                         f"闭环上线，卡点：{p.get('risk_note') or '待补充'}")
    if ongoing:
        lines.append(f"- 继续推进进行中需求（{len(ongoing)} 条）：")
        for n in ongoing[:6]:
            lines.append(f"  - {n}")
    if not po and not ongoing:
        lines.append("- （本期无在途/风险需求，按计划推进既有需求）")
    lines.append("")

    # 运营支撑
    lines.append("### 运营支撑")
    if hs:
        lines.append(f"- **高敏（P0/P1）工单盯办**（{len(hs)} 条，防止升级）：")
        for h in hs[:6]:
            handler = h.get("handler") or "待指派"
            lines.append(f"  - 【{h.get('title') or h.get('issue_no')}】（{h.get('category')}/{h.get('impact')}"
                         f"，处理人：{handler}）闭环处置")
    if overdue_h:
        lines.append(f"- 跟进超期处理人：{', '.join(overdue_h[:5])}，压缩处置时长")
    if not hs and not overdue_h:
        lines.append("- （本期运营平稳，维持常态化支撑）")
    lines.append("")

    # 会议与协同
    lines.append("### 会议与协同")
    if ma_unfinished:
        lines.append(f"- **未闭环会议行动项**（剩 {len(ma_unfinished)} 项，需指定责任人跟办）：")
        for a in ma_unfinished[:6]:
            due = a.get("due_date") or "未定"
            lines.append(f"  - 【{a.get('title')}】（负责人：{a.get('owner')}，截止：{due}）")
    elif ma_total:
        lines.append(f"- （本期 {ma_total} 项会议行动项均已闭环，关注新决议落地）")
    else:
        lines.append("- （本期无会议行动项跟踪）")
    lines.append("")

    # 个人待办
    lines.append("### 个人待办")
    if td_overdue_items:
        lines.append(f"- **清理超期个人待办**（{len(td_overdue_items)} 项）：")
        for t in td_overdue_items[:6]:
            due = t.get("due_date") or "未定"
            lines.append(f"  - 【{t.get('title')}】（{t.get('category')}，截止：{due}）")
    else:
        lines.append("- （个人待办无超期，保持节奏）")
    lines.append("")

    # 知识中心
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

    # ---- 关键指标速览（表格，便于一眼掌握全局）----
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
    # 整体判断作为 callout，醒目
    lines.append(f"> **本期整体判断**：{overview}。")
    lines.append("")
    lines.append("**关键指标速览：**")
    lines.append(_md_table(
        ["维度", "指标"],
        [
            ("需求交付", f"{len(delivered)} 项（新增 {len(added)} / 评估完成 {len(evaluated)} / 启动开发 {len(dev_start)}）"),
            ("运营支撑", f"{op_total} 条（高敏 {len(hs)}）"),
            ("会议协同", f"{mt_total} 场，行动项闭环 {ma_done}/{ma_total}（{ma_rate * 100:.0f}%）"),
            ("个人待办", f"{td_total} 项（完成率 {td_rate * 100:.0f}%，超期 {td_overdue}）"),
            ("知识中心", f"{kn_total} 条"),
        ],
    ))
    lines.append("")

    # 二、需求与交付（分析型，上线需求逐一总结）
    lines.append("## 二、需求与交付")
    delivered_items = req.get("delivered_items") or []
    if delivered_items:
        lines.append(f"- 本期完成上线/交付 {len(delivered_items)} 项需求，逐一总结如下：")
        for it in delivered_items[:15]:
            lines.append(_build_delivered_item_summary(it))
        lines.append(f"- 交付节奏判断：{len(delivered_items)} 项需求已按计划上线，交付侧有实质产出。")
    elif delivered:
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
        lines.append("- **PO 级交付风险**（需重点盯办）：")
        lines.append(_md_table(
            ["需求", "优先级", "状态", "风险/卡点"],
            [(p.get("req_name"), p.get("priority"), p.get("status"), p.get("risk_note") or "待补充") for p in po[:10]],
        ))
    else:
        lines.append("- PO 级交付风险：本期无在途 PO 级风险。")
    lines.append("")

    # 三、运营支撑（分析型）
    lines.append("## 三、运营支撑")
    if op_total:
        lines.append("- **工单类别分布**：")
        lines.append(_md_table(
            ["类别", "数量"],
            sorted(((k, v) for k, v in op_cat.items()), key=lambda x: -x[1])[:6],
        ))
        if hs:
            lines.append(f"- **高敏（P0/P1）工单 {len(hs)} 条**，已纳入重点盯办，防止升级投诉：")
            for h in hs[:6]:
                handler = h.get("handler") or "待指派"
                lines.append(f"  - 【{h.get('title') or h.get('issue_no')}】（{h.get('category')}/{h.get('impact')}"
                             f"，处理人：{handler}）")
        else:
            lines.append("- 高敏（P0/P1）工单：本期无。")
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
            lines.append(f"- 个人待办 {td_total} 项，完成率 {td_rate * 100:.0f}%，**超期 {td_overdue} 项**——本周个人执行偏弱，需优先清理超期项：")
            for t in (td.get("overdue_items") or [])[:6]:
                due = t.get("due_date") or "未定"
                lines.append(f"  - 【{t.get('title')}】（{t.get('category')}，截止：{due}）")
        elif td_rate < 1:
            lines.append(f"- 个人待办 {td_total} 项，完成率 {td_rate * 100:.0f}%，仍有 {td_total - td_done} 项在办，保持节奏推进。")
        else:
            lines.append(f"- 个人待办 {td_total} 项，完成率 100%，执行良好。")
        if td.get("by_category"):
            cat_str = "、".join(f"{k} {v}" for k, v in (td.get("by_category") or {}).items())
            lines.append(f"- 待办分类：{cat_str}。")
    else:
        lines.append("- 本期无个人待办。")
    lines.append("")

    # 六、知识中心
    lines.append("## 六、知识中心")
    if kn_total:
        topk = sorted(kn.get("by_category", {}).items(), key=lambda x: -x[1])[:3]
        lines.append(f"- 本期维护知识 {kn_total} 条，以 {'、'.join(f'{k} {v}' for k, v in topk)} 为主，知识沉淀活跃。")
        lines.append("- 建议：补充运营处置与系统平台类知识占比，形成可复用资产。")
    else:
        lines.append("- 本期暂无知识沉淀。")
    lines.append("")

    # 七、下期重点计划（按模块对齐本期进展，列出具体对象）
    lines.append(build_next_period_section(data, report_type))
    return "\n".join(lines)
