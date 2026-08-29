"""工作总结数据采集器 —— 从各业务表汇总报告期内的工作数据。

设计要点（深度分析）：
- 需求按生命周期分桶（新增/评估/启动开发/交付/进行中）+ PO 级交付风险。
- 运营按子类聚合，单列高敏 P0/P1 工单与处理人时效。
- 会议提炼价值与行动项完成率。
- 个人待办独立统计完成率与超期。
- 知识中心统计维护情况。
各子采集均包 try/except，单模块异常不影响整体生成。
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from db.models import (
    PmwbActiveOptimization,
    PmwbDevTicket,
    PmwbKeyWork,
    PmwbKnowledgeItem,
    PmwbMeeting,
    PmwbMeetingAction,
    PmwbOperationIssue,
    PmwbRequirementEvaluation,
    PmwbRequirementExt,
    PmwbTodo,
)
from services.report_dict import (
    tr,
    tr_keys,
    REQUIREMENT_STATUS,
    REQUIREMENT_PRIORITY,
    DEV_TICKET_STATUS,
    OP_ISSUE_CATEGORY,
    OP_ISSUE_STATUS,
    IMPACT_LEVEL,
    TODO_STATUS,
    TODO_CATEGORY,
    MEETING_ACTION_STATUS,
    KW_CATEGORY,
    KW_STATUS,
    KW_PRIORITY,
)

logger = logging.getLogger(__name__)


def _g(obj, attr, default=None):
    return getattr(obj, attr, default)


def _date_of(value) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _in_range(d: Optional[date], start: date, end: date) -> bool:
    if d is None:
        return False
    return start <= d <= end


def _iso_week(d: Optional[date]) -> str:
    """返回 ISO 周次标签，如 2026-W34。"""
    if d is None:
        return ""
    return d.strftime("%G-W%V")


def _is_in_scope(obj, start: date, end: date, date_fields=("updated_at", "created_at"),
                 exclude_completed: bool = True) -> bool:
    """判断对象是否在时间范围内发生过状态/数据更新。

    以 updated_at 为主判定，辅以 created_at 等关键事件日期。
    若 exclude_completed=True 且对象已处于完结状态（completed/closed/done），
    且完结日期早于周期起点、周期内无新更新，则排除（避免旧已完结任务污染报告）。
    """
    for f in date_fields:
        d = _date_of(_g(obj, f))
        if _in_range(d, start, end):
            return True
    # 已完结且无周期内变更：排除
    if exclude_completed:
        st = str(_g(obj, "status") or "").lower()
        if st in ("completed", "closed", "done", "cancelled"):
            # 查找完结日期字段
            completed_at = _date_of(_g(obj, "completed_at") or _g(obj, "closed_at"))
            if completed_at and completed_at < start:
                return False
    return False


def _latest_related_date(parent_obj, related_iter, fields=("updated_at", "created_at")) -> Optional[date]:
    """从关联子对象中找出最近的日期（用于判定父对象是否因关联更新而纳入范围）。"""
    latest: Optional[date] = None
    for child in related_iter or []:
        for f in fields:
            d = _date_of(_g(child, f))
            if d and (latest is None or d > latest):
                latest = d
    return latest


class ReportDataCollector:
    def __init__(self, db):
        self.db = db

    def collect(self, date_start: date, date_end: date) -> Dict[str, Any]:
        return {
            "date_start": date_start.isoformat(),
            "date_end": date_end.isoformat(),
            "requirement": self._collect_requirement(date_start, date_end),
            "operation_issue": self._collect_operation_issue(date_start, date_end),
            "dev_ticket": self._collect_dev_ticket(date_start, date_end),
            "meeting": self._collect_meeting(date_start, date_end),
            "meeting_action": self._collect_meeting_action(date_start, date_end),
            "todo": self._collect_todo(date_start, date_end),
            "knowledge": self._collect_knowledge(date_start, date_end),
            "key_work": self._collect_key_work(date_start, date_end),
            "active_optimization": self._collect_active_optimization(date_start, date_end),
        }

    # ---- 需求与交付 ----
    def _collect_requirement(self, start, end):
        try:
            rows = self.db.query(PmwbRequirementExt).all()
        except Exception as e:  # noqa: BLE001
            logger.warning("采集需求失败: %s", e)
            return {"items": [], "buckets": {}, "po_risk": []}

        buckets = {"added": [], "evaluated": [], "dev_start": [], "delivered": [], "ongoing": []}
        delivered_items: List[Dict[str, Any]] = []
        po_risk: List[Dict[str, Any]] = []
        items: List[Dict[str, Any]] = []
        for r in rows:
            req_id = _g(r, "req_id") or ""
            req_name = _g(r, "req_name") or req_id
            status = _g(r, "status") or "proposed"
            priority = _g(r, "priority") or "P2"
            created = _date_of(_g(r, "created_at"))
            updated = _date_of(_g(r, "updated_at"))

            tickets = self.db.query(PmwbDevTicket).filter(PmwbDevTicket.req_id == req_id).all()
            ticket_go_live = None
            for t in tickets:
                d = _date_of(_g(t, "go_live_date"))
                if d and (ticket_go_live is None or d > ticket_go_live):
                    ticket_go_live = d
            evals = self.db.query(PmwbRequirementEvaluation).filter(
                PmwbRequirementEvaluation.req_id == req_id
            ).all()
            workload = sum(float(_g(e, "workload") or 0) for e in evals)
            risk_notes = "; ".join(str(_g(t, "risk_note") or "") for t in tickets if _g(t, "risk_note"))

            # 权威上线日期：需求表 delivered_date（用户在「已上线」时手工填报的实际上线日期）优先，
            # 回退开发工单 go_live_date（多工单取最晚）。delivered_date 是 AI 周报上线判断的事实依据。
            req_delivered = _date_of(_g(r, "delivered_date"))
            go_live = req_delivered or ticket_go_live

            # 范围判定：本期是否发生过状态/数据更新；已完成需求（delivered_date 在周期前）排除
            in_scope = (
                _is_in_scope(r, start, end)
                or _in_range(go_live, start, end)
                or _in_range(req_delivered, start, end)
                or any(_is_in_scope(e, start, end) for e in evals)
                or any(_is_in_scope(t, start, end) for t in tickets)
            )
            if not in_scope:
                continue

            item = {
                "req_id": req_id,
                "req_name": req_name,
                "status": status,
                "priority": priority,
                "background": (_g(r, "background") or "")[:200],
                "description": (_g(r, "description") or "")[:200],
                "clarification": (_g(r, "clarification") or "")[:200],
                "system_name": _g(r, "system_name") or "",
                "sa_name": _g(r, "sa_name") or "",
                "go_live": go_live.isoformat() if go_live else "",
                "delivered_date": req_delivered.isoformat() if req_delivered else "",
                "workload": workload,
                "dev_status": [tr(DEV_TICKET_STATUS, _g(t, "status")) for t in tickets],
            }

            # 本期新增/评估/启动开发/交付/进行中分桶
            if _in_range(created, start, end):
                buckets["added"].append(req_name)
            if any(_in_range(_date_of(_g(e, "created_at")), start, end) for e in evals):
                buckets["evaluated"].append(req_name)
            if any(
                _in_range(_date_of(_g(t, "created_at")), start, end)
                or _in_range(_date_of(_g(t, "design_reviewed_date")), start, end)
                for t in tickets
            ):
                buckets["dev_start"].append(req_name)
            if go_live and _in_range(go_live, start, end):
                buckets["delivered"].append(req_name)
                delivered_items.append(item)
            if status != "closed":
                buckets["ongoing"].append(req_name)

            is_high = ("P0" in str(priority)) or ("集团需求" in str(priority)) or ("紧急需求" in str(priority))
            dev_high = any((_g(t, "priority") == "P0") for t in tickets)
            if (is_high or dev_high) and status != "closed":
                po_risk.append({
                    "req_name": req_name,
                    "priority": tr(REQUIREMENT_PRIORITY, priority),
                    "status": tr(REQUIREMENT_STATUS, status),
                    "sa_name": _g(r, "sa_name") or "",
                    "go_live": go_live.isoformat() if go_live else "",
                    "risk_note": risk_notes,
                })

            items.append(item)
        return {"items": items, "buckets": buckets, "delivered_items": delivered_items, "po_risk": po_risk}

    # ---- 运营支撑 ----
    def _collect_operation_issue(self, start, end):
        try:
            rows = self.db.query(PmwbOperationIssue).all()
        except Exception as e:  # noqa: BLE001
            logger.warning("采集运营工单失败: %s", e)
            return {"items": [], "by_category": {}, "by_status": {}, "by_impact": {}, "by_handler": {}, "high_sensitivity": []}

        by_category = defaultdict(int)
        by_status = defaultdict(int)
        by_impact = defaultdict(int)
        by_handler = defaultdict(lambda: {"total": 0, "done": 0, "overdue": 0})
        high: List[Dict[str, Any]] = []
        items: List[Dict[str, Any]] = []
        cross_period: List[Dict[str, Any]] = []
        for r in rows:
            cat = _g(r, "category") or "other"
            st = _g(r, "status") or "pending"
            impact = _g(r, "impact_level") or "P2"
            handler = _g(r, "handler") or ""
            handlers = [h.strip() for h in str(handler).split(",") if h.strip()]
            disc = _date_of(_g(r, "discovery_date")) or _date_of(_g(r, "created_at"))
            resolve = _date_of(_g(r, "resolve_date"))
            is_overdue = _g(r, "is_overdue") or 0

            # 范围判定：基于更新时间戳或发现/解决日期；已完成且周期前已解决的工单排除
            in_scope = (
                _is_in_scope(r, start, end, ("updated_at", "created_at"), exclude_completed=True)
                or _in_range(disc, start, end)
                or _in_range(resolve, start, end)
            )
            # 跨期跟踪：本周期前已存在且仍处理中的工单
            is_cross_period = (
                not in_scope
                and disc and disc < start
                and st not in ("resolved", "closed", "verify", "completed", "done")
            )
            if not in_scope and not is_cross_period:
                continue

            by_category[cat] += 1
            by_status[st] += 1
            by_impact[impact] += 1
            for h in handlers:
                by_handler[h]["total"] += 1
                if st in ("resolved", "closed", "verify"):
                    by_handler[h]["done"] += 1
                if is_overdue:
                    by_handler[h]["overdue"] += 1
            if impact in ("P0", "P1"):
                high.append({
                    "issue_no": _g(r, "issue_no"),
                    "title": _g(r, "title"),
                    "category": tr(OP_ISSUE_CATEGORY, cat),
                    "status": tr(OP_ISSUE_STATUS, st),
                    "handler": handler,
                    "impact": tr(IMPACT_LEVEL, impact),
                    "cross_period": is_cross_period,
                })
            item = {
                "issue_no": _g(r, "issue_no"),
                "title": _g(r, "title"),
                "category": tr(OP_ISSUE_CATEGORY, cat),
                "status": tr(OP_ISSUE_STATUS, st),
                "impact": tr(IMPACT_LEVEL, impact),
                "handler": handler,
            }
            if is_cross_period:
                item["cross_period"] = True
                cross_period.append(item)
            else:
                items.append(item)
        return {
            "items": items,
            "by_category": tr_keys(OP_ISSUE_CATEGORY, by_category),
            "by_status": tr_keys(OP_ISSUE_STATUS, by_status),
            "by_impact": tr_keys(IMPACT_LEVEL, by_impact),
            "by_handler": {
                k: {
                    **v,
                    "done_rate": round(v["done"] / v["total"], 2) if v["total"] else 0.0,
                    "overdue_rate": round(v["overdue"] / v["total"], 2) if v["total"] else 0.0,
                }
                for k, v in by_handler.items()
            },
            "high_sensitivity": high,
            "cross_period_items": cross_period,
        }

    # ---- 开发工单 ----
    def _collect_dev_ticket(self, start, end):
        try:
            rows = self.db.query(PmwbDevTicket).all()
        except Exception as e:  # noqa: BLE001
            logger.warning("采集开发工单失败: %s", e)
            return {"items": [], "by_status": {}}
        by_status = defaultdict(int)
        items: List[Dict[str, Any]] = []
        for t in rows:
            st = _g(t, "status") or "created"
            go_live = _date_of(_g(t, "go_live_date"))
            # 已上线且上线日期在周期前的工单不纳入（避免旧已交付工单污染）
            if st == "live" and go_live and go_live < start:
                continue
            in_scope = (
                _is_in_scope(t, start, end, exclude_completed=(st == "live"))
                or _in_range(go_live, start, end)
            )
            if not in_scope:
                continue
            by_status[st] += 1
            items.append({
                "ticket_no": _g(t, "ticket_no"),
                "system_name": _g(t, "system_name"),
                "status": tr(DEV_TICKET_STATUS, st),
                "go_live": go_live.isoformat() if go_live else "",
                "risk_note": _g(t, "risk_note") or "",
            })
        return {"items": items, "by_status": tr_keys(DEV_TICKET_STATUS, by_status)}

    # ---- 会议 ----
    def _collect_meeting(self, start, end):
        try:
            rows = self.db.query(PmwbMeeting).all()
        except Exception as e:  # noqa: BLE001
            logger.warning("采集会议失败: %s", e)
            return {"items": [], "total": 0}
        items: List[Dict[str, Any]] = []
        for m in rows:
            st = _date_of(_g(m, "start_time"))
            if not _in_range(st, start, end):
                continue
            items.append({
                "meeting_id": _g(m, "meeting_id"),
                "title": _g(m, "title"),
                "start_time": _g(m, "start_time").isoformat() if _g(m, "start_time") else "",
                "summary": (_g(m, "summary") or "")[:300],
                "host": _g(m, "host") or "",
            })
        return {"items": items, "total": len(items)}

    # ---- 会议行动项 ----
    def _collect_meeting_action(self, start, end):
        try:
            rows = self.db.query(PmwbMeetingAction).all()
        except Exception as e:  # noqa: BLE001
            logger.warning("采集行动项失败: %s", e)
            return {"total": 0, "done": 0, "completion_rate": 0.0, "unfinished": []}
        total = 0
        done = 0
        unfinished: List[Dict[str, Any]] = []
        for a in rows:
            st = _g(a, "status") or "pending"
            due = _date_of(_g(a, "due_date"))
            # 已完成的行动项排除（除非完成日在周期内）
            in_scope = (
                _is_in_scope(a, start, end, exclude_completed=(st in ("done", "closed")))
                or _in_range(due, start, end)
                or _in_range(_date_of(_g(a, "created_at")), start, end)
            )
            if not in_scope:
                continue
            total += 1
            if st in ("done", "closed"):
                done += 1
            else:
                # 未闭环行动项：下期计划需逐一列出具体对象（标题/负责人/截止日）
                a_title = _g(a, "title") or _g(a, "content") or "（无标题行动项）"
                unfinished.append({
                    "title": a_title[:80],
                    "owner": _g(a, "owner") or "待指派",
                    "due_date": due.isoformat() if due else "",
                    "status": tr(MEETING_ACTION_STATUS, st),
                })
        rate = round(done / total, 2) if total else 0.0
        return {"total": total, "done": done, "completion_rate": rate, "unfinished": unfinished}

    # ---- 个人待办 ----
    def _collect_todo(self, start, end):
        try:
            rows = self.db.query(PmwbTodo).all()
        except Exception as e:  # noqa: BLE001
            logger.warning("采集待办失败: %s", e)
            return {"total": 0, "done": 0, "completion_rate": 0.0, "overdue": 0, "by_category": {}, "by_priority": {}}
        total = 0
        done = 0
        overdue = 0
        by_category = defaultdict(int)
        by_priority = defaultdict(int)
        overdue_items: List[Dict[str, Any]] = []
        today = date.today()
        for t in rows:
            st = _g(t, "status") or "todo"
            due = _date_of(_g(t, "due_date"))
            completed = _date_of(_g(t, "completed_at"))
            in_scope = (
                _is_in_scope(t, start, end, exclude_completed=(st in ("done", "cancelled")))
                or _in_range(completed, start, end)
                or _in_range(due, start, end)
            )
            if not in_scope:
                continue
            total += 1
            cat = _g(t, "category") or "other"
            by_category[cat] += 1
            by_priority[_g(t, "priority") or "P2"] += 1
            if st in ("done", "cancelled") and completed:
                done += 1
            if st not in ("done", "cancelled") and due and due < today:
                overdue += 1
                overdue_items.append({
                    "title": (_g(t, "title") or "")[:80],
                    "due_date": due.isoformat(),
                    "category": tr(TODO_CATEGORY, cat),
                    "priority": tr(IMPACT_LEVEL, _g(t, "priority")),
                })
        rate = round(done / total, 2) if total else 0.0
        return {
            "total": total, "done": done, "completion_rate": rate, "overdue": overdue,
            "by_category": tr_keys(TODO_CATEGORY, by_category),
            "by_priority": tr_keys(IMPACT_LEVEL, by_priority),
            "overdue_items": overdue_items,
        }

    # ---- 知识中心 ----
    def _collect_knowledge(self, start, end):
        try:
            rows = self.db.query(PmwbKnowledgeItem).all()
        except Exception as e:  # noqa: BLE001
            logger.warning("采集知识库失败: %s", e)
            return {"total": 0, "by_category": {}}
        by_category = defaultdict(int)
        total = 0
        for k in rows:
            if not _in_range(_date_of(_g(k, "created_at")), start, end):
                continue
            total += 1
            by_category[_g(k, "category") or "other"] += 1
        return {"total": total, "by_category": dict(by_category)}

    # ---- 重点工作 ----
    def _collect_key_work(self, start, end):
        try:
            rows = self.db.query(PmwbKeyWork).all()
        except Exception as e:  # noqa: BLE001
            logger.warning("采集重点工作失败: %s", e)
            return {"total": 0, "by_category": {}, "by_status": {}, "by_priority": {},
                    "active": [], "completed_in_range": [], "overdue": []}
        by_category = defaultdict(int)
        by_status = defaultdict(int)
        by_priority = defaultdict(int)
        active: List[Dict[str, Any]] = []
        completed_in_range: List[Dict[str, Any]] = []
        overdue: List[Dict[str, Any]] = []

        this_week_label = _iso_week(start)
        next_week_label = _iso_week(start + timedelta(days=7))

        PLAN_STATUS_LABELS = {
            "not_started": "未开始",
            "in_progress": "进行中",
            "completed": "已完成",
            "cancelled": "已作废",
            "delayed": "已延期",
        }

        def _fmt_weekly_plan(p):
            p_status = _g(p, "status") or "not_started"
            return {
                "title": _g(p, "title") or "",
                "content": (_g(p, "content") or "")[:200],
                "assignee": _g(p, "assignee") or "",
                "status": PLAN_STATUS_LABELS.get(p_status, p_status),
                "due_date": _date_of(_g(p, "due_date")).isoformat() if _date_of(_g(p, "due_date")) else "",
            }

        for w in rows:
            cat = _g(w, "category") or "annual_task"
            st = _g(w, "status") or "planning"
            pri = _g(w, "priority") or "P2"
            title = _g(w, "title") or ""
            owner = _g(w, "owner") or ""
            progress = _g(w, "progress") or 0
            planned = _date_of(_g(w, "planned_finish_date"))
            updated = _date_of(_g(w, "updated_at"))
            created = _date_of(_g(w, "created_at"))
            work_no = _g(w, "work_no") or ""
            current_status = (_g(w, "current_status") or "")[:200]

            weekly_plans = _g(w, "weekly_plans") or []
            progresses = _g(w, "progresses") or []
            member_tasks = _g(w, "member_tasks") or []

            # 范围判定：主表 updated_at/created_at，或关联周计划/进展/成员任务在范围内有更新
            latest_related = _latest_related_date(w, list(weekly_plans) + list(progresses) + list(member_tasks))
            is_overdue_risk = planned and planned < end and st not in ("completed", "cancelled")
            in_scope = (
                _in_range(updated, start, end)
                or _in_range(created, start, end)
                or _in_range(latest_related, start, end)
                or _in_range(planned, start, end)
            )
            if not in_scope and not is_overdue_risk:
                continue

            by_category[cat] += 1
            by_status[st] += 1
            by_priority[pri] += 1

            # 本周/下周计划与本周进展
            this_week_plans = [p for p in weekly_plans if _g(p, "week") == this_week_label]
            next_week_plans = [p for p in weekly_plans if _g(p, "week") == next_week_label]
            this_week_progresses = [
                p for p in progresses
                if _in_range(_date_of(_g(p, "record_date")), start, end)
            ]

            this_week_plan_summary = {
                "week": this_week_label,
                "total": len(this_week_plans),
                "done": sum(1 for p in this_week_plans if (_g(p, "status") or "") == "completed"),
                "items": [_fmt_weekly_plan(p) for p in this_week_plans],
            }
            next_week_plan_summary = {
                "week": next_week_label,
                "total": len(next_week_plans),
                "items": [_fmt_weekly_plan(p) for p in next_week_plans],
            }
            this_week_progress_summary = [
                {
                    "record_date": _date_of(_g(p, "record_date")).isoformat() if _date_of(_g(p, "record_date")) else "",
                    "content": (_g(p, "content") or "")[:300],
                    "reporter": _g(p, "reporter") or "",
                }
                for p in this_week_progresses
            ]

            # 本期完成（状态为已完成且更新落在区间内）
            if st == "completed" and _in_range(updated, start, end):
                completed_in_range.append({
                    "work_no": work_no,
                    "title": title,
                    "owner": owner,
                    "completed_at": updated.isoformat() if updated else "",
                })
            # 规划中/进行中/已暂停 视为重点推进事项
            if st in ("planning", "in_progress", "paused"):
                active.append({
                    "work_no": work_no,
                    "title": title,
                    "category": tr(KW_CATEGORY, cat),
                    "owner": owner,
                    "priority": tr(KW_PRIORITY, pri),
                    "status": tr(KW_STATUS, st),
                    "progress": progress,
                    "planned_finish_date": planned.isoformat() if planned else "",
                    "current_status": current_status,
                    "this_week_plan": this_week_plan_summary,
                    "next_week_plan": next_week_plan_summary,
                    "this_week_progress": this_week_progress_summary,
                })
            # 逾期风险：计划完成日已过且未完结（非已完成/已取消）
            if is_overdue_risk:
                overdue.append({
                    "title": title,
                    "owner": owner,
                    "planned_finish_date": planned.isoformat(),
                    "status": tr(KW_STATUS, st),
                })
        return {
            "total": len(by_category) and sum(by_category.values()),
            "by_category": tr_keys(KW_CATEGORY, by_category),
            "by_status": tr_keys(KW_STATUS, by_status),
            "by_priority": tr_keys(KW_PRIORITY, by_priority),
            "active": active,
            "completed_in_range": completed_in_range,
            "overdue": overdue,
        }

    # ---- 主动优化 ----
    def _collect_active_optimization(self, start, end):
        try:
            rows = self.db.query(PmwbActiveOptimization).all()
        except Exception as e:  # noqa: BLE001
            logger.warning("采集主动优化失败: %s", e)
            return {"items": [], "buckets": {}, "stats": {}}

        buckets = {"added": [], "adopted": [], "rejected": [], "pending": []}
        items = []
        for r in rows:
            created = _date_of(_g(r, "created_at"))
            updated = _date_of(_g(r, "updated_at"))
            in_scope = (
                _is_in_scope(r, start, end)
                or _in_range(created, start, end)
            )
            if not in_scope:
                continue

            status = _g(r, "status") or "pending"
            item = {
                "title": _g(r, "title") or "",
                "status": status,
                "admin_name": _g(r, "admin_name") or "",
                "req_id": _g(r, "req_id") or "",
                "current_situation": (_g(r, "current_situation") or "")[:200],
                "suggestion": (_g(r, "suggestion") or "")[:200],
            }

            if _in_range(created, start, end):
                buckets["added"].append(item["title"])
            if status == "adopted":
                buckets["adopted"].append(item["title"])
            elif status == "rejected":
                buckets["rejected"].append(item["title"])
            else:
                buckets["pending"].append(item["title"])
            items.append(item)

        return {
            "items": items,
            "buckets": buckets,
            "stats": {
                "total": len(items),
                "adopted": len(buckets["adopted"]),
                "rejected": len(buckets["rejected"]),
                "pending": len(buckets["pending"]),
            },
        }
