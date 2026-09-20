"""需求分析专题（AI总结）：数据筛选 + 提示词 + 规则降级。

从「需求与交付」模块筛选两类需求工单：
1. 近期已上线：权威上线日期（delivered_date 优先，回退开发工单 go_live_date）落在分析周期内；
2. 计划上线：尚未上线，且进入「启动开发」(stage=dev) 环节已超 overdue_days 天（默认 15 天）。

输出格式（LLM 与规则降级一致）：
- 已上线【需求名称】需求，实现了【能力】。
- 计划上线【需求名称】需求，实现了【能力】。
「能力」依据需求澄清内容高度概括。
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List

from db.models import PmwbDevTicket, PmwbRequirementExt, PmwbRequirementStageLog

logger = logging.getLogger(__name__)

OVERDUE_DAYS_DEFAULT = 15
_CLARIFICATION_PROMPT_CAP = 600  # 送入 LLM 的澄清内容单条截断长度


def _to_date(v) -> date | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    try:
        return datetime_date(v)
    except Exception:  # noqa: BLE001
        return None


def datetime_date(v):
    from datetime import datetime as _dt

    if isinstance(v, _dt):
        return v.date()
    return None


def _clamp(s: str, n: int) -> str:
    return (s or "").strip()[:n]


def _first_sentence(s: str, cap: int = 60) -> str:
    """规则降级用：取澄清内容首句作为能力概括。"""
    text = re.sub(r"\s+", " ", (s or "").strip())
    if not text:
        return ""
    for sep in ["。", "；", "!", "！", "?", "？", "\n"]:
        idx = text.find(sep)
        if idx > 0:
            text = text[:idx]
            break
    # 剥离常见前缀（如「实现」「支持」引导词保留，剥掉编号/标签）
    text = re.sub(r"^[\d一二三四五六七八九十]+[、.．]\s*", "", text)
    return text[:cap]


def collect(db, start: date, end: date, overdue_days: int = OVERDUE_DAYS_DEFAULT) -> Dict[str, Any]:
    """筛选两类需求，返回 {delivered: [...], planned: [...]}。

    delivered/planned 元素：req_id / req_name / clarification / system_name / 上线或进入开发信息。
    """
    rows = db.query(PmwbRequirementExt).all()
    dev_overdue_before = end - timedelta(days=overdue_days)

    # 批量取 stage=dev 进入时间与开发工单上线日期，避免 N+1
    dev_entered: Dict[str, Any] = {}
    for log in db.query(PmwbRequirementStageLog).filter(PmwbRequirementStageLog.stage == "dev").all():
        if log.entered_at:
            dev_entered[log.req_id] = log.entered_at
    ticket_go_live: Dict[str, date] = {}
    for t in db.query(PmwbDevTicket).all():
        d = _to_date(t.go_live_date)
        if d and (t.req_id not in ticket_go_live or d > ticket_go_live[t.req_id]):
            ticket_go_live[t.req_id] = d

    delivered: List[Dict[str, Any]] = []
    planned: List[Dict[str, Any]] = []
    for r in rows:
        if (r.status or "") in ("paused", "suspended"):
            continue
        req_id = r.req_id or ""
        req_name = (r.req_name or "").strip() or req_id
        if not req_name:
            continue
        base = {
            "req_id": req_id,
            "req_name": req_name,
            "clarification": _clamp(r.clarification, _CLARIFICATION_PROMPT_CAP),
            "system_name": (r.system_name or "").strip(),
            "status": r.status or "",
        }
        # 权威上线日期：与 AI 周报口径一致（delivered_date 优先，回退开发工单 go_live_date）
        go_live = _to_date(r.delivered_date) or ticket_go_live.get(req_id)
        if go_live and start <= go_live <= end:
            delivered.append({**base, "go_live": go_live.isoformat()})
            continue
        # 尚未上线 + 进入启动开发环节超期
        # 注：closed 但从未填报上线日期的需求，同样视为未上线，按超期规则正常参与判断
        if go_live:
            continue  # 已上线（周期外）不计入计划上线
        entered = dev_entered.get(req_id)
        if entered and entered.date() <= dev_overdue_before:
            planned.append({
                **base,
                "dev_entered_at": entered.date().isoformat(),
                "dev_overdue_days": (end - entered.date()).days,
            })
    # 已上线按上线日期倒序，计划上线按超期天数倒序
    delivered.sort(key=lambda x: x.get("go_live") or "", reverse=True)
    planned.sort(key=lambda x: x.get("dev_overdue_days") or 0, reverse=True)
    return {"delivered": delivered, "planned": planned}


SYSTEM_PROMPT = (
    "你是资深电信行业产品经理助理，负责输出「需求分析」专题总结。"
    "要求：1) 只依据给出的需求数据输出，不得编造不存在的需求；"
    "2) 每条需求一句话，格式必须严格为：已上线【需求名称】需求，实现了【能力】。"
    "或：计划上线【需求名称】需求，实现了【能力】。"
    "3)【能力】依据需求澄清内容高度概括，简要说明该需求实现的业务能力，"
    "用简洁的业务语言（不超过 35 字），不要罗列技术细节，不要照抄澄清原文；"
    "4) 澄清内容为空时，可依据背景/描述概括，概括不了就写『相关业务能力』；"
    "5) 输出为 Markdown，仅包含指定章节，不要输出其他解释。"
)


def build_prompt(data: Dict[str, Any], start: date, end: date, overdue_days: int = OVERDUE_DAYS_DEFAULT):
    """构造需求分析专题的 system/user 提示词。"""
    delivered = data.get("delivered") or []
    planned = data.get("planned") or []

    lines: List[str] = [
        f"分析周期：{start.isoformat()} ~ {end.isoformat()}（需求分析专题，默认近7天）。",
        "",
        f"## 一、近期已上线需求（{len(delivered)} 条）",
    ]
    if delivered:
        for it in delivered:
            lines.append(
                f"- 需求名称：{it['req_name']}；上线日期：{it.get('go_live', '')}；"
                f"澄清内容：{it.get('clarification') or '（无）'}"
            )
    else:
        lines.append("（无）")

    lines += ["", f"## 二、计划上线需求（进入启动开发环节已超 {overdue_days} 天且尚未上线，{len(planned)} 条）"]
    if planned:
        for it in planned:
            lines.append(
                f"- 需求名称：{it['req_name']}；进入启动开发：{it.get('dev_entered_at', '')}"
                f"（已 {it.get('dev_overdue_days', 0)} 天）；澄清内容：{it.get('clarification') or '（无）'}"
            )
    else:
        lines.append("（无）")

    lines += [
        "",
        "请输出：",
        "# 需求分析（统计区间：%s ~ %s）" % (start.isoformat(), end.isoformat()),
        "",
        "## 近期已上线需求",
        "- （每条格式：已上线【需求名称】需求，实现了【能力】。）",
        "",
        "## 计划上线需求",
        "- （每条格式：计划上线【需求名称】需求，实现了【能力】。）",
        "无数据的章节写「本期暂无」。每条一行，保持给定顺序。",
    ]
    return SYSTEM_PROMPT, "\n".join(lines)


def render_rule(data: Dict[str, Any], start: date, end: date, overdue_days: int = OVERDUE_DAYS_DEFAULT) -> str:
    """规则降级版：能力=澄清内容首句截取（LLM 不可用时兜底，内容仍可用）。"""
    delivered = data.get("delivered") or []
    planned = data.get("planned") or []
    lines = [
        f"# 需求分析（统计区间：{start.isoformat()} ~ {end.isoformat()}）",
        "",
        f"> 降级说明：大模型不可用，能力概括为规则截取（澄清内容首句），非 AI 高度概括。",
        "",
        f"## 近期已上线需求（{len(delivered)} 条）",
    ]
    if delivered:
        for it in delivered:
            cap = _first_sentence(it.get("clarification")) or "相关业务能力"
            lines.append(f"- 已上线【{it['req_name']}】需求，实现了【{cap}】。")
    else:
        lines.append("本期暂无。")
    lines += ["", f"## 计划上线需求（进入启动开发环节已超 {overdue_days} 天，{len(planned)} 条）"]
    if planned:
        for it in planned:
            cap = _first_sentence(it.get("clarification")) or "相关业务能力"
            lines.append(f"- 计划上线【{it['req_name']}】需求，实现了【{cap}】。")
    else:
        lines.append("本期暂无。")
    return "\n".join(lines) + "\n"
