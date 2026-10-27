"""客诉周报一键流水线 —— 每周收到导出文件后跑这一条命令即可。

用法（backend 目录下）：
    python -m scripts.complaint.run_weekly "D:\\path\\小信工单导出.xlsx"
    python -m scripts.complaint.run_weekly                       # 不导新数据，仅按库内最新周出报告
    python -m scripts.complaint.run_weekly <file> --week 2026-W43 --no-pdf

执行顺序：归档入库 → 按字典重跑分类 → 重算批量簇/复发 → 计算指标 → 渲染 HTML → 导出 PDF。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence

from scripts.complaint import config as C
from scripts.complaint import metrics, report
from scripts.complaint.ingest import ingest_file, reclassify, refresh_derived


def export_pdf(html_path: Path, pdf_path: Path) -> bool:
    """调用本地 puppeteer 导出 PDF（打印媒体下先重绘图表，避免裁切）。"""
    js = Path(__file__).parent / "pdf_export.js"
    if not js.exists():
        print("[WARN] 缺少 pdf_export.js，跳过 PDF 导出")
        return False
    proc = subprocess.run(
        ["node", str(js), str(html_path), str(pdf_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        print("[WARN] PDF 导出失败：", (proc.stderr or proc.stdout)[-400:])
        return False
    print((proc.stdout or "").strip())
    return True


def run(file: Optional[str] = None, week: Optional[str] = None, pdf: bool = True) -> dict:
    from db.base import SessionLocal

    db = SessionLocal()
    try:
        info = {}
        if file:
            info = ingest_file(db, Path(file))
            print(f"入库完成：新增 {info['inserted']} 条（跳过重复 {info['skipped_duplicate']}），"
                  f"归档 {info['archive']}")
            rc = reclassify(db)
            print(f"分类重跑：{rc['scanned']} 条")
        else:
            refresh_derived(db)

        m = metrics.collect(db, week)
        html_path = report.write_report(m)
        print(f"报告已生成：{html_path}")

        pdf_path = html_path.with_suffix(".pdf")
        if pdf:
            export_pdf(html_path, pdf_path)
        return {"week": m["week"], "total": m["total"], "html": str(html_path),
                "pdf": str(pdf_path) if pdf else ""}
    finally:
        db.close()


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="客诉周报一键流水线")
    ap.add_argument("file", nargs="?", help="本周导出的 xlsx（不传则用库内数据）")
    ap.add_argument("--week", help="指定周（默认取库内最新周）")
    ap.add_argument("--no-pdf", action="store_true", help="只出 HTML，不导 PDF")
    args = ap.parse_args(argv)

    result = run(args.file, args.week, pdf=not args.no_pdf)
    print("─" * 56)
    print(f"周次 {result['week']}｜总量 {result['total']} 单")
    print(f"HTML：{result['html']}")
    if result["pdf"]:
        print(f"PDF ：{result['pdf']}")
    print("─" * 56)
    return 0


if __name__ == "__main__":
    sys.exit(main())
