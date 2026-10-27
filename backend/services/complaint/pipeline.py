"""客诉周报一键流水线 —— 服务层实现（scripts/complaint/run_weekly.py 是其 CLI 薄封装）。

执行顺序：归档入库 → 按字典重跑分类 → 重算批量簇/复发 → 计算指标 → 渲染 HTML → 导出 PDF。
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, Optional

from sqlalchemy.orm import Session

from services.complaint import config as C
from services.complaint import metrics, report
from services.complaint.ingest import ingest_file, reclassify, refresh_derived

PDF_EXPORT_JS = Path(__file__).resolve().parents[2] / "scripts" / "complaint" / "pdf_export.js"


def export_pdf(html_path: Path, pdf_path: Path) -> bool:
    """调用本地 puppeteer 导出 PDF（打印媒体下先重绘图表，避免裁切）。"""
    if not PDF_EXPORT_JS.exists():
        print("[WARN] 缺少 pdf_export.js，跳过 PDF 导出")
        return False
    proc = subprocess.run(
        ["node", str(PDF_EXPORT_JS), str(html_path), str(pdf_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        print("[WARN] PDF 导出失败：", (proc.stderr or proc.stdout)[-400:])
        return False
    print((proc.stdout or "").strip())
    return True


def run(db: Session, file: Optional[str] = None, week: Optional[str] = None,
        pdf: bool = True) -> Dict:
    """周报流水线主入口。file 为空则不导新数据，仅按库内数据出报告。"""
    info: Dict = {}
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
            "pdf": str(pdf_path) if pdf else "", "ingest": info}
