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
from schemas.complaint import (
    ActionCreateIn,
    ActionUpdateIn,
    CategoryCorrectIn,
    CategoryEnabledIn,
    GoLiveIn,
    ReportGenIn,
)
from services.complaint import (
    actions as complaint_actions,
    classify as complaint_classify,
    metrics as complaint_metrics,
    pipeline as complaint_pipeline,
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

    cond = " AND ".join(where)
    total = db.execute(text(
        f"SELECT COUNT(*) FROM pmwb_complaint_ticket WHERE {cond}"
    ), params).scalar() or 0
    rows = db.execute(text(f"""
        SELECT id, ticket_no, week, created_time, city, channel, appeal_category, biz_attr,
               handler, handle_unit, dispatch_count, status, category_l1, category_l2,
               classify_by, cluster_key, is_batch, is_recur, linked_issue_no, remark,
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
    """登记措施（可选同步创建运营工单父子关联，进程内调用）。"""
    try:
        r = complaint_actions.add(
            db, body.l2, body.title, body.owner, body.due_date,
            body.acceptance, body.create_issue, body.desc,
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

    result = {
        "ingest": ingest_info,
        "reclassify": rc,
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
