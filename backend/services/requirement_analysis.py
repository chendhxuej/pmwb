"""需求分析专题（AI总结）：数据筛选 + 提示词 + 规则降级。

口径（2026-11-08 老大确认，改动前须再确认）：

1. **已上线**：权威上线日期 = `delivered_date`（手工填报）优先，回退开发工单 `go_live_date`；
   只有落在统计区间内才计入。`closed` 但缺日期的需求**不进正文**，单列
   「数据质量提示」待补录——此前无条件塞进已上线（go_live="未填报"），
   导致 8 月的老需求（如 072000381/072800739/081400648）每期重复出现。

2. **在途需求过程进展**（本周无版本时报告的主体）：从
   `pmwb_requirement_stage_log`（6 环节进出）+ `pmwb_req_dev_event`（开发事件）
   汇总本周实际发生的推进动作，正向表述。
   注：`pmwb_dev_ticket` / `pmwb_dev_ticket_log` 当前 0 行，不能作为过程数据源。

3. **下周计划上线**：三通道并集，每条标命中理由
   T1 期望上线日期落在下周 / T1b 承诺日期已过仍在途 / T2 开发推进超 overdue_days /
   T3 新增资费类快速配置。排序 T1 > T1b > T2 > T3。

4. **口吻**：团队工作成效反馈，积极表述；每条一句话，控字数，不展开技术细节。

输出格式（LLM 与规则降级一致，无中括号）：
- 已上线 需求名称，实现 能力概述。
- 计划上线 需求名称，将实现 能力概述。
- 需求名称：本周<进展动作>，<下一步>。
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from constants import requirement_analysis as R
from constants.status_registry import get_status
from db.models import PmwbDevTicket, PmwbReqDevEvent, PmwbRequirementExt, PmwbRequirementStageLog

logger = logging.getLogger(__name__)

OVERDUE_DAYS_DEFAULT = 15
_CLARIFICATION_PROMPT_CAP = 600  # 送入 LLM 的澄清内容单条截断长度（上限）
_PROMPT_CLARIFY_LONG = 160       # 已上线/计划上线：只需够抓「实现了什么功能」
_PROMPT_CLARIFY_SHORT = 120      # 在途：只需进展与动作，澄清更短
_REASON_RANK = {"T1": 0, "T1b": 1, "T2": 2, "T3": 3}


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
def _to_date(v) -> Optional[date]:
    """统一转 date。注意 datetime 是 date 子类，必须优先判 datetime，
    否则返回 datetime 与 date 比较会抛 TypeError（历史坑）。"""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return None


def _clamp(s: str, n: int) -> str:
    return (s or "").strip()[:n]


def _in_window(d: Optional[date], start: date, end: date) -> bool:
    return bool(d) and start <= d <= end


def _status_label(value: Optional[str]) -> str:
    """状态中文名唯一取自状态注册表，禁本地另存映射。"""
    sd = get_status("requirement", value)
    return sd.label if sd else (value or "")


# 纯编号需求名（如「敏捷需求（2026）第（110500902）号」）对成效反馈零信息量
_NAME_ONLY_RE = re.compile(r"^(?:敏捷需求|手工需求|运营工单)?[（(]\d{4}[）)]第[（(][^）)]+[）)]号$")
_LIST_PREFIX_RE = re.compile(r"^(?:\d+[、.．，,)）]|[（(]\d+[）)]|[①-⑩])\s*")
_SYSTEM_PREFIX_RE = re.compile(r"^[^：:，,。]{1,14}(?:系统)?(?:改造|优化)\s*[：:，,]?\s*")
_CONTENT_PREFIX_RE = re.compile(r"^(?:优化内容|改造内容|需求内容|需求描述|背景|说明)[：:]\s*")


def _is_meaningful_name(name: str) -> bool:
    n = (name or "").strip()
    return bool(n) and not _NAME_ONLY_RE.match(n)


def _capability(text: str, cap: int = R.CAP_CAPABILITY) -> str:
    """规则降级：从澄清原文压出一句话能力概述（去系统前缀/编号，句读处收口）。"""
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return ""
    for sep in ("。", "；", "!", "！", "?", "？", "\n"):
        i = t.find(sep)
        if i > 0:
            t = t[:i]
            break
    t = _CONTENT_PREFIX_RE.sub("", t)
    t = _SYSTEM_PREFIX_RE.sub("", t)
    t = _LIST_PREFIX_RE.sub("", t)
    # 句中夹带「1、2、」列表时，砍掉列表部分
    m = re.search(r"\s+\d+[、.．，,]\s*", t)
    if m and m.start() > 8:
        t = t[: m.start()]
    t = t.strip(" ：:，,、")
    if len(t) > cap:
        cut = t[:cap]
        for sep in ("，", "、", "；", ",", "：", ":", " "):
            j = cut.rfind(sep)
            if j >= 8:
                cut = cut[:j]
                break
        t = cut
    return t.strip(" ，,、；;：:")


def _category_stats(items: List[Dict[str, Any]]) -> str:
    counter: Dict[str, int] = {}
    for it in items:
        cat = (it.get("category") or "").strip() or "未分类"
        counter[cat] = counter.get(cat, 0) + 1
    return "、".join(f"{k} {v} 项" for k, v in sorted(counter.items(), key=lambda x: -x[1]))


def _sorted_by_category(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按分类归组排序（组内保持原顺序），未分类殿后——LLM 与规则降级共用同一顺序。"""
    return sorted(
        items,
        key=lambda it: ((it.get("category") or "").strip() == "", (it.get("category") or "").strip()),
    )


def _is_tariff(req: PmwbRequirementExt) -> bool:
    """新增资费类快速配置：分类命中，或名称/澄清命中资费关键词。"""
    if (req.category or "").strip() == R.TARIFF_CATEGORY:
        return True
    text = f"{req.req_name or ''}{req.clarification or ''}"
    return any(k in text for k in R.TARIFF_KEYWORDS)


def _is_dropped(req: PmwbRequirementExt) -> bool:
    """作废/明确不开发的需求不进报告（否则会把取消的功能当成果播报）。"""
    text = f"{req.clarification or ''}{req.personal_note or ''}{req.owner_note or ''}"
    return any(k in text for k in R.SKIP_KEYWORDS)


# --------------------------------------------------------------------------- #
# 数据采集
# --------------------------------------------------------------------------- #
def _load_maps(db):
    """批量取开发工单上线日、环节日志、开发事件，避免 N+1。"""
    ticket_go_live: Dict[str, date] = {}
    for t in db.query(PmwbDevTicket).all():
        d = _to_date(t.go_live_date)
        if d and (t.req_id not in ticket_go_live or d > ticket_go_live[t.req_id]):
            ticket_go_live[t.req_id] = d

    stages: Dict[Tuple[str, str], PmwbRequirementStageLog] = {}
    for log in db.query(PmwbRequirementStageLog).all():
        stages[(log.req_id, log.stage)] = log

    events: Dict[str, List[PmwbReqDevEvent]] = {}
    for ev in db.query(PmwbReqDevEvent).all():
        events.setdefault(ev.req_id, []).append(ev)
    return ticket_go_live, stages, events


def _inflight_actions(req_id: str, stages, events, start: date, end: date) -> List[str]:
    """本周发生的推进动作（按时间升序去重，最多留最后 N 个）。"""
    acts: List[Tuple[datetime, str]] = []
    for stage in ("collect", "evaluate", "story", "doc", "dev", "deploy"):
        log = stages.get((req_id, stage))
        if not log:
            continue
        entered = log.entered_at
        if entered and _in_window(_to_date(entered), start, end):
            txt = R.STAGE_ACTIONS.get(stage)
            if txt:
                acts.append((entered, txt))
        if stage == "deploy" and log.left_at and _in_window(_to_date(log.left_at), start, end):
            acts.append((log.left_at, "完成生产部署上线"))
    for ev in events.get(req_id, []):
        when = ev.event_time
        if not when or not _in_window(_to_date(when), start, end):
            continue
        txt = R.DEV_EVENT_ACTIONS.get(ev.event_type or "")
        if not txt:
            txt = _clamp((ev.title or "").strip(), 20)
        if txt:
            acts.append((when, txt))
    seen: set = set()
    ordered: List[str] = []
    for _, txt in sorted(acts, key=lambda x: x[0]):
        if txt in seen:
            continue
        seen.add(txt)
        ordered.append(txt)
    return ordered[-R.MAX_INFLIGHT_ACTIONS:]


_PLAN_LIKE = ("完成需求澄清与落地方案评估", "输出需求用户故事与验收标准", "输出需求方案说明书")


def _summarize_actions(actions: List[str]) -> List[str]:
    """把本周多个动作压成 1~2 段可读短语（成效反馈要简短，保持时间顺序）。"""
    group = [a for a in actions if a in _PLAN_LIKE]
    merged = ""
    if group:
        has_eval = any("落地方案评估" in a for a in group)
        has_doc = any("需求方案说明书" in a for a in group)
        has_story = any("用户故事" in a for a in group)
        if has_doc and has_eval:
            merged = "完成落地方案评估并输出需求方案说明书"
        elif has_doc:
            merged = "输出需求方案说明书"
        elif has_eval and has_story:
            merged = "完成落地方案评估并输出用户故事"
        else:
            merged = group[0]
    out: List[str] = []
    used = False
    for a in actions:
        if a in _PLAN_LIKE:
            if not used and merged:
                out.append(merged)
                used = True
            continue
        out.append(a)
    if len(out) > 2:
        # 优先「方案 + 开发/上线」这一对，丢掉前面的受理登记等低信息量动作
        dev_like = [x for x in out if any(k in x for k in ("开发", "测试", "联调", "部署", "上线", "修复"))]
        if dev_like:
            i = out.index(dev_like[-1])
            out = out[max(0, i - 1): i + 1]
        else:
            out = out[-2:]
    if len(out) > 1:
        # 「完成需求受理登记」信息量低，有别的动作时不留
        out = [x for x in out if x != "完成需求受理登记"] or out
    return out


def _next_hint(vrd: Optional[date], end: date) -> str:
    if not vrd:
        return "按里程碑持续推进"
    if vrd > end:
        return f"计划 {vrd.strftime('%m-%d')} 版本上线"
    return "正加快收口，力争尽快交付上线"


def _planned_reasons(req, vrd, dev_entered, end, overdue_days) -> List[str]:
    reasons: List[str] = []
    if vrd and end < vrd <= end + timedelta(days=7):
        reasons.append("T1")
    elif vrd and vrd <= end and (req.status or "") in ("dev", "partial_live", "live_failed"):
        # 承诺日期已过：只在已进入开发/部分上线阶段才算「下周收口」，
        # 建议中/已受理的过期日期（多为版本要求变更）不纳入，避免章节被灌满
        reasons.append("T1b")
    if (req.status or "") == "dev" and dev_entered:
        if (end - dev_entered).days > overdue_days:
            reasons.append("T2")
    if not reasons and _is_tariff(req):
        # 资费类小配置不必等超期：改配置即可上线，是下周最确定的产出
        reasons.append("T3")
    return reasons


def collect(db, start: date, end: date, overdue_days: int = OVERDUE_DAYS_DEFAULT) -> Dict[str, Any]:
    """筛选四类数据：delivered / inflight / planned / quality。

    返回结构：
      delivered [{req_id, req_name, category, system_name, clarification, go_live}]
      inflight  [{req_id, req_name, category, status, status_label, actions, dev_days, vrd, next_hint}]
      planned   [{..., reasons, vrd, dev_overdue_days, is_tariff}]
      quality   [{req_id, req_name, missing}]
      stats     {delivered, inflight, planned, quality, delivered_truncated, planned_truncated}
    """
    rows = db.query(PmwbRequirementExt).all()
    ticket_go_live, stages, events = _load_maps(db)

    delivered: List[Dict[str, Any]] = []
    inflight: List[Dict[str, Any]] = []
    planned: List[Dict[str, Any]] = []
    quality: List[Dict[str, Any]] = []

    for r in rows:
        status = r.status or ""
        if status in ("paused", "suspended") or _is_dropped(r):
            continue
        req_id = r.req_id or ""
        req_name = (r.req_name or "").strip() or req_id
        if not req_name:
            continue
        vrd = _to_date(r.version_required_date)
        dev_log = stages.get((req_id, "dev"))
        dev_entered = _to_date(dev_log.entered_at) if dev_log else None

        base = {
            "req_id": req_id,
            "req_name": req_name,
            "clarification": _clamp(r.clarification, _CLARIFICATION_PROMPT_CAP),
            "system_name": (r.system_name or "").strip(),
            "category": (r.category or "").strip(),
            "status": status,
        }

        # 权威上线日期：delivered_date 优先，回退开发工单 go_live_date
        go_live = _to_date(r.delivered_date) or ticket_go_live.get(req_id)

        if status == "closed":
            if _in_window(go_live, start, end):
                delivered.append({**base, "go_live": go_live.isoformat()})
            elif not go_live:
                # 缺日期属数据问题，不是「本周上线」——隔离提示，不进正文
                quality.append({
                    "req_id": req_id,
                    "req_name": req_name,
                    "missing": "实际上线日期（delivered_date）未填报",
                })
            continue

        # 非 closed 但已有上线日期落窗口内（如部分上线后补记），仍算本期上线
        if _in_window(go_live, start, end):
            delivered.append({**base, "go_live": go_live.isoformat()})
            continue

        if status not in R.INFLIGHT_STATUSES:
            continue

        # 在途过程进展：只收本周有实际推进动作的需求（纯编号需求名不进正文）
        actions = _summarize_actions(_inflight_actions(req_id, stages, events, start, end))
        if actions and _is_meaningful_name(req_name):
            inflight.append({
                **base,
                "status_label": _status_label(status),
                "actions": actions,
                "dev_entered_at": dev_entered.isoformat() if dev_entered else None,
                "dev_days": (end - dev_entered).days if dev_entered else None,
                "vrd": vrd.isoformat() if vrd else None,
                "next_hint": _next_hint(vrd, end),
                "is_tariff": _is_tariff(r),
            })

        reasons = _planned_reasons(r, vrd, dev_entered, end, overdue_days)
        if reasons and _is_meaningful_name(req_name):
            planned.append({
                **base,
                "status_label": _status_label(status),
                "reasons": reasons,
                "vrd": vrd.isoformat() if vrd else None,
                "dev_entered_at": dev_entered.isoformat() if dev_entered else None,
                "dev_overdue_days": (end - dev_entered).days if dev_entered else None,
                "is_tariff": _is_tariff(r),
            })

    delivered.sort(key=lambda x: x.get("go_live") or "", reverse=True)
    inflight.sort(key=lambda x: (-len(x.get("actions") or []), x.get("req_name") or ""))
    planned.sort(key=lambda x: (
        _REASON_RANK.get((x.get("reasons") or ["T3"])[0], 9),
        x.get("vrd") or "9999-12-31",
        -(x.get("dev_overdue_days") or 0),
    ))

    d_trunc = max(0, len(delivered) - R.MAX_DELIVERED)
    p_trunc = max(0, len(planned) - R.MAX_PLANNED)
    return {
        "delivered": delivered[: R.MAX_DELIVERED],
        "inflight": inflight[: R.MAX_INFLIGHT],
        "planned": planned[: R.MAX_PLANNED],
        "quality": quality,
        "stats": {
            "delivered": len(delivered),
            "inflight": len(inflight),
            "planned": len(planned),
            "quality": len(quality),
            "delivered_truncated": d_trunc,
            "planned_truncated": p_trunc,
        },
    }


# --------------------------------------------------------------------------- #
# 提示词
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = (
    "你是资深电信行业产品经理，负责输出团队「需求分析」周度成效反馈。"
    "写作要求："
    "1) 这是团队工作成效反馈：一律积极、进取的表述，突出推进与成果；"
    "严禁使用「超期、滞后、卡点、风险、延误、未完成、积压」等负面或问题性措辞；"
    "2) 只依据给出的需求数据输出，不得编造不存在的需求、功能或日期；"
    "3) 每条只写一句话，简洁概括「什么需求、做了什么、实现了什么功能」，"
    "不展开技术细节，不照抄需求澄清原文，不罗列接口/字段；"
    "4) 已上线与计划上线格式固定（不加任何中括号/书名号，不写环节名如「生产开发部署」）："
    "已上线 需求名称，实现 能力概述。"
    "计划上线 需求名称，将实现 能力概述。"
    "能力概述控制在 20~40 字，一句话说清业务能力与受益对象（如营业员、客户经理、企业客户）；"
    "5) 在途需求过程进展格式：需求名称：本周<推进动作>，<下一步>。"
    "推进动作直接采用给定动作描述，进展与下一步合计不超过 50 字；"
    "6) 澄清内容为空时依据需求名称概括，概括不了写「相关业务能力」；"
    "7) 「纳入依据」仅用于理解需求为何列入下周计划，不得写进正文；"
    "8) 每个章节内按「需求分类」归组陈述（同分类相邻，未分类归入「其他」），"
    "保持给定顺序；输出 Markdown，仅包含指定章节，不输出前言、解释或总结。"
)


def _prompt_actions(it: Dict[str, Any]) -> str:
    acts = it.get("actions") or []
    return "、".join(acts) if acts else "持续推进"


def build_prompt(data: Dict[str, Any], start: date, end: date, overdue_days: int = OVERDUE_DAYS_DEFAULT):
    """构造需求分析专题的 system/user 提示词（三章）。"""
    delivered = _sorted_by_category(data.get("delivered") or [])
    inflight = data.get("inflight") or []
    planned = _sorted_by_category(data.get("planned") or [])
    stats = data.get("stats") or {}

    lines: List[str] = [
        f"分析周期：{start.isoformat()} ~ {end.isoformat()}（本周自然周，需求分析专题）。",
        "本报告为团队工作成效反馈，请积极表述。",
        "",
        f"## 一、本周已上线需求（{stats.get('delivered', len(delivered))} 项，分类分布：{_category_stats(delivered) or '无'}）",
    ]
    if delivered:
        for it in delivered:
            lines.append(
                f"- 需求名称：{it['req_name']}；需求分类：{it.get('category') or '未分类'}；"
                f"上线日期：{it.get('go_live', '')}；"
                f"澄清内容：{_clamp(it.get('clarification'), _PROMPT_CLARIFY_LONG) or '（无）'}"
            )
    else:
        lines.append("（本周无版本上线）")

    lines += ["", f"## 二、在途需求过程进展（{len(inflight)} 项，本周有实际推进）"]
    if inflight:
        for it in inflight:
            lines.append(
                f"- 需求名称：{it['req_name']}；本周推进动作：{_prompt_actions(it)}；"
                f"当前状态：{it.get('status_label') or ''}；下一步：{it.get('next_hint') or ''}"
                f"{'；备注：新增资费类配置' if it.get('is_tariff') else ''}；"
                f"澄清内容：{_clamp(it.get('clarification'), _PROMPT_CLARIFY_SHORT) or '（无）'}"
            )
    else:
        lines.append("（本周在途需求按计划持续推进，无新增环节记录）")

    # 仅用于让模型理解纳入原因，措辞保持积极；system prompt 已要求不写进正文
    reason_desc = {
        "T1": "期望上线日期在下周",
        "T1b": "已进入交付冲刺阶段、本周集中收口",
        "T2": "开发推进已达 {d} 天、临近交付".format(d=overdue_days),
        "T3": "新增资费类快速配置",
    }
    lines += ["", f"## 三、下周计划上线需求（{stats.get('planned', len(planned))} 项，分类分布：{_category_stats(planned) or '无'}）"]
    if planned:
        for it in planned:
            rs = "、".join(reason_desc.get(x, x) for x in (it.get("reasons") or []))
            lines.append(
                f"- 需求名称：{it['req_name']}；需求分类：{it.get('category') or '未分类'}；"
                f"纳入依据：{rs}；"
                f"期望上线日期：{it.get('vrd') or '未标注'}；"
                f"澄清内容：{_clamp(it.get('clarification'), _PROMPT_CLARIFY_LONG) or '（无）'}"
            )
    else:
        lines.append("（下周暂无版本要求内的需求，按计划推进在途需求）")

    if stats.get("planned_truncated"):
        lines.append(f"（另有 {stats['planned_truncated']} 项需求同步推进，本报告未逐条列出）")
    if data.get("quality"):
        lines.append("")
        lines.append("## 数据质量提示（不进正文，仅供内部补录，禁写入报告章节）")
        for it in data["quality"]:
            lines.append(f"- {it['req_name']}：{it['missing']}")

    lines += [
        "",
        "请输出：",
        f"# 需求分析（本周：{start.isoformat()} ~ {end.isoformat()}）",
        "",
        "> 一句话概述本期团队需求推进成效（30 字内，积极表述）。",
        "",
        "## 一、本周已上线需求",
        "- （每条格式：已上线 需求名称，实现 能力概述。不加中括号/书名号，不写环节名，能力概述 20~40 字。）",
        "",
        "## 二、在途需求过程进展",
        "- （每条格式：需求名称：本周<推进动作>，<下一步>。合计不超过 50 字。）",
        "",
        "## 三、下周计划上线需求",
        "- （每条格式：计划上线 需求名称，将实现 能力概述。不加中括号/书名号，不写环节名。）",
        "空章节写「本期暂无」。每条一行，按分类归组排序（同分类相邻，未分类殿后）。",
    ]
    return SYSTEM_PROMPT, "\n".join(lines)


# --------------------------------------------------------------------------- #
# 规则降级（LLM 不可用时，内容仍可用）
# --------------------------------------------------------------------------- #
def render_rule(data: Dict[str, Any], start: date, end: date, overdue_days: int = OVERDUE_DAYS_DEFAULT) -> str:
    """规则降级版：能力=澄清内容首句截取，措辞与 LLM 版同口径（正向、控字数）。"""
    delivered = _sorted_by_category(data.get("delivered") or [])
    inflight = data.get("inflight") or []
    planned = _sorted_by_category(data.get("planned") or [])
    stats = data.get("stats") or {}
    total = stats.get("delivered", len(delivered)) + stats.get("inflight", len(inflight)) + stats.get("planned", len(planned))

    lines = [
        f"# 需求分析（本周：{start.isoformat()} ~ {end.isoformat()}）",
        "",
        f"> 本期团队推进需求 {total} 项，已上线 {stats.get('delivered', len(delivered))} 项、"
        f"在途推进 {stats.get('inflight', len(inflight))} 项、"
        f"下周计划交付 {stats.get('planned', len(planned))} 项。",
        "",
        "> 降级说明：大模型不可用，能力概括为规则截取（澄清内容首句），非 AI 高度概括。",
        "",
        f"## 一、本周已上线需求（{stats.get('delivered', len(delivered))} 项）",
    ]
    if delivered:
        for it in delivered:
            cap = _capability(it.get("clarification")) or "相关业务能力"
            lines.append(f"- 已上线 {it['req_name']}，实现 {cap}。")
    else:
        lines.append("本期暂无版本上线，团队集中推进在途需求与方案准备。")

    lines += ["", f"## 二、在途需求过程进展（{len(inflight)} 项）"]
    if inflight:
        for it in inflight:
            acts = "、".join(it.get("actions") or []) or "持续推进"
            lines.append(f"- {it['req_name']}：本周{acts}，{it.get('next_hint') or '按里程碑持续推进'}。")
    else:
        lines.append("本周在途需求按计划持续推进，无新增环节记录。")

    lines += ["", f"## 三、下周计划上线需求（{stats.get('planned', len(planned))} 项）"]
    if planned:
        for it in planned:
            cap = _capability(it.get("clarification")) or "相关业务能力"
            lines.append(f"- 计划上线 {it['req_name']}，将实现 {cap}。")
    else:
        lines.append("下周暂无版本要求内的新增需求，团队按计划推进在途需求。")

    if stats.get("planned_truncated"):
        lines += ["", f"> 另有 {stats['planned_truncated']} 项需求同步推进，未逐条列出。"]
    if data.get("quality"):
        lines += [
            "",
            f"> 数据质量提示：{len(data['quality'])} 项已上线需求缺实际上线日期，未纳入本期统计，"
            "请到需求与交付模块补录（本提示不进正文）。",
        ]
    return "\n".join(lines) + "\n"
