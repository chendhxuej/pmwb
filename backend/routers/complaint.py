"""客诉专题分析 API —— 台账/字典/措施/指标/周报/导入。

口径纪律：
  - 指标一律调 services/complaint/metrics.collect（唯一实现），禁止在路由层重算；
  - 分类一律走字典表；人工校正置 classify_by='manual'，reclassify 不覆盖；
  - 措施状态流转复用任务中心统一端点（PUT /task-center/tasks/complaint_action/{no}/status），
    本路由不另设流转口，避免第二套校验。
"""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from services.mail_dispatch import dispatch_email
from schemas.complaint import (
    ActionCreateIn,
    ActionUpdateIn,
    CategoryCorrectIn,
    CategoryEnabledIn,
    GoLiveIn,
    ProblemActionLinkIn,
    ProblemConfirmIn,
    ProblemCreateIn,
    ProblemStatusIn,
    ProblemUpdateIn,
    ProblemUrgeIn,
    ReportGenIn,
    UrgePreviewIn,
)
from services.complaint import (
    actions as complaint_actions,
    classify as complaint_classify,
    metrics as complaint_metrics,
    pipeline as complaint_pipeline,
    problems as complaint_problems,
)
from services.complaint.ingest import ingest_file
from utils.owners import split_owners

router = APIRouter(prefix="/complaint", tags=["客诉专题分析"])


# ── 台账 ─────────────────────────────────────────────────────
@router.get("/tickets")
def list_tickets(
    db: Session = Depends(get_db),
    week: Optional[str] = Query(None, description="周次，如 2026-W43"),
    keyword: Optional[str] = Query(None, description="内容关键词"),
    l1: Optional[str] = Query(None, description="一级性质"),
    l2: Optional[str] = Query(None, description="二级场景"),
    is_batch: Optional[int] = Query(None, ge=0, le=1),
    classify_by: Optional[str] = Query(None, description="auto / manual"),
    handler: Optional[str] = Query(None, description="处理人（精确）"),
    problem_no: Optional[str] = Query(None, description="按归属共性问题下钻"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """客诉工单台账分页列表。"""
    where = ["1 = 1"]
    params: dict = {}
    if week:
        where.append("week = :week")
        params["week"] = week
    if keyword:
        where.append("(content LIKE :kw OR ticket_no LIKE :kw)")
        params["kw"] = f"%{keyword}%"
    if l1:
        where.append("category_l1 = :l1")
        params["l1"] = l1
    if l2:
        where.append("category_l2 = :l2")
        params["l2"] = l2
    if is_batch is not None:
        where.append("is_batch = :ib")
        params["ib"] = is_batch
    if classify_by:
        where.append("classify_by = :cb")
        params["cb"] = classify_by
    if handler:
        where.append("handler = :handler")
        params["handler"] = handler
    if problem_no:
        where.append("problem_no = :pno")
        params["pno"] = problem_no

    cond = " AND ".join(where)
    total = db.execute(text(
        f"SELECT COUNT(*) FROM pmwb_complaint_ticket WHERE {cond}"
    ), params).scalar() or 0
    rows = db.execute(text(f"""
        SELECT id, ticket_no, week, created_time, city, channel, appeal_category, biz_attr,
               handler, handle_unit, dispatch_count, status, category_l1, category_l2,
               classify_by, cluster_key, is_batch, is_recur, problem_no, remark,
               content
        FROM pmwb_complaint_ticket WHERE {cond}
        ORDER BY created_time DESC
        LIMIT :limit OFFSET :offset
    """), {**params, "limit": page_size, "offset": (page - 1) * page_size}).mappings().all()

    return success({
        "total": int(total),
        "page": page,
        "page_size": page_size,
        "items": [
            {**dict(r), "content_preview": (r.get("content") or "")[:300]}
            for r in rows
        ],
    })


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    """工单详情（含解决方案历史全文）。"""
    row = db.execute(text(
        "SELECT * FROM pmwb_complaint_ticket WHERE id = :id"
    ), {"id": ticket_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="工单不存在")
    return success(dict(row))


@router.put("/tickets/{ticket_id}/category")
def correct_category(ticket_id: int, body: CategoryCorrectIn, db: Session = Depends(get_db)):
    """人工校正分类：落库并置 classify_by='manual'（reclassify 不覆盖）。"""
    row = db.execute(text(
        "SELECT id FROM pmwb_complaint_ticket WHERE id = :id"
    ), {"id": ticket_id}).scalar()
    if not row:
        raise HTTPException(status_code=404, detail="工单不存在")
    db.execute(text("""
        UPDATE pmwb_complaint_ticket
        SET category_l1 = :l1, category_l2 = :l2, classify_by = 'manual',
            remark = COALESCE(:remark, remark), updated_at = :now_ts
        WHERE id = :id
    """), {"l1": body.category_l1, "l2": body.category_l2,
           "remark": body.remark, "id": ticket_id, "now_ts": datetime.now()})
    db.commit()
    # 校正可能影响批量簇构成（同场景单量变化）→ 重算该单所在周派生字段
    week = db.execute(text(
        "SELECT week FROM pmwb_complaint_ticket WHERE id = :id"
    ), {"id": ticket_id}).scalar()
    if week:
        from services.complaint.ingest import refresh_derived
        refresh_derived(db, weeks=[week])
        # 人工校正只回写归因与周轨迹，不重扫候选（避免校正产生候选噪音）
        if complaint_metrics.latest_week(db):
            complaint_problems.assign_tickets(db, week=week)
            complaint_problems.recompute(db, week=week)
    return success({"id": ticket_id, "classify_by": "manual"})


@router.get("/clusters")
def list_clusters(week: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """批量异常簇清单（week 为空取库内最新周）。"""
    week = week or complaint_metrics.latest_week(db)
    if not week:
        return success({"week": "", "clusters": []})
    m = complaint_metrics.collect(db, week)
    return success({"week": week, "clusters": m["batch"]["clusters"]})


# ── 分类字典 ─────────────────────────────────────────────────
@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    """两级分类字典（含停用项，供维护与校正下拉）。"""
    rows = db.execute(text("""
        SELECT id, level, parent_name, name, keywords, sort_order, enabled, note, updated_at
        FROM pmwb_complaint_category
        ORDER BY sort_order ASC
    """)).mappings().all()
    return success([dict(r) for r in rows])


@router.put("/categories/{category_id}/enabled")
def toggle_category(category_id: int, body: CategoryEnabledIn, db: Session = Depends(get_db)):
    """字典启停：启停改变分类口径，必须清分类引擎进程缓存。"""
    row = db.execute(text(
        "SELECT id FROM pmwb_complaint_category WHERE id = :id"
    ), {"id": category_id}).scalar()
    if not row:
        raise HTTPException(status_code=404, detail="字典条目不存在")
    db.execute(text(
        "UPDATE pmwb_complaint_category SET enabled = :e, updated_at = :now_ts WHERE id = :id"
    ), {"e": body.enabled, "id": category_id, "now_ts": datetime.now()})
    db.commit()
    complaint_classify.clear_cache()
    return success({"id": category_id, "enabled": body.enabled})


# ── 措施台账 ─────────────────────────────────────────────────
@router.get("/actions")
def list_actions(db: Session = Depends(get_db)):
    """措施台账全量（按状态优先级 + 完成期限排序）。"""
    return success(complaint_actions.list_actions(db))


@router.post("/actions/verify")
def verify_actions(db: Session = Depends(get_db)):
    """结算验证中的措施（到观察期自动定论 effective/ineffective）。"""
    return success(complaint_actions.verify(db))


@router.post("/actions/{action_no}/go-live")
def go_live(action_no: str, body: GoLiveIn, db: Session = Depends(get_db)):
    """标记措施生效并绑定基线（生效日前 N 周该场景周均单量）。"""
    row = db.execute(text(
        "SELECT id FROM pmwb_complaint_action WHERE action_no = :no"
    ), {"no": action_no}).scalar()
    if not row:
        raise HTTPException(status_code=404, detail="措施不存在")
    complaint_actions.mark_go_live(db, action_no, body.go_live_date)
    return success(complaint_actions.list_actions(db))


@router.post("/actions")
def create_action(body: ActionCreateIn, db: Session = Depends(get_db)):
    """登记措施（可选同步创建运营工单父子关联 + 关联共性问题，进程内调用）。"""
    try:
        r = complaint_actions.add(
            db, body.l2, body.title, body.owner, body.due_date,
            body.acceptance, body.create_issue, body.desc,
            problem_nos=body.problem_nos or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(r)


@router.put("/actions/{action_no}")
def update_action(action_no: str, body: ActionUpdateIn, db: Session = Depends(get_db)):
    """编辑措施基础字段（不含状态流转——流转走任务中心统一端点）。"""
    row = db.execute(text(
        "SELECT id FROM pmwb_complaint_action WHERE action_no = :no"
    ), {"no": action_no}).scalar()
    if not row:
        raise HTTPException(status_code=404, detail="措施不存在")

    sets: List[str] = ["updated_at = :now_ts"]
    params: dict = {"no": action_no, "now_ts": datetime.now()}
    if body.title is not None:
        sets.append("title = :title")
        params["title"] = body.title
    if body.owner is not None:
        sets.append("owner = :owner")
        params["owner"] = body.owner
    if body.due_date is not None:
        sets.append("due_date = :due")
        params["due"] = body.due_date
    if body.acceptance is not None:
        sets.append("acceptance = :acc")
        params["acc"] = body.acceptance
    if body.note is not None:
        sets.append("note = :note")
        params["note"] = body.note
    if body.target_drop_pct is not None:
        sets.append("target_drop_pct = :tdp")
        params["tdp"] = body.target_drop_pct
    if body.verify_weeks is not None:
        sets.append("verify_weeks = :vw")
        params["vw"] = body.verify_weeks

    db.execute(text(
        f"UPDATE pmwb_complaint_action SET {', '.join(sets)} WHERE action_no = :no"
    ), params)
    db.commit()
    from services.complaint import get_action
    return success(get_action(db, action_no))


# ── 指标与周报 ───────────────────────────────────────────────
@router.get("/metrics")
def get_metrics(week: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """周度指标（12 项，唯一实现 metrics.collect）。"""
    try:
        m = complaint_metrics.collect(db, week)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return success(m)


@router.post("/reports")
def gen_report(body: ReportGenIn, db: Session = Depends(get_db)):
    """生成周报（HTML 必出；PDF 失败降级仅 HTML，不抛 500）。"""
    try:
        r = complaint_pipeline.run(db, file=None, week=body.week, pdf=body.with_pdf)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    pdf_ok = Path(r["pdf"]).exists() if r["pdf"] else False
    return success({
        "week": r["week"], "total": r["total"],
        "html": r["html"],
        "pdf": r["pdf"] if pdf_ok else "",
        "pdf_generated": pdf_ok,
    })


@router.get("/reports/{week}/download")
def download_report(week: str, ext: str = Query("html", pattern="^(html|pdf)$")):
    """下载周报文件（HTML / PDF）。"""
    base = Path(r"D:\项目\个人工作台系统\docs\客诉周报")
    path = base / f"客诉周报_{week}.{ext}"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"周报不存在：{path.name}（请先生成）")
    media = "text/html" if ext == "html" else "application/pdf"
    return FileResponse(path, media_type=media, filename=path.name)


# ── 督办邮件 ─────────────────────────────────────────────────
@router.post("/actions/urge-preview")
def urge_preview(body: UrgePreviewIn, db: Session = Depends(get_db)):
    """客诉措施督办邮件：默认 dry_run（落库不真发）；真发须 confirm_send=True
    且由前端显式点击触发（邮件铁律：AI/脚本自测一律 dry_run）。

    收件对象 = 到期/超期（due_date < 今天）且状态属 planned/in_progress/ineffective
    的措施责任人，按人聚合清单走任务中心清单装配器渲染。
    """
    from datetime import date as _date
    from utils.owners import split_owners

    from services.complaint import urge_candidates
    from services.task_center import task_center_service

    candidates = urge_candidates(db)
    if body.owner:
        want = {o for o in split_owners(body.owner)}
        candidates = [c for c in candidates
                      if want & set(split_owners(c.get("owner") or ""))]
    if not candidates:
        return success({"sent": [], "skipped": "无到期/超期未完结的客诉措施"})

    today = _date.today()
    by_owner: dict = {}
    for c in candidates:
        owners = split_owners(c.get("owner") or "") or ["未指派"]
        for o in owners:
            flags: dict = {"is_overdue": False, "is_due_soon": False}
            due = c.get("due_date")
            if due:
                d = due if isinstance(due, _date) else _date.fromisoformat(str(due)[:10])
                if d < today:
                    flags["is_overdue"] = True
                elif (d - today).days <= 3:
                    flags["is_due_soon"] = True
            by_owner.setdefault(o, []).append({
                "title": f"[{c['action_no']}] {c.get('title') or ''}",
                "source_label": "客诉措施",
                "owner": o,
                "created_at": "",
                "due_date": str(due)[:10] if due else "",
                "status_label": c.get("status") or "",
                "priority": "P1",
                "description": (
                    f"针对场景：{c.get('category_l2') or '—'}；"
                    f"基线/目标：{c.get('baseline_cnt') if c.get('baseline_cnt') is not None else '—'}"
                    f" / 降{c.get('target_drop_pct') or 50}%；"
                    f"上周单量：{c.get('last_week_cnt') if c.get('last_week_cnt') is not None else '—'}；"
                    f"关联工单：{c.get('issue_no') or '—'}"
                ),
                **flags,
            })

    results = []
    for owner, tasks in by_owner.items():
        if owner == "未指派":
            results.append({"owner": owner, "skipped": "措施未指派责任人，无法督办"})
            continue
        resolved = task_center_service.resolve_contacts([owner])
        to_addr = resolved.get(owner)
        if not to_addr:
            results.append({"owner": owner, "skipped": f"收件人邮箱解析失败（{owner}）"})
            continue
        r = dispatch_email(
            db=db, to=[to_addr],
            subject=body.subject,
            scene="complaint_action_urge",
            variables={"tasks": tasks, "recipient_name": owner},
            fields={"tasks": tasks},
            recipient_name=owner,
            email_type="pmwb_complaint_urge",
            req_id=";".join(t["title"].split("]")[0][1:] for t in tasks[:5])[:64],
            req_name=f"客诉措施督办（{len(tasks)} 项）",
            ref_type="complaint_action",
            ref_id=tasks[0]["title"].split("]")[0][1:],
            raise_on_error=False,
            confirm_send=body.confirm_send,
        )
        results.append({
            "owner": owner, "to": to_addr, "task_cnt": len(tasks),
            "dry_run": bool(r.get("dry_run")), "success": r.get("success"),
            "record_id": r.get("record_id"),
            "subject": r.get("subject"),
        })
    return success({"sent": results, "total_candidates": len(candidates)})


# ── 共性问题台账（闭环管理） ─────────────────────────────────
# 注意：candidates/scan/closure-suggestions/urge-preview 须声明在 /{problem_no} 之前
@router.get("/problems")
def list_problems(
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None, description="逗号分隔，如 open,resolving"),
    week: Optional[str] = Query(None, description="按首见/末见周过滤"),
    l1: Optional[str] = Query(None),
    l2: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    owner: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """共性问题台账分页（含关联措施数）。"""
    items = complaint_problems.list_problems(
        db, status=status or "", week=week or "", l1=l1 or "", l2=l2 or "",
        source_type=source_type or "", keyword=keyword or "", owner=owner or "",
        limit=page_size, offset=(page - 1) * page_size,
    )
    return success({"items": items, "page": page, "page_size": page_size})


@router.get("/problems/candidates")
def list_candidates(db: Session = Depends(get_db)):
    """候选确认区（status=candidate，按更新时间倒序）。"""
    return success({"items": complaint_problems.list_problems(db, status="candidate")})


@router.post("/problems/scan")
def scan_problems(
    db: Session = Depends(get_db),
    week: Optional[str] = Query(None, description="周次（默认库内最新周）"),
    dry_run: bool = Query(True, description="默认仅预览不落库（阈值调优用）"),
):
    """手动重扫候选共性问题（R1-R4 规则；幂等，同场景在办只累加不新建）。"""
    try:
        return success(complaint_problems.scan_candidates(db, week=week, dry_run=dry_run))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/problems/closure-suggestions")
def closure_suggestions(db: Session = Depends(get_db)):
    """闭环建议清单（只读：措施全生效+连续零复发；人工确认后才 closed）。"""
    return success({"items": complaint_problems.closure_suggestions(db)})


@router.post("/problems/urge-preview")
def problems_urge(body: ProblemUrgeIn, db: Session = Depends(get_db)):
    """问题级督办（复用 complaint_action_urge 邮件场景；dry_run 默认，
    真发须前端显式 confirm_send=True）。"""
    from datetime import date as _date
    from services.complaint import urge_candidates
    from services.task_center import task_center_service

    problems = complaint_problems.list_problems(db, status="open,resolving")
    by_problem = {p["problem_no"]: p for p in problems}
    overdue_map = {c["action_no"]: c for c in urge_candidates(db)}
    candidates = []
    for p in problems.values():
        linked = complaint_problems.linked_actions(db, p["problem_no"])
        has_overdue = any(la["action_no"] in overdue_map for la in linked)
        if has_overdue or p["reopen_flag"] or p["active_weeks"] >= 12:
            for la in linked:
                if la["action_no"] not in overdue_map:
                    continue
                candidates.append({**overdue_map[la["action_no"]],
                                   "_problem": p})
    if not candidates:
        return success({"sent": [], "skipped": "无待督办的问题关联措施"})

    today = _date.today()
    by_owner: dict = {}
    for c in candidates:
        p = c["_problem"]
        owners = split_owners(c.get("owner") or "") or ["未指派"]
        for o in owners:
            flags: dict = {"is_overdue": False, "is_due_soon": False}
            due = c.get("due_date")
            if due:
                d = due if isinstance(due, _date) else _date.fromisoformat(str(due)[:10])
                if d < today:
                    flags["is_overdue"] = True
                elif (d - today).days <= 3:
                    flags["is_due_soon"] = True
            by_owner.setdefault(o, []).append({
                "title": f"[{p['problem_no']}] {p['title']}｜[{c['action_no']}] {c.get('title') or ''}"[:200],
                "source_label": "客诉共性问题",
                "owner": o,
                "created_at": "",
                "due_date": str(due)[:10] if due else "",
                "status_label": c.get("status") or "",
                "priority": "P1",
                "description": (
                    f"共性问题：{p['problem_no']}（{p['status']}）；"
                    f"在办 {p['active_weeks']} 周；当周单量 {p['week_cnt']}；"
                    f"累计复发 {p['recur_cnt']} 单"
                    + ("；⚠ 已闭环问题再次出现，建议重开" if p["reopen_flag"] else "")
                ),
                **flags,
            })

    results = []
    for owner, tasks in by_owner.items():
        if owner == "未指派":
            results.append({"owner": owner, "skipped": "措施未指派责任人，无法督办"})
            continue
        resolved = task_center_service.resolve_contacts([owner])
        to_addr = resolved.get(owner)
        if not to_addr:
            results.append({"owner": owner, "skipped": f"收件人邮箱解析失败（{owner}）"})
            continue
        r = dispatch_email(
            db=db, to=[to_addr],
            scene="complaint_action_urge",
            variables={"tasks": tasks, "recipient_name": owner},
            fields={"tasks": tasks},
            recipient_name=owner,
            email_type="pmwb_complaint_urge",
            req_id=";".join(t["title"].split("]")[0][1:] for t in tasks[:5])[:64],
            req_name=f"客诉共性问题督办（{len(tasks)} 项）",
            ref_type="complaint_action",
            ref_id=tasks[0]["title"].split("]")[0][1:],
            raise_on_error=False,
            confirm_send=body.confirm_send,
        )
        results.append({
            "owner": owner, "to": to_addr, "task_cnt": len(tasks),
            "dry_run": bool(r.get("dry_run")), "success": r.get("success"),
            "record_id": r.get("record_id"), "subject": r.get("subject"),
        })
    return success({"sent": results, "total_candidates": len(candidates)})


@router.post("/problems")
def create_problem(body: ProblemCreateIn, db: Session = Depends(get_db)):
    """手工立问题（source_type=manual；同场景在办问题已存在则拒绝）。"""
    row = db.execute(text(
        "SELECT parent_name FROM pmwb_complaint_category WHERE level = 2 AND name = :n"
    ), {"n": body.category_l2}).scalar()
    if not row:
        raise HTTPException(status_code=400, detail=f"二级场景不存在于字典：{body.category_l2}")
    inflight = complaint_problems.list_problems(db, status="candidate,open,resolving",
                                                l2=body.category_l2)
    if inflight:
        raise HTTPException(
            status_code=400,
            detail=f"该场景已有在办问题 {inflight[0]['problem_no']}（同一场景至多一条在办问题）")
    week = complaint_metrics.latest_week(db) or datetime.now().strftime("%Y-W%W")
    no = complaint_problems._next_problem_no(db, week)
    now_ts = datetime.now()
    db.execute(text("""
        INSERT INTO pmwb_complaint_problem
            (problem_no, title, category_l1, category_l2, source_type, rule_hits, status,
             first_week, last_week, owner, note, created_at, updated_at)
        VALUES (:no, :title, :l1, :l2, 'manual', 'manual', :st,
                :wk, :wk, :owner, :note, :now_ts, :now_ts)
    """), {"no": no, "title": body.title, "l1": row, "l2": body.category_l2,
           "st": "open" if body.owner else "candidate", "wk": week,
           "owner": body.owner or None, "note": body.note, "now_ts": now_ts})
    if body.owner:
        db.execute(text(
            "UPDATE pmwb_complaint_problem SET confirm_by = 'manual', confirm_at = :at "
            "WHERE problem_no = :no"
        ), {"at": now_ts, "no": no})
    db.commit()
    return success(complaint_problems.get_problem(db, no))


@router.get("/problems/{problem_no}")
def get_problem(problem_no: str, db: Session = Depends(get_db)):
    """问题详情：基础字段 + 关联措施。"""
    p = complaint_problems.get_problem(db, problem_no)
    if not p:
        raise HTTPException(status_code=404, detail=f"问题不存在：{problem_no}")
    p["trajectory"] = complaint_problems.weekly_trajectory(db, problem_no)
    return success(p)


@router.put("/problems/{problem_no}")
def update_problem(problem_no: str, body: ProblemUpdateIn, db: Session = Depends(get_db)):
    """编辑问题基础字段（不含 status）。"""
    p = complaint_problems.get_problem(db, problem_no)
    if not p:
        raise HTTPException(status_code=404, detail=f"问题不存在：{problem_no}")
    sets = ["updated_at = :now_ts"]
    params: dict = {"no": problem_no, "now_ts": datetime.now()}
    for col, val in (("title", body.title), ("category_l1", body.category_l1),
                     ("owner", body.owner), ("note", body.note)):
        if val is not None:
            sets.append(f"{col} = :{col}")
            params[col] = val
    db.execute(text(
        f"UPDATE pmwb_complaint_problem SET {', '.join(sets)} WHERE problem_no = :no"
    ), params)
    db.commit()
    return success(complaint_problems.get_problem(db, problem_no))


@router.patch("/problems/{problem_no}/status")
def change_problem_status(problem_no: str, body: ProblemStatusIn,
                          db: Session = Depends(get_db)):
    """问题状态流转（status_registry complaint_problem 域校验；闭环须结论必填）。

    问题不入任务中心（可执行单元是措施），故自设流转端点。
    """
    try:
        return success(complaint_problems.update_status(db, problem_no, body.status, {
            "owner": body.owner, "conclusion": body.conclusion,
            "closed_week": body.closed_week, "note": body.note,
        }))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/problems/{problem_no}/confirm")
def confirm_problem(problem_no: str, body: ProblemConfirmIn, db: Session = Depends(get_db)):
    """候选确认：open（入账）/ merge（合并，归因改写+计数吸收）/ ignore（忽略）。"""
    try:
        return success(complaint_problems.confirm(
            db, problem_no, body.decision, owner=body.owner,
            merged_into=body.merged_into, note=body.note or "",
            confirm_by=body.confirm_by,
        ))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/problems/{problem_no}/actions")
def link_problem_action(problem_no: str, body: ProblemActionLinkIn,
                        db: Session = Depends(get_db)):
    """关联措施到问题（candidate 不可关联；跨场景给 warning 不硬拦）。"""
    try:
        return success(complaint_problems.link_action(
            db, problem_no, body.action_no, is_primary=body.is_primary,
            linked_by="manual", note=body.note or "",
        ))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/problems/{problem_no}/actions/{action_no}")
def unlink_problem_action(problem_no: str, action_no: str, db: Session = Depends(get_db)):
    """解除问题↔措施关联。"""
    complaint_problems.unlink_action(db, problem_no, action_no)
    return success({"problem_no": problem_no, "action_no": action_no, "unlinked": True})


# ── 每周导入 ─────────────────────────────────────────────────
@router.post("/import")
async def import_weekly(
    db: Session = Depends(get_db),
    file: UploadFile = File(..., description="小信工单导出 xlsx"),
    with_report: bool = Form(False, description="导入后是否直接生成周报"),
    with_pdf: bool = Form(True, description="周报是否导出 PDF"),
):
    """页面上传 xlsx 一键处理：归档 → 去重入库 → 分类 → 批量簇标记 →（可选）出周报。"""
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 导出文件")

    # 落临时文件（服务层 ingest 按周归档时会再复制一份永久留底）
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        ingest_info = ingest_file(db, tmp_path, import_batch=datetime.now().strftime("%Y%m%d%H%M%S"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败：{e}")
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="临时文件丢失，请重试")
    finally:
        tmp_path.unlink(missing_ok=True)

    from services.complaint.ingest import reclassify
    rc = reclassify(db)

    # 共性问题闭环：扫描候选 → 回写归因 → 重算周轨迹（本次导入覆盖的周）
    problems_summary = complaint_problems.after_import(db, weeks=ingest_info.get("weeks"))

    result = {
        "ingest": ingest_info,
        "reclassify": rc,
        "problems": problems_summary,
        "report": None,
    }
    if with_report:
        try:
            r = complaint_pipeline.run(db, file=None, week=None, pdf=with_pdf)
            pdf_ok = Path(r["pdf"]).exists() if r["pdf"] else False
            result["report"] = {
                "week": r["week"], "total": r["total"], "html": r["html"],
                "pdf": r["pdf"] if pdf_ok else "", "pdf_generated": pdf_ok,
            }
        except (ValueError, RuntimeError) as e:
            # 周报失败不吞导入结果
            result["report"] = {"error": str(e)}
    return success(result)
