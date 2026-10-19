"""需求开发超期专题分析（AI总结固化专题，2026-10-19）。

口径（老大拍板，与既有模块同源，禁另造第二份算法）：
1. **对象**：跟踪状态＝「开发中」(`pmwb_requirement_ext.status='dev'`)，且**尚未上线**。
   未上线判定与 AI 周报/需求分析同源：`delivered_date` 与开发工单 `go_live_date` 均为空。
2. **计时起点**：`pmwb_requirement_stage_log` 中 `stage='dev'` 的 `entered_at`
   （进入「启动开发」环节日期），与 `workload_analysis._dev_months`、
   `requirement_analysis.collect` 同源。
3. **超期**：基准日与启动开发日的自然日差 **> 阈值**（默认 25 天，生成时可手工修改）。
4. **渲染纪律**：明细表/分布/统计**全部确定性渲染**，绝不由 LLM 生成；
   LLM 只写「四、研判与建议」章节，不可用时用规则文案兜底 —— 保证数据永不失真。
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from db.models import (
    PmwbDevTicket,
    PmwbReqVendorDev,
    PmwbRequirementEvaluation,
    PmwbRequirementExt,
    PmwbRequirementStageLog,
)

logger = logging.getLogger(__name__)

DEV_STAGE = "dev"
DEV_STATUS = "dev"
OVERDUE_DAYS_DEFAULT = 25

_OWNER_SPLIT = re.compile(r"[,，;；、]+")
_SYS_SPLIT = re.compile(r"[,，、;；]+")

# 厂家开发状态中文（展示用，仅本专题表格）
_VENDOR_STATUS_LABELS = {
    "pending": "待开发",
    "developing": "开发中",
    "live": "已上线",
    "completed": "已完成",
}

# 风险分级规则（写入报告脚注，可核查）
RISK_HIGHEST, RISK_HIGH, RISK_MID = "极高", "高", "中"


def _to_date(v) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return None


def _num(v) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _fmt_days(n: Optional[int]) -> str:
    return f"{n} 天" if n is not None else "—"


def _risk_of(priority: str, days: int, version_overdue: Optional[int]) -> str:
    """风险分级：极高＝P0/或 P1 且版本逾期/或滞留 >60 天；高＝>45 天或版本逾期；其余中。"""
    pri = (priority or "").upper()
    if pri == "P0" or (pri == "P1" and version_overdue) or days > 60:
        return RISK_HIGHEST
    if days > 45 or version_overdue:
        return RISK_HIGH
    return RISK_MID


def _md_table(headers: List[str], rows: List[List[str]]) -> str:
    if not rows:
        return "（本期无数据）"
    lines = ["| " + " | ".join(headers) + " |",
             "| " + " | ".join(["---"] * len(headers)) + " |"]
    for r in rows:
        lines.append("| " + " | ".join(str(c).replace("|", "／") for c in r) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 数据采集
# ---------------------------------------------------------------------------
def collect(db, as_of: date, overdue_days: int = OVERDUE_DAYS_DEFAULT) -> Dict[str, Any]:
    """采集「开发中且未上线」需求，筛出超期对象并附多维统计。"""
    try:
        threshold = int(overdue_days)
    except (TypeError, ValueError):
        threshold = OVERDUE_DAYS_DEFAULT
    if threshold < 1:
        threshold = OVERDUE_DAYS_DEFAULT

    exts = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.status == DEV_STATUS).all()
    req_ids = [e.req_id for e in exts if e.req_id]

    # 启动开发进入时间（uk_req_stage 唯一约束 → 一需求一条）
    dev_map: Dict[str, Any] = {}
    if req_ids:
        for log in (
            db.query(PmwbRequirementStageLog)
            .filter(
                PmwbRequirementStageLog.stage == DEV_STAGE,
                PmwbRequirementStageLog.req_id.in_(req_ids),
            )
            .all()
        ):
            dev_map[log.req_id] = log

    # 开发工单上线日期（取最晚，与 requirement_analysis 同口径）
    go_live_map: Dict[str, date] = {}
    if req_ids:
        for t in db.query(PmwbDevTicket).filter(PmwbDevTicket.req_id.in_(req_ids)).all():
            d = _to_date(t.go_live_date)
            if d and (t.req_id not in go_live_map or d > go_live_map[t.req_id]):
                go_live_map[t.req_id] = d

    # 团队评估：工作量（review 优先）+ SA/系统集合
    eval_map: Dict[str, Dict[str, Any]] = {}
    vendor_map: Dict[str, List[Dict[str, str]]] = {}
    ticket_map: Dict[str, List[str]] = {}
    if req_ids:
        for ev in (
            db.query(PmwbRequirementEvaluation)
            .filter(PmwbRequirementEvaluation.req_id.in_(req_ids))
            .all()
        ):
            b = eval_map.setdefault(ev.req_id, {"workload": 0.0, "sa": set(), "systems": set()})
            rw = ev.review_workload
            wl = rw if rw is not None else ev.workload
            b["workload"] += _num(wl)
            for n in _OWNER_SPLIT.split(ev.sa_name or ""):
                if n.strip():
                    b["sa"].add(n.strip())
            if (ev.system_name or "").strip():
                b["systems"].add(ev.system_name.strip())
        for vd in (
            db.query(PmwbReqVendorDev).filter(PmwbReqVendorDev.req_id.in_(req_ids)).all()
        ):
            vendor_map.setdefault(vd.req_id, []).append({
                "system_name": vd.system_name or "",
                "dev_status": vd.dev_status or "",
                "dev_ticket_no": vd.dev_ticket_no or "",
            })
        for t in db.query(PmwbDevTicket).filter(PmwbDevTicket.req_id.in_(req_ids)).all():
            if t.ticket_no:
                ticket_map.setdefault(t.req_id, []).append(t.ticket_no)

    items: List[Dict[str, Any]] = []
    total_workload = 0.0
    already_live = 0
    no_dev_date: List[str] = []

    for e in exts:
        rid = e.req_id or ""
        ev = eval_map.get(rid) or {"workload": 0.0, "sa": set(), "systems": set()}
        total_workload += ev["workload"]

        # 已上线（权威上线日口径）→ 不进入超期池
        go_live = _to_date(e.delivered_date) or go_live_map.get(rid)
        if go_live:
            already_live += 1
            continue

        log = dev_map.get(rid)
        entered = _to_date(log.entered_at) if log else None
        if not entered:
            no_dev_date.append(rid)
            continue
        days = (as_of - entered).days
        if days <= threshold:
            continue

        vrd = _to_date(e.version_required_date)
        ver_overdue = (as_of - vrd).days if (vrd and vrd < as_of) else None

        items.append({
            "req_id": rid,
            "req_name": (e.req_name or "").strip() or rid,
            "system_name": (e.system_name or "").strip() or "—",
            "sa_name": (e.sa_name or "").strip() or "—",
            "priority": (e.priority or "").strip() or "未设",
            "dev_entered": entered.isoformat(),
            "days": days,
            "dev_source": (log.source or "auto") if log else "auto",
            "backfill": bool(log and (log.source or "") == "backfill"),
            "version_required_date": vrd.isoformat() if vrd else "",
            "version_overdue_days": ver_overdue,
            "vendor_dev": vendor_map.get(rid, []),
            "tickets": ticket_map.get(rid, []),
            "workload": round(ev["workload"], 1),
            "risk": _risk_of(e.priority or "", days, ver_overdue),
        })

    items.sort(key=lambda x: (-x["days"], x["req_id"]))
    overdue_workload = round(sum(i["workload"] for i in items), 1)

    # ---- 多维分布（多人共担按人计次，故合计可大于条数） ----
    def _dist(key: str) -> List[Dict[str, Any]]:
        cnt: Dict[str, int] = {}
        for it in items:
            if key == "owner":
                names = [n.strip() for n in _OWNER_SPLIT.split(it["sa_name"]) if n.strip()]
            elif key == "system":
                names = [n.strip() for n in _SYS_SPLIT.split(it["system_name"]) if n.strip()]
            elif key == "priority":
                names = [it["priority"]]
            else:  # month
                names = [it["dev_entered"][:7]]
            for n in names:
                cnt[n] = cnt.get(n, 0) + 1
        return [{"name": k, "count": v} for k, v in sorted(cnt.items(), key=lambda x: (-x[1], x[0]))]

    buckets = [
        {"name": f"27–30 天", "count": sum(1 for i in items if 27 <= i["days"] <= 30)},
        {"name": f"31–45 天", "count": sum(1 for i in items if 31 <= i["days"] <= 45)},
        {"name": f"46–60 天", "count": sum(1 for i in items if 46 <= i["days"] <= 60)},
        {"name": f"> 60 天", "count": sum(1 for i in items if i["days"] > 60)},
    ]

    return {
        "as_of": as_of.isoformat(),
        "overdue_days": threshold,
        "total_dev": len(exts),
        "already_live": already_live,
        "no_dev_date": no_dev_date,
        "overdue_count": len(items),
        "ratio": round(len(items) / len(exts) * 100, 1) if exts else 0.0,
        "avg_days": round(sum(i["days"] for i in items) / len(items), 1) if items else 0.0,
        "max_days": max((i["days"] for i in items), default=0),
        "overdue_workload": overdue_workload,
        "total_workload": round(total_workload, 1),
        "workload_ratio": round(overdue_workload / total_workload * 100, 1) if total_workload else 0.0,
        "version_overdue_count": sum(1 for i in items if i["version_overdue_days"] is not None),
        "backfill_count": sum(1 for i in items if i["backfill"]),
        "vendor_tracked_count": sum(1 for i in items if i["vendor_dev"]),
        "ticket_linked_count": sum(1 for i in items if i["tickets"]),
        "items": items,
        "by_system": _dist("system"),
        "by_owner": _dist("owner"),
        "by_priority": _dist("priority"),
        "by_month": _dist("month"),
        "buckets": buckets,
    }


# ---------------------------------------------------------------------------
# 确定性命中渲染（表格/分布/统计）
# ---------------------------------------------------------------------------
def _vendor_cell(item: Dict[str, Any]) -> str:
    vd = item.get("vendor_dev") or []
    if not vd:
        return "未登记"
    parts = []
    for v in vd:
        st = _VENDOR_STATUS_LABELS.get(v.get("dev_status") or "", v.get("dev_status") or "—")
        parts.append(f"{v.get('system_name') or '—'} {st}")
    return "；".join(parts)


def _version_cell(item: Dict[str, Any]) -> str:
    d = item.get("version_required_date") or ""
    if not d:
        return "—"
    od = item.get("version_overdue_days")
    return f"{d}（逾期 {od} 天）" if od else d


def _table_block(data: Dict[str, Any]) -> str:
    rows = []
    for idx, it in enumerate(data["items"], 1):
        name = it["req_name"]
        if it["backfill"]:
            name += "（启动开发日期为历史回填）"
        rows.append([
            str(idx),
            it["req_id"],
            name,
            it["system_name"],
            it["sa_name"],
            it["priority"],
            it["dev_entered"],
            f"**{it['days']}**",
            _version_cell(it),
            _vendor_cell(it),
            it["risk"],
        ])
    return _md_table(
        ["#", "需求编号", "需求名称", "目标系统", "SA 负责人", "优先级",
         "启动开发", "已开发", "版本要求", "厂家开发状态", "风险"],
        rows,
    )


def _dist_block(data: Dict[str, Any]) -> str:
    def line(name: str, arr: List[Dict[str, Any]], unit: str = "条") -> str:
        if not arr:
            return f"- **{name}**：无"
        return f"- **{name}**：" + "、".join(f"{x['name']} {x['count']} {unit}" for x in arr)

    lines = [
        line("按目标系统", data["by_system"]),
        line("按 SA 负责人（共担按人计次）", data["by_owner"]),
        line("按优先级", data["by_priority"]),
        line("按进入「启动开发」月份", data["by_month"]),
        "- **按滞留时长**：" + "、".join(f"{b['name']} {b['count']} 条" for b in data["buckets"]),
    ]
    return "\n".join(lines)


def render_header(data: Dict[str, Any]) -> str:
    """第一~三章：概况 / 明细 / 分布（纯确定性，禁 LLM）。"""
    d = data
    lines = [
        f"# 需求开发超期专题分析（统计基准日 {d['as_of']}）",
        "",
        f"> 口径：对象＝跟踪状态「开发中」且尚未上线；计时起点＝进入「启动开发」环节日期；"
        f"超期阈值＝**超过 {d['overdue_days']} 天**（生成时可手工修改）；"
        f"已填写实际上线日或开发工单上线日的需求不计入。",
        "",
        "## 一、总体概况",
        "",
        f"- 当前「开发中」需求 **{d['total_dev']} 条**，其中超 {d['overdue_days']} 天未上线 **{d['overdue_count']} 条**，"
        f"占比 **{d['ratio']}%**。",
        f"- 超期对象平均已开发 **{d['avg_days']} 天**，最长 **{d['max_days']} 天**。",
        f"- 超期对象评估工作量合计 **{d['overdue_workload']} 人天**，占开发中总量 {d['total_workload']} 人天的 "
        f"{d['workload_ratio']}%。",
        f"- 已明确版本要求日期且已逾期 **{d['version_overdue_count']} 条**；"
        f"已登记厂家开发状态 **{d['vendor_tracked_count']} 条**；关联开发工单号 **{d['ticket_linked_count']} 条**。",
    ]
    if d["already_live"]:
        lines.append(f"- 另有 {d['already_live']} 条虽为「开发中」但已填报上线日期，按口径不计入。")
    if d["no_dev_date"]:
        lines.append(
            f"- ⚠ 有 {len(d['no_dev_date'])} 条开发中需求缺「启动开发」时间记录，无法计时，"
            f"需补录：{'、'.join(d['no_dev_date'][:6])}{'…' if len(d['no_dev_date']) > 6 else ''}。"
        )

    lines += ["", f"## 二、超期需求明细（{d['overdue_count']} 条，按已开发天数倒序）", ""]
    if d["items"]:
        lines.append(_table_block(d))
    else:
        lines.append(f"本期无超过 {d['overdue_days']} 天仍未上线的开发中需求。")

    lines += ["", "## 三、分布画像", "", _dist_block(d)]
    return "\n".join(lines)


def render_footer(data: Dict[str, Any]) -> str:
    """第五章：口径与数据质量说明。"""
    d = data
    lines = [
        "## 五、口径与数据质量说明",
        "",
        f"- **状态口径**：取 `pmwb_requirement_ext.status='dev'`（开发中），共 {d['total_dev']} 条；"
        "暂停、已关闭、评审中、待排期不在本次统计内。",
        "- **计时起点**：`pmwb_requirement_stage_log` 中 `stage='dev'` 的 `entered_at`，"
        "与工作量分析、需求分析专题同源。",
        f"- **天数算法**：{d['as_of']} 减启动开发日期，自然日差，阈值严格大于 {d['overdue_days']} 天。",
        "- **风险分级**：极高＝P0 / 或 P1 且版本已逾期 / 或滞留超 60 天；"
        "高＝滞留超 45 天或版本已逾期；其余为中。",
        "- **回填标记**：`source='backfill'` 的启动开发日期为历史回填，可信度低于自动记录，已在明细中注明。",
        "- **工作量**：按 `review_workload` 优先、否则 `workload` 汇总，与工作量分析模块同源。",
    ]
    if d["backfill_count"]:
        lines.append(f"- 本期超期对象中 **{d['backfill_count']} 条**启动开发日期为历史回填，"
                     "判断真实滞留时长时需与负责人确认。")
    if d["vendor_tracked_count"] < d["overdue_count"]:
        lines.append(
            f"- **过程数据缺口**：超期对象中仅 {d['vendor_tracked_count']} 条登记厂家开发状态、"
            f"{d['ticket_linked_count']} 条关联开发工单号，"
            "目前无法区分「真实卡点」与「已完工未收口」，建议补齐后再做二次核验。"
        )
    return "\n".join(lines)


def render_markdown(data: Dict[str, Any], insight: str) -> str:
    """装配完整报告：确定性 1–3 章 + 研判建议 + 确定性口径章。"""
    body = render_header(data)
    insight = (insight or "").strip()
    if not insight:
        insight = render_rule_insight(data)
    return (
        body
        + "\n\n## 四、研判与建议\n\n"
        + insight
        + "\n\n"
        + render_footer(data)
        + "\n"
    )


# ---------------------------------------------------------------------------
# 研判与建议：LLM 生成，规则兜底
# ---------------------------------------------------------------------------
INSIGHT_SYSTEM_PROMPT = (
    "你是资深电信行业产品经理助理，负责为「需求开发超期」专题写研判与建议。"
    "要求：1) 严格依据给定统计数据，不得编造需求名称、人员、数字；"
    "2) 输出 3~5 条 Markdown 无序列表，每条格式为「- **小标题**：1~2 句说明」；"
    "3) 聚焦结构性原因、最该优先处置的对象、可落地的机制改进，不要复述明细表；"
    "4) 不要输出任何章节标题、表格或额外解释。"
)


def build_prompt(data: Dict[str, Any]) -> tuple[str, str]:
    """构造研判章节的提示词（只喂聚合数据，控制 token）。"""
    d = data
    tops = d["items"][:6]
    lines = [
        f"统计基准日：{d['as_of']}；超期阈值：超过 {d['overdue_days']} 天未上线。",
        f"开发中总数 {d['total_dev']} 条，超期 {d['overdue_count']} 条（{d['ratio']}%），"
        f"平均 {d['avg_days']} 天，最长 {d['max_days']} 天。",
        f"超期工作量 {d['overdue_workload']} 人天 / 开发中总量 {d['total_workload']} 人天。",
        f"版本已逾期 {d['version_overdue_count']} 条；登记厂家开发状态 {d['vendor_tracked_count']} 条；"
        f"关联开发工单号 {d['ticket_linked_count']} 条；启动开发日期为回填 {d['backfill_count']} 条。",
        "",
        "分布：",
        _dist_block(d),
        "",
        "最长滞留前 6 条：",
    ]
    for it in tops:
        ver = f"，版本要求 {it['version_required_date']}" if it["version_required_date"] else ""
        ver += f"（逾期 {it['version_overdue_days']} 天）" if it["version_overdue_days"] else ""
        lines.append(
            f"- {it['req_name']}｜{it['system_name']}｜{it['priority']}｜{it['sa_name']}｜"
            f"已开发 {it['days']} 天｜风险 {it['risk']}{ver}"
        )
    lines += ["", "请输出研判与建议。"]
    return INSIGHT_SYSTEM_PROMPT, "\n".join(lines)


def render_rule_insight(data: Dict[str, Any]) -> str:
    """规则兜底：大模型不可用时仍给出可用的三条判断。"""
    d = data
    items = d["items"]
    if not items:
        return f"- **本期无超期对象**：当前「开发中」需求均未超过 {d['overdue_days']} 天，建议保持现有节奏。"

    top = items[0]
    ver_over = [i for i in items if i["version_overdue_days"]]
    pri0 = [i for i in items if (i["priority"] or "").upper() == "P0"]
    sys_top = d["by_system"][0] if d["by_system"] else None
    own_top = d["by_owner"][0] if d["by_owner"] else None

    out = [
        f"- **最需先动的一条**：{top['req_name']}（{top['system_name']}，{top['priority']}，"
        f"已开发 {top['days']} 天），建议本周内明确上线承诺日期或正式走版本调整。",
    ]
    if pri0 or ver_over:
        names = "、".join(i["req_name"] for i in (pri0 + ver_over)[:3])
        out.append(f"- **版本已逾期需闭环**：{len(ver_over)} 条需求已过版本要求日期"
                   + (f"，其中 P0 {len(pri0)} 条" if pri0 else "")
                   + f"（{names}），需按周跟踪到上线。")
    if sys_top:
        out.append(f"- **系统瓶颈**：{sys_top['name']} 涉及 {sys_top['count']} 条超期"
                   + (f"，责任侧 {own_top['name']} 涉及 {own_top['count']} 条" if own_top else "")
                   + "，建议按系统拉通一次专项对齐。")
    if d["vendor_tracked_count"] < d["overdue_count"]:
        out.append(f"- **过程数据补录**：{d['overdue_count']} 条超期对象中仅 {d['vendor_tracked_count']} 条登记厂家开发状态、"
                   f"{d['ticket_linked_count']} 条关联开发工单号，建议补齐后再评估真实卡点。")
    return "\n".join(out)
