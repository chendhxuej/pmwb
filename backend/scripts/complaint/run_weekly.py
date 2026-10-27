"""客诉周报一键流水线（CLI 薄封装）—— 实现见 services/complaint/pipeline.py。

用法（backend 目录下）：
    python -m scripts.complaint.run_weekly "D:\\path\\小信工单导出.xlsx"
    python -m scripts.complaint.run_weekly                       # 不导新数据，仅按库内最新周出报告
    python -m scripts.complaint.run_weekly <file> --week 2026-W43 --no-pdf
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from services.complaint.pipeline import export_pdf, run  # noqa: F401


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="客诉周报一键流水线")
    ap.add_argument("file", nargs="?", help="本周导出的 xlsx（不传则用库内数据）")
    ap.add_argument("--week", help="指定周（默认取库内最新周）")
    ap.add_argument("--no-pdf", action="store_true", help="只出 HTML，不导 PDF")
    args = ap.parse_args(argv)

    from db.base import SessionLocal
    db = SessionLocal()
    try:
        result = run(db, args.file, args.week, pdf=not args.no_pdf)
    finally:
        db.close()

    print("─" * 56)
    print(f"周次 {result['week']}｜总量 {result['total']} 单")
    print(f"HTML：{result['html']}")
    if result["pdf"]:
        print(f"PDF ：{result['pdf']}")
    print("─" * 56)
    return 0


if __name__ == "__main__":
    sys.exit(main())
