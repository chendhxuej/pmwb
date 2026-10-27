"""客诉工单入库（CLI 薄封装）—— 实现见 services/complaint/ingest.py。

用法（在 backend 目录下执行）：
    python -m scripts.complaint.ingest "D:\\path\\小信工单上周全部明细.xlsx"
    python -m scripts.complaint.ingest <file> --dry-run     # 只解析不入库
    python -m scripts.complaint.ingest --reclassify         # 按当前字典重跑分类
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from services.complaint.ingest import (  # noqa: F401
    archive_source,
    ingest_file,
    read_rows,
    reclassify,
    refresh_derived,
    week_key,
)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="客诉工单导出文件入库")
    ap.add_argument("file", nargs="?", help="小信工单导出 xlsx 路径")
    ap.add_argument("--batch", default="", help="导入批次号（默认时间戳）")
    ap.add_argument("--dry-run", action="store_true", help="只解析不入库")
    ap.add_argument("--reclassify", action="store_true", help="仅按当前字典重跑分类（不导入文件）")
    args = ap.parse_args(argv)

    from db.base import SessionLocal

    if args.reclassify:
        db = SessionLocal()
        try:
            r = reclassify(db)
            print(f"重跑分类：扫描 {r['scanned']} 条，更新 {r['updated']} 条")
        finally:
            db.close()
        return 0

    if args.dry_run:
        rows, header = read_rows(Path(args.file))
        print(f"解析成功：{len(rows)} 行，列数 {len(header)}")
        return 0

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
