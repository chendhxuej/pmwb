# -*- coding: utf-8 -*-
"""
L2 功能模块问题归并服务（分析汇聚输出层）。

设计（对应 2026-11-05 优化方案）：
- 闭集归并：只用 constants/complaint_module.py 字典内 ID，规则/别名锚定优先，绝不自由建类。
- 归并键 = 业务功能模块 × 失效对象 × 失效性质；表象文案/涉及系统/客户/地市/时间不参与键。
- 跨表象汇聚：同一模块问题下「描述不同、本质同模块」的工单强制归并（老大举例：开户/激活后账号未同步）。
- 不依赖人：主流投诉自动归集；少量无匹配/低置信进入「待处理队列」，系统可完整运行，人工管理台为可选安全网。
- 派生字段（ticket_cnt/first_week/active_weeks/surfaces）全部由逐单映射重建，保证可重建（无漂移）。
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from constants import complaint_module as M
from constants.complaint_module import MODULE_PROBLEMS, match_module_problem
from db.models import (
    PmwbComplaintModuleProblem,
    PmwbComplaintTicketModule,
    PmwbComplaintProblemPoint,
    PmwbComplaintTicket,
)

logger = logging.getLogger(__name__)

POLICY_VERSION = "vL2-%d" % M.MODULE_DICT_VERSION


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _loads(raw: Any, fallback: Any) -> Any:
    if raw is None or raw == "":
        return fallback
    try:
        return json.loads(raw)
    except Exception:
        return fallback


def _norm_surface(point: str) -> str:
    p = (point or "").strip()
    # 去尾点号/空格，便于跨表象去重展示
    while p and p[-1] in "。. ；;，, ":
        p = p[:-1]
    return p


def _soft_suggest(point: str, fault_stage: Optional[str], category_l1: Optional[str]):
    """非严格建议：仅命中对象族时，给出该对象族下优先级最高的模块问题作为人工台默认建议。"""
    pt = point or ""
    for m in sorted(MODULE_PROBLEMS, key=lambda x: x["priority"]):
        if any(o in pt for o in m["objects"]):
            if m["is_defect"]:
                return m["id"]
    return None


def run_aggregate(db: Session, dry_run: bool = True) -> Dict:
    """对全量工单执行 L2 闭集归并。dry_run=True 仅统计不落库。"""
    rows = (
        db.query(
            PmwbComplaintTicket.ticket_no,
            PmwbComplaintTicket.week,
            PmwbComplaintTicket.city,
            PmwbComplaintProblemPoint.point,
            PmwbComplaintTicket.content,
            PmwbComplaintTicket.fault_stage,
            PmwbComplaintTicket.category_l1,
        )
        .join(PmwbComplaintProblemPoint, PmwbComplaintProblemPoint.ticket_no == PmwbComplaintTicket.ticket_no)
        .all()
    )

    ticket_rows = []  # (ticket_no, mp_id, confidence, surface, review_status, gap, suggested_id, week)
    for r in rows:
        ticket_no, week, city, point, content, stage, cat = r
        # 两遍匹配：先用 L1 简述(point)，未命中再用原始工单内容(content)兜底。
        # 既保留已归类工单的稳定口径，又把「简述为空/含糊」的残留单尽量归上
        # （空 point 正是 343 未归类的主因）。
        signal = point or ""
        mp_id, conf, reason = match_module_problem(signal, stage, cat)
        if mp_id is None and content:
            mp_id, conf, reason = match_module_problem(content or "", stage, cat)
            signal = content or ""
        surface = _norm_surface(signal[:80]) if signal else _norm_surface(point)
        if mp_id is None:
            suggested = _soft_suggest(point or content or "", stage, cat)
            ticket_rows.append((ticket_no, None, None, surface, "unclassified", reason, suggested, week))
        else:
            review = "auto" if conf == "high" else "low"
            ticket_rows.append((ticket_no, mp_id, conf, surface, review, "", None, week))

    # 聚合
    agg = defaultdict(lambda: {"cnt": 0, "weeks": set(), "surfaces": set()})
    unclassified = 0
    low = 0
    for t in ticket_rows:
        mp_id = t[1]
        if mp_id is None:
            unclassified += 1
            continue
        if t[4] == "low":
            low += 1
        a = agg[mp_id]
        a["cnt"] += 1
        if t[7] and week_of(t[7]) is not None:
            a["weeks"].add(week_of(t[7]))
        if t[3]:
            a["surfaces"].add(t[3])

    result = {
        "total": len(ticket_rows),
        "classified": len(ticket_rows) - unclassified,
        "unclassified": unclassified,
        "low_conf": low,
        "classes": len([k for k in agg if M.get_module_problem(k) and M.get_module_problem(k)["is_defect"]]),
        "module_problems": [
            {
                "module_problem_id": k,
                "name": (M.get_module_problem(k) or {}).get("name", k),
                "is_defect": (M.get_module_problem(k) or {}).get("is_defect", 1),
                "ticket_cnt": v["cnt"],
                "active_weeks": len(v["weeks"]),
                "surface_cnt": len(v["surfaces"]),
            }
            for k, v in sorted(agg.items(), key=lambda x: -x[1]["cnt"])
        ],
    }

    if dry_run:
        return result

    # 落库
    db.query(PmwbComplaintTicketModule).delete()
    db.query(PmwbComplaintModuleProblem).delete()
    now = datetime.now()
    for t in ticket_rows:
        ticket_no, mp_id, conf, surface, review, gap, suggested, _week = t
        db.add(
            PmwbComplaintTicketModule(
                ticket_no=ticket_no,
                module_problem_id=mp_id,
                confidence=conf,
                surface=surface,
                review_status=review,
                gap=gap,
                suggested_id=suggested,
                policy_version=POLICY_VERSION,
                updated_at=now,
            )
        )
    for k, v in agg.items():
        mp = M.get_module_problem(k)
        if not mp:
            continue
        weeks_sorted = sorted(v["weeks"])
        db.add(
            PmwbComplaintModuleProblem(
                module_problem_id=k,
                name=mp["name"],
                module=mp["module"],
                fail_object=mp["fail_object"],
                fail_nature=mp["fail_nature"],
                is_defect=1 if mp["is_defect"] else 0,
                ticket_cnt=v["cnt"],
                first_week=weeks_sorted[0] if weeks_sorted else None,
                active_weeks=len(weeks_sorted),
                surfaces_json=_dumps(sorted(v["surfaces"])),
                status="published",
                version=M.MODULE_DICT_VERSION,
                policy_version=POLICY_VERSION,
                created_at=now,
                updated_at=now,
            )
        )
    db.commit()
    return result


def week_of(week: str) -> Optional[str]:
    """归一 ISO 周字符串，无效返回 None。"""
    if not week:
        return None
    wk = week.strip()
    if len(wk) >= 8 and wk[4] == "-":
        return wk
    return wk


def rebuild_counters(db: Session) -> int:
    """由逐单映射全量重建模块问题派生字段（保证可重建，无漂移）。"""
    rows = (
        db.query(
            PmwbComplaintTicketModule.module_problem_id,
            func.count(PmwbComplaintTicketModule.ticket_no),
        )
        .filter(PmwbComplaintTicketModule.module_problem_id.isnot(None))
        .group_by(PmwbComplaintTicketModule.module_problem_id)
        .all()
    )
    cnt_map = {r[0]: r[1] for r in rows}
    surfaces_map = defaultdict(set)
    weeks_map = defaultdict(set)
    tm = (
        db.query(
            PmwbComplaintTicketModule.module_problem_id,
            PmwbComplaintTicketModule.surface,
            PmwbComplaintTicket.week,
        )
        .join(PmwbComplaintTicket, PmwbComplaintTicket.ticket_no == PmwbComplaintTicketModule.ticket_no)
        .filter(PmwbComplaintTicketModule.module_problem_id.isnot(None))
        .all()
    )
    for mp_id, surface, week in tm:
        if surface:
            surfaces_map[mp_id].add(surface)
        if week:
            weeks_map[mp_id].add(week)
    for mp_id, cnt in cnt_map.items():
        mp = db.query(PmwbComplaintModuleProblem).filter_by(module_problem_id=mp_id).first()
        if not mp:
            continue
        mp.ticket_cnt = cnt
        mp.active_weeks = len(weeks_map.get(mp_id, set()))
        mp.first_week = sorted(weeks_map.get(mp_id, set()))[0] if weeks_map.get(mp_id) else None
        mp.surfaces_json = _dumps(sorted(surfaces_map.get(mp_id, set())))
        mp.updated_at = datetime.now()
    db.commit()
    return len(cnt_map)


def list_module_problems(db: Session, include_consult: bool = False,
                         week: Optional[str] = None) -> List[Dict]:
    """模块问题类表（主视角：主要投诉点）。

    week 为空取库内最新周；同时给出该周单量与环比（2026-11-10 由「热点投诉」页
    并入——原热门榜单走旧 l2 口径，与闭集重复，其环比能力在此承接）。
    """
    from services.complaint.metrics import prev_week

    if not week:
        week = db.query(func.max(PmwbComplaintTicket.week)).scalar()
    pw = prev_week(week) if week else ""

    problems = db.query(PmwbComplaintModuleProblem).all()
    out = []
    for p in problems:
        if not include_consult and p.is_defect == 0:
            continue
        # 表象离散度：一类内不同表象数（衡量跨表象汇聚成效）
        surfaces = _loads(p.surfaces_json, [])
        # 近 8 周日均分布
        weekly = _weekly_distribution(db, p.module_problem_id)
        cur_cnt = next((w["cnt"] for w in weekly if w["week"] == week), 0)
        prev_cnt = next((w["cnt"] for w in weekly if w["week"] == pw), 0)
        wow = round((cur_cnt - prev_cnt) / prev_cnt * 100, 1) if prev_cnt else None
        out.append({
            "module_problem_id": p.module_problem_id,
            "name": p.name,
            "module": p.module,
            "fail_object": p.fail_object,
            "fail_nature": p.fail_nature,
            "is_defect": p.is_defect,
            "ticket_cnt": p.ticket_cnt,
            "first_week": p.first_week,
            "active_weeks": p.active_weeks,
            "surface_cnt": len(surfaces),
            "surfaces": surfaces[:12],  # 展示取前 12 种说法；surface_cnt 为真实去重总数
            "weekly": weekly,
            # 环比（承接热点投诉页能力）：本周单量 / 上周单量 / 环比百分比（上周 0 单为 None）
            "stat_week": week,
            "week_cnt": cur_cnt,
            "prev_week_cnt": prev_cnt,
            "wow_pct": wow,
        })
    # 缺陷类优先；主排序键必须与调用方展示的字段一致。看板 TOP 榜展示 week_cnt，
    # 若调用方展示 ticket_cnt 却按 week_cnt 排，会出现「第 1 名 80 单、第 2 名 265 单」
    # 的错位（2026-11-10 实测）。调用方须显式传 week，保证与页面选周同源。
    out.sort(key=lambda x: (-x["is_defect"], -x["week_cnt"], -x["ticket_cnt"]))
    return out


def _weekly_distribution(db: Session, mp_id: str) -> List[Dict]:
    rows = (
        db.query(PmwbComplaintTicket.week, func.count(PmwbComplaintTicketModule.ticket_no))
        .join(PmwbComplaintTicketModule, PmwbComplaintTicketModule.ticket_no == PmwbComplaintTicket.ticket_no)
        .filter(PmwbComplaintTicketModule.module_problem_id == mp_id)
        .group_by(PmwbComplaintTicket.week)
        .all()
    )
    return [{"week": r[0], "cnt": r[1]} for r in rows if r[0]]


def list_unclassified(db: Session, page: int = 1, page_size: int = 50) -> Dict:
    """未归类清单：逐单写明缺口（待处理队列，不污染缺陷主 KPI）。"""
    q = db.query(PmwbComplaintTicketModule).filter_by(review_status="unclassified")
    total = q.count()
    items = (
        q.order_by(PmwbComplaintTicketModule.ticket_no)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    out = []
    for t in items:
        out.append({
            "ticket_no": t.ticket_no,
            "surface": t.surface,
            "gap": t.gap,
            "suggested_id": t.suggested_id,
        })
    return {"total": total, "page": page, "page_size": page_size, "items": out}


def list_review_queue(db: Session, page: int = 1, page_size: int = 50) -> Dict:
    """人工管理台队列：低置信 + 未归类 + 已改派（系统可独立运行，此为可选安全网）。"""
    q = db.query(PmwbComplaintTicketModule).filter(
        PmwbComplaintTicketModule.review_status.in_(["low", "unclassified", "override", "accepted"])
    )
    total = q.count()
    items = (
        q.order_by(PmwbComplaintTicketModule.review_status, PmwbComplaintTicketModule.ticket_no)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    out = []
    for t in items:
        mp = M.get_module_problem(t.module_problem_id) if t.module_problem_id else None
        out.append({
            "ticket_no": t.ticket_no,
            "surface": t.surface,
            "current_id": t.module_problem_id,
            "current_name": (mp or {}).get("name") if mp else None,
            "review_status": t.review_status,
            "confidence": t.confidence,
            "gap": t.gap,
            "suggested_id": t.suggested_id,
        })
    return {"total": total, "page": page, "page_size": page_size, "items": out}


def accept_suggestion(db: Session, ticket_no: str) -> Dict:
    """人工台：一键采纳系统建议（非阻塞；系统不依赖此操作）。"""
    t = db.query(PmwbComplaintTicketModule).filter_by(ticket_no=ticket_no).first()
    if not t:
        return {"ok": False, "msg": "工单不存在"}
    if not t.suggested_id:
        return {"ok": False, "msg": "无系统建议可采纳"}
    t.module_problem_id = t.suggested_id
    t.review_status = "accepted"
    t.updated_at = datetime.now()
    db.commit()
    rebuild_counters(db)
    return {"ok": True, "module_problem_id": t.module_problem_id}


def override_ticket(db: Session, ticket_no: str, target_id: str) -> Dict:
    """人工台：改派到指定模块问题（闭集内 ID 才允许）。"""
    if not M.get_module_problem(target_id):
        return {"ok": False, "msg": "目标模块问题ID不在字典内"}
    t = db.query(PmwbComplaintTicketModule).filter_by(ticket_no=ticket_no).first()
    if not t:
        return {"ok": False, "msg": "工单不存在"}
    t.module_problem_id = target_id
    t.review_status = "override"
    t.gap = ""
    t.updated_at = datetime.now()
    db.commit()
    rebuild_counters(db)
    return {"ok": True, "module_problem_id": target_id}


def summary(db: Session) -> Dict:
    """页面头部汇总（live/merged 两数以同源，防漂移）。"""
    total_tickets = db.query(func.count(PmwbComplaintTicket.ticket_no)).scalar() or 0
    # 缺陷已归集（排除咨询类）
    defect_classified = (
        db.query(func.count(PmwbComplaintTicketModule.ticket_no))
        .filter(PmwbComplaintTicketModule.module_problem_id.isnot(None))
        .filter(PmwbComplaintTicketModule.module_problem_id != "MP-CONSULT")
        .scalar()
        or 0
    )
    consult = (
        db.query(func.count(PmwbComplaintTicketModule.ticket_no))
        .filter_by(module_problem_id="MP-CONSULT")
        .scalar()
        or 0
    )
    unclassified = (
        db.query(func.count(PmwbComplaintTicketModule.ticket_no))
        .filter_by(review_status="unclassified")
        .scalar()
        or 0
    )
    low = (
        db.query(func.count(PmwbComplaintTicketModule.ticket_no))
        .filter_by(review_status="low")
        .scalar()
        or 0
    )
    defect_classes = (
        db.query(func.count(PmwbComplaintModuleProblem.module_problem_id))
        .filter_by(is_defect=1)
        .scalar()
        or 0
    )
    ratio = round(defect_classes / defect_classified, 3) if defect_classified else 0
    top10 = (
        db.query(func.sum(PmwbComplaintModuleProblem.ticket_cnt))
        .filter_by(is_defect=1)
        .scalar()
        or 0
    )
    top10_rate = round(top10 / defect_classified, 3) if defect_classified else 0
    return {
        "total_tickets": total_tickets,
        "defect_classified": defect_classified,
        "consult": consult,
        "unclassified": unclassified,
        "low_conf": low,
        "defect_classes": defect_classes,
        "class_ratio": ratio,
        "top10_rate": top10_rate,
        "policy_version": POLICY_VERSION,
    }
