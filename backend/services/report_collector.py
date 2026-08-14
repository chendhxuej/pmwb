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
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from db.models import (
    PmwbDevTicket,
    PmwbKnowledgeItem,
    PmwbMeeting,
    PmwbMeetingAction,
    PmwbOperationIssue,
    PmwbRequirementEvaluation,
    PmwbRequirementExt,
    PmwbTodo,
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

        # 批量预加载工单/评估并按 req_id 分组，避免逐条需求各查一次（N+1）
        tickets_by_req: Dict[str, List[Any]] = defaultdict(list)
        evals_by_req: Dict[str, List[Any]] = defaultdict(list)
        try:
            for t in self.db.query(PmwbDevTicket).all():
                tickets_by_req[_g(t, "req_id") or ""].append(t)
            for e in self.db.query(PmwbRequirementEvaluation).all():
                evals_by_req[_g(e, "req_id") or ""].append(e)
        except Exception as e:  # noqa: BLE001
            logger.warning("预加载工单/评估失败（按空处理）: %s", e)

        for r in rows:
            try:
                item, bucket_flags, risk = self._build_requirement_item(
                    r, start, end, tickets_by_req, evals_by_req
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("采集单条需求失败（已跳过）: %s", e)
                continue
            items.append(item)
            req_name = item["req_name"]
            for name in bucket_flags:
                buckets[name].append(req_name)
            if "delivered" in bucket_flags:
                delivered_items.append(dict(item))
            if risk:
                po_risk.append(risk)
        return {"items": items, "buckets": buckets, "delivered_items": delivered_items, "po_risk": po_risk}

    def _build_requirement_item(self, r, start, end, tickets_by_req, evals_by_req):
        """把一条需求整理为 (明细 dict, 命中的分桶名列表, PO 级风险项或 None)。"""
        req_id = _g(r, "req_id") or ""
        req_name = _g(r, "req_name") or req_id
        status = _g(r, "status") or "proposed"
        priority = _g(r, "priority") or "P2"
        created = _date_of(_g(r, "created_at"))

        tickets = tickets_by_req.get(req_id, [])
        evals = evals_by_req.get(req_id, [])
        go_live = None
        for t in tickets:
            d = _date_of(_g(t, "go_live_date"))
            if d and (go_live is None or d > go_live):
                go_live = d
        workload = sum(float(_g(e, "workload") or 0) for e in evals)
        risk_notes = "; ".join(str(_g(t, "risk_note") or "") for t in tickets if _g(t, "risk_note"))

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
            "workload": workload,
            "dev_status": [(_g(t, "status") or "") for t in tickets],
        }

        # 本期新增/评估/启动开发/交付/进行中分桶
        flags: List[str] = []
        if _in_range(created, start, end):
            flags.append("added")
        if any(_in_range(_date_of(_g(e, "created_at")), start, end) for e in evals):
            flags.append("evaluated")
        if any(
            _in_range(_date_of(_g(t, "created_at")), start, end)
            or _in_range(_date_of(_g(t, "design_reviewed_date")), start, end)
            for t in tickets
        ):
            flags.append("dev_start")
        if go_live and _in_range(go_live, start, end):
            flags.append("delivered")
        if status != "closed":
            flags.append("ongoing")

        risk = None
        is_high = ("P0" in str(priority)) or ("集团需求" in str(priority)) or ("紧急需求" in str(priority))
        dev_high = any((_g(t, "priority") == "P0") for t in tickets)
        if (is_high or dev_high) and status != "closed":
            risk = {
                "req_name": req_name,
                "priority": priority,
                "status": status,
                "go_live": go_live.isoformat() if go_live else "",
                "risk_note": risk_notes,
            }
        return item, flags, risk

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
        for r in rows:
            cat = _g(r, "category") or "other"
            st = _g(r, "status") or "pending"
            impact = _g(r, "impact_level") or "P2"
            handler = _g(r, "handler") or ""
            handlers = [h.strip() for h in str(handler).split(",") if h.strip()]
            disc = _date_of(_g(r, "discovery_date")) or _date_of(_g(r, "created_at"))
            resolve = _date_of(_g(r, "resolve_date"))
            is_overdue = _g(r, "is_overdue") or 0

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
                    "category": cat,
                    "status": st,
                    "handler": handler,
                    "impact": impact,
                })
            if _in_range(disc, start, end) or _in_range(resolve, start, end):
                items.append({
                    "issue_no": _g(r, "issue_no"),
                    "title": _g(r, "title"),
                    "category": cat,
                    "status": st,
                    "impact": impact,
                    "handler": handler,
                })
        return {
            "items": items,
            "by_category": dict(by_category),
            "by_status": dict(by_status),
            "by_impact": dict(by_impact),
            "by_handler": {k: v for k, v in by_handler.items()},
            "high_sensitivity": high,
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
            by_status[st] += 1
            go_live = _date_of(_g(t, "go_live_date"))
            if _in_range(go_live, start, end) or _in_range(_date_of(_g(t, "created_at")), start, end):
                items.append({
                    "ticket_no": _g(t, "ticket_no"),
                    "system_name": _g(t, "system_name"),
                    "status": st,
                    "go_live": go_live.isoformat() if go_live else "",
                    "risk_note": _g(t, "risk_note") or "",
                })
        return {"items": items, "by_status": dict(by_status)}

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
            return {"total": 0, "done": 0, "completion_rate": 0.0}
        total = 0
        done = 0
        for a in rows:
            due = _date_of(_g(a, "due_date"))
            if not (_in_range(due, start, end) or _in_range(_date_of(_g(a, "created_at")), start, end)):
                continue
            total += 1
            if (_g(a, "status") or "pending") in ("done", "closed"):
                done += 1
        rate = round(done / total, 2) if total else 0.0
        return {"total": total, "done": done, "completion_rate": rate}

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
        today = date.today()
        for t in rows:
            st = _g(t, "status") or "todo"
            due = _date_of(_g(t, "due_date"))
            completed = _date_of(_g(t, "completed_at"))
            if not (
                _in_range(_date_of(_g(t, "created_at")), start, end)
                or _in_range(completed, start, end)
                or _in_range(due, start, end)
            ):
                continue
            total += 1
            by_category[_g(t, "category") or "other"] += 1
            by_priority[_g(t, "priority") or "P2"] += 1
            if st in ("done", "cancelled") and completed:
                done += 1
            if st not in ("done", "cancelled") and due and due < today:
                overdue += 1
        rate = round(done / total, 2) if total else 0.0
        return {
            "total": total, "done": done, "completion_rate": rate, "overdue": overdue,
            "by_category": dict(by_category), "by_priority": dict(by_priority),
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
            if _in_range(_date_of(_g(k, "created_at")), start, end):
                total += 1
                by_category[_g(k, "category") or "other"] += 1
        return {"total": total, "by_category": dict(by_category)}
