"""客诉周报一键流水线 —— 服务层实现（scripts/complaint/run_weekly.py 是其 CLI 薄封装）。

执行顺序：归档入库 → 按字典重跑分类 → 重算批量簇/复发 → 计算指标 → 渲染 HTML → 导出 PDF。
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, Optional

from sqlalchemy.orm import Session

from services.complaint import config as C
from services.complaint import metrics, problems, report
from services.complaint.ingest import ingest_file, refresh_derived

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
    """周报流水线主入口。file 为空则不导新数据，仅按库内数据出报告。

    LLM 主导归类：流水线内**同步**执行（CLI 跑批需等待归类完成后再出报告）；
    API 导入路径则由 ingest_file 起后台线程异步归类。
    """
    from services.complaint.llm_classify import run_llm_classify
    from services.complaint.rootcause import run_rootcause
    from services.complaint.rootcause_lib import auto_merge_similar, build_clusters

    info: Dict = {}
    if file:
        info = ingest_file(db, Path(file), run_llm=False)
        print(f"入库完成：新增 {info['inserted']} 条（跳过重复 {info['skipped_duplicate']}），"
              f"归档 {info['archive']}")
        rc = run_llm_classify(db, force=False)
        print(f"LLM 归类：更新 {rc['updated']} 条（自动 {rc['auto']}，低置信待人工 {rc['low_conf']}，"
              f"失败 {rc['failed']}）；{rc['notice']}")
        refresh_derived(db, weeks=info.get("weeks") or None)
    else:
        refresh_derived(db)

    # 根因层（2026-11-03）：增量归纳 → 归并进根因库 → 跨桶消重
    # 根因是批量投诉识别与方案制定的基础数据，故放在指标计算之前，且失败不阻断周报
    try:
        rcs = run_rootcause(db, force=False)
        print(f"根因归纳：扫描 {rcs['scanned']} 单（已归纳 {rcs['ok']}，待人工 {rcs['low']}，"
              f"重写 {rcs['rewritten']}）；{rcs['notice']}")
        if rcs.get("saved"):
            cl = build_clusters(db)
            mg = auto_merge_similar(db)
            print(f"根因库：归并 {cl['assigned']} 单 → {len(cl['new_clusters'])} 簇"
                  f"（{cl['buckets']} 个桶）；跨桶消重合并 {mg.get('merged', 0)} 单")
    except Exception as e:  # 根因失败不阻断周报
        print(f"[WARN] 根因归纳异常: {e}")

    # 共性问题闭环（幂等）：候选扫描 → 归因回写 → 周轨迹重算
    try:
        p_weeks = info.get("weeks") if info else ([week] if week else None)
        p_summary = problems.after_import(db, weeks=p_weeks)
        if p_summary.get("created") or p_summary.get("updated"):
            print(f"共性问题：新建候选 {p_summary['created']}，"
                  f"归并更新 {p_summary['updated']}，待重开 {p_summary['reopen']}")
    except Exception as e:  # 闭环失败不阻断周报主流程
        print(f"[WARN] 共性问题闭环处理异常: {e}")

    m = metrics.collect(db, week)
    # 周报第七章：共性问题闭环台账（只读查询，不进 metrics 口径）
    try:
        problem_rows = problems.list_for_report(db, m["week"])
    except Exception:
        problem_rows = None
    # 全周期全貌：唯一实现 overall.collect，失败不阻断周报（与根因/台账同样降级）；
    # 拿不到时模板输出「全貌暂缺」提示块，不静默留一章空数据。
    try:
        from services.complaint import overall as complaint_overall
        ov = complaint_overall.collect(db)
    except Exception as e:
        print(f"[WARN] 全貌聚合异常，周报将标注全貌暂缺: {e}")
        ov = None
    html_path = report.write_report(m, problems=problem_rows, overall=ov)
    print(f"报告已生成：{html_path}")

    pdf_path = html_path.with_suffix(".pdf")
    if pdf:
        export_pdf(html_path, pdf_path)
    return {"week": m["week"], "total": m["total"], "html": str(html_path),
            "pdf": str(pdf_path) if pdf else "", "ingest": info}
