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

import argparse
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from openpyxl import load_workbook
from sqlalchemy import text
from sqlalchemy.orm import Session

from scripts.complaint import config as C
from scripts.complaint.classify import load_dictionary


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
    """
    params: Dict = {"threshold": threshold}
    f_plain = ""   # 无别名表过滤条件
    f_alias = ""   # 别名 t 的过滤条件
    if weeks:
        for i, w in enumerate(weeks):
            params[f"w{i}"] = w
        in_list = ",".join(f":w{i}" for i in range(len(weeks)))
        f_plain = f" AND week IN ({in_list})"
        f_alias = f" AND t.week IN ({in_list})"

    # 1) 批量异常簇
    db.execute(text(
        f"UPDATE pmwb_complaint_ticket SET cluster_key = NULL, is_batch = 0 WHERE 1 = 1{f_plain}"
    ), params)
    db.execute(text(f"""
        UPDATE pmwb_complaint_ticket t
        JOIN (
            SELECT category_l2, DATE(created_time) AS d, COUNT(*) AS c
            FROM pmwb_complaint_ticket
            WHERE category_l2 IS NOT NULL AND category_l2 <> ''{f_plain}
            GROUP BY category_l2, DATE(created_time)
            HAVING COUNT(*) >= :threshold
        ) g ON g.category_l2 = t.category_l2 AND g.d = DATE(t.created_time)
        SET t.cluster_key = CONCAT(g.category_l2, '@', g.d), t.is_batch = 1
    """), params)

    # 2) 措施上线后同类复发
    db.execute(text(
        f"UPDATE pmwb_complaint_ticket SET is_recur = 0 WHERE 1 = 1{f_plain}"
    ), params)
    db.execute(text(f"""
        UPDATE pmwb_complaint_ticket t
        JOIN pmwb_complaint_action a
          ON a.category_l2 = t.category_l2
         AND a.go_live_date IS NOT NULL
         AND t.created_time >= a.go_live_date
         AND a.status IN ('verifying', 'effective', 'ineffective')
        SET t.is_recur = 1
        WHERE 1 = 1{f_alias}
    """), params)
    db.commit()

    clusters = db.execute(text(
        f"SELECT COUNT(DISTINCT cluster_key) FROM pmwb_complaint_ticket "
        f"WHERE cluster_key IS NOT NULL{f_plain}"
    ), params).scalar() or 0
    recur = db.execute(text(
        f"SELECT COUNT(*) FROM pmwb_complaint_ticket WHERE is_recur = 1{f_plain}"
    ), params).scalar() or 0
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


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="客诉工单导出文件入库")
    ap.add_argument("file", nargs="?", help="小信工单导出 xlsx 路径")
    ap.add_argument("--batch", default="", help="导入批次号（默认时间戳）")
    ap.add_argument("--dry-run", action="store_true", help="只解析不入库")
    ap.add_argument("--reclassify", action="store_true", help="仅按当前字典重跑分类（不导入文件）")
    args = ap.parse_args(argv)

    if args.reclassify:
        from db.base import SessionLocal as _SL
        _db = _SL()
        try:
            r = reclassify(_db)
            print(f"重跑分类：扫描 {r['scanned']} 条，更新 {r['updated']} 条")
        finally:
            _db.close()
        return 0

    if args.dry_run:
        rows, header = read_rows(Path(args.file))
        print(f"解析成功：{len(rows)} 行，列数 {len(header)}")
        return 0

    from db.base import SessionLocal
    db = SessionLocal()
    try:
        result = ingest_file(db, Path(args.file), args.batch)
    finally:
        db.close()

    print("─" * 56)
    print(f"文件      : {result['file']}")
    print(f"归档路径  : {result['archive'] or '（无有效创建时间，未归档）'}")
    print(f"解析/入库 : {result['parsed']} 行 / 新增 {result['inserted']} 条（重复跳过 {result['skipped_duplicate']}）")
    print(f"归属周    : {', '.join(result['weeks'])}")
    print(f"批量簇    : {result['clusters']} 个    复发标记：{result['recur']} 条")
    print("─" * 56)
    return 0


if __name__ == "__main__":
    sys.exit(main())
