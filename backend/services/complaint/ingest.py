"""客诉工单入库 —— 导出文件归档 → 解析 → 去重入库 → 分类 → 批量簇/复发标记。

用法（在 backend 目录下执行）：
    python -m scripts.complaint.ingest "D:\\path\\小信工单上周全部明细.xlsx"
    python -m scripts.complaint.ingest <file> --dry-run     # 只解析不入库

设计要点：
  - 原始文件按自然周归档到 data/complaint/YYYY-Www/，永久留底可溯源；
  - ticket_no（BOMC流水号）唯一去重，重复导入天然幂等；
  - 分类走字典表规则，classify_by 标记 auto，人工校正后改 manual（校正不被覆盖）；
  - 批量簇/复发为派生字段，每次导入后整表重算，保证口径一致。
"""

from __future__ import annotations

import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from openpyxl import load_workbook
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.complaint import config as C
from services.complaint.classify import load_dictionary


# ── 工具 ──────────────────────────────────────────────────────
def week_key(dt: Optional[datetime]) -> str:
    """自然周（ISO 周）标识，如 2026-W44。"""
    if not dt:
        return ""
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


def _to_dt(v) -> Optional[datetime]:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.replace(tzinfo=None)
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    s = str(v).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S",
                "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _s(v, limit: int = 255) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return s[:limit]


# ── 解析 ──────────────────────────────────────────────────────
def read_rows(path: Path) -> Tuple[List[Dict], List[str]]:
    """读取导出文件，返回 [{列名: 值}] 与表头列表。"""
    wb = load_workbook(filename=str(path), read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows_iter = ws.iter_rows(values_only=True)
    header = [str(c).strip() if c is not None else "" for c in next(rows_iter)]
    out: List[Dict] = []
    for values in rows_iter:
        if values is None or all(v is None or str(v).strip() == "" for v in values):
            continue
        out.append(dict(zip(header, values)))
    wb.close()
    return out, header


def archive_source(path: Path, week: str) -> Path:
    """原始导出按自然周归档留底。"""
    target_dir = C.ARCHIVE_ROOT / (week or "unknown")
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / path.name
    if not target.exists():
        shutil.copy2(path, target)
    return target


# ── 入库 ──────────────────────────────────────────────────────
def ingest_file(db: Session, path: Path, import_batch: str = "") -> Dict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    rows, header = read_rows(path)
    missing = [c for c in C.COL_HEADER_CANDIDATES if c not in header]
    if missing:
        raise ValueError(f"导出文件缺少必需列：{missing}；实际表头={header}")

    dic = load_dictionary(db)
    existing = {r[0] for r in db.execute(text("SELECT ticket_no FROM pmwb_complaint_ticket"))}

    batch = import_batch or datetime.now().strftime("%Y%m%d%H%M%S")
    archive_path = None
    inserted = skipped = 0
    weeks = set()

    for row in rows:
        ticket_no = _s(row.get(C.COL_TICKET_NO), 64)
        if not ticket_no:
            skipped += 1
            continue
        if ticket_no in existing:
            skipped += 1
            continue

        created = _to_dt(row.get(C.COL_CREATED))
        week = week_key(created)
        if archive_path is None and week:
            archive_path = archive_source(path, week)
        weeks.add(week)

        content = _s(row.get(C.COL_CONTENT), 20000)
        solution = _s(row.get(C.COL_SOLUTION), 20000)
        l1, l2, _hit = dic.classify(content, solution)

        dispatch_raw = row.get(C.COL_DISPATCH)
        try:
            dispatch = int(float(dispatch_raw)) if dispatch_raw not in (None, "") else 1
        except (TypeError, ValueError):
            dispatch = 1

        db.execute(text("""
            INSERT INTO pmwb_complaint_ticket
                (ticket_no, week, created_time, city, channel, appeal_category, biz_attr,
                 content, solution_history, handler, handle_unit, dispatch_count, status,
                 category_l1, category_l2, classify_by, cluster_key, is_batch, is_recur,
                 source_file, import_batch, created_at, updated_at)
            VALUES
                (:ticket_no, :week, :created_time, :city, :channel, :appeal, :biz_attr,
                 :content, :solution, :handler, :unit, :dispatch, :status,
                 :l1, :l2, 'auto', NULL, 0, 0, :src, :batch, NOW(), NOW())
        """), {
            "ticket_no": ticket_no, "week": week, "created_time": created,
            "city": _s(row.get(C.COL_CITY), 64), "channel": _s(row.get(C.COL_CHANNEL), 64),
            "appeal": _s(row.get(C.COL_APPEAL), 64), "biz_attr": _s(row.get(C.COL_BIZ_ATTR), 64),
            "content": content, "solution": solution,
            "handler": _s(row.get(C.COL_HANDLER), 255), "unit": _s(row.get(C.COL_UNIT), 255),
            "dispatch": dispatch, "status": _s(row.get(C.COL_STATUS), 32),
            "l1": l1, "l2": l2, "src": path.name, "batch": batch,
        })
        existing.add(ticket_no)
        inserted += 1

    db.commit()

    derived = refresh_derived(db, weeks=sorted(w for w in weeks if w))

    return {
        "file": path.name,
        "archive": str(archive_path) if archive_path else "",
        "parsed": len(rows),
        "inserted": inserted,
        "skipped_duplicate": skipped,
        "weeks": sorted(w for w in weeks if w),
        "batch": batch,
        "clusters": derived["clusters"],
        "recur": derived["recur"],
    }


# ── 派生字段重算 ──────────────────────────────────────────────
def refresh_derived(db: Session, weeks: Optional[Sequence[str]] = None,
                    threshold: int = C.BATCH_DAILY_THRESHOLD) -> Dict:
    """重算批量簇标识与复发标记（整表或指定周）。

    批量簇：同二级场景 + 同自然日单量 >= 阈值 → cluster_key='场景@日期'；
    复发：措施台账该场景已有生效日期，且工单创建时间在其之后 → is_recur=1。
    先清零再打标，避免历史标记残留。

    实现说明：聚合在 Python 侧完成后逐单更新（SQL 方言可移植，
    被 API /correct-category 在测试库 SQLite 上调用；周数据量 ≤ 千级，性能无虞）。
    """
    f_week = ""
    params: Dict = {}
    if weeks:
        for i, w in enumerate(weeks):
            params[f"w{i}"] = w
        in_list = ",".join(f":w{i}" for i in range(len(weeks)))
        f_week = f" AND week IN ({in_list})"

    rows = db.execute(text(
        "SELECT id, category_l2, created_time FROM pmwb_complaint_ticket "
        "WHERE 1 = 1" + f_week
    ), params).fetchall()

    # 1) 批量异常簇：清零 → 按场景+自然日计数打标
    db.execute(text(
        "UPDATE pmwb_complaint_ticket SET cluster_key = NULL, is_batch = 0 WHERE 1 = 1" + f_week
    ), params)

    from collections import Counter
    day_counter: Counter = Counter()
    for _tid, l2, created in rows:
        if l2 and created:
            day_counter[(l2, created.date())] += 1

    cluster_updates = []
    for tid, l2, created in rows:
        if l2 and created and day_counter[(l2, created.date())] >= threshold:
            cluster_updates.append(
                {"id": tid, "ck": f"{l2}@{created.date().isoformat()}"})
    if cluster_updates:
        db.execute(text(
            "UPDATE pmwb_complaint_ticket SET cluster_key = :ck, is_batch = 1 WHERE id = :id"
        ), cluster_updates)

    # 2) 措施上线后同类复发：清零 → 生效措施匹配同场景打标
    db.execute(text(
        "UPDATE pmwb_complaint_ticket SET is_recur = 0 WHERE 1 = 1" + f_week
    ), params)
    go_lives = db.execute(text(
        "SELECT category_l2, go_live_date FROM pmwb_complaint_action "
        "WHERE go_live_date IS NOT NULL "
        "AND status IN ('verifying', 'effective', 'ineffective')"
    )).fetchall()
    recur_map: Dict[str, list] = {}
    for l2, g in go_lives:
        recur_map.setdefault(l2 or "", []).append(g)

    recur_updates = []
    for tid, l2, created in rows:
        if l2 and created:
            for g in recur_map.get(l2, []):
                g_dt = g if isinstance(g, datetime) else datetime.combine(g, datetime.min.time())
                if created >= g_dt:
                    recur_updates.append({"id": tid})
                    break
    if recur_updates:
        db.execute(text(
            "UPDATE pmwb_complaint_ticket SET is_recur = 1 WHERE id = :id"
        ), recur_updates)

    db.commit()

    clusters = sum(1 for k in day_counter.values() if k >= threshold)
    recur = len(recur_updates)
    return {"clusters": int(clusters), "recur": int(recur)}


def reclassify(db: Session) -> Dict:
    """按当前字典重跑分类（字典调口径后无需重新导入）。

    仅覆盖 classify_by='auto' 的工单，人工校正（manual）一律不动。
    """
    dic = load_dictionary(db, use_cache=False)
    rows = db.execute(text(
        "SELECT id, content, solution_history FROM pmwb_complaint_ticket WHERE classify_by = 'auto'"
    )).fetchall()

    updated = 0
    for tid, content, solution in rows:
        l1, l2, _hit = dic.classify(content or "", solution or "")
        db.execute(text(
            "UPDATE pmwb_complaint_ticket SET category_l1 = :l1, category_l2 = :l2 WHERE id = :id"
        ), {"l1": l1, "l2": l2, "id": tid})
        updated += 1
    db.commit()
    return {"scanned": len(rows), "updated": updated}


