"""客诉根因归纳与根因库（CLI 薄封装）—— 实现见 services/complaint/rootcause*.py。

用法（backend 目录下）：
    python -m scripts.complaint.rootcause analyze              # 增量：只分析待分析工单
    python -m scripts.complaint.rootcause analyze --force      # 全量重跑（不覆盖人工确认）
    python -m scripts.complaint.rootcause analyze --limit 20   # 限量
    python -m scripts.complaint.rootcause cluster              # 归并进根因库（新簇为候选）
    python -m scripts.complaint.rootcause status               # 根因覆盖率/质量率
    python -m scripts.complaint.rootcause clusters             # 列根因库
    python -m scripts.complaint.rootcause top --week 2026-W44  # 当周簇排名（压降空间）
"""

from __future__ import annotations

import argparse
import json
from typing import Optional, Sequence

from db.base import SessionLocal
from services.complaint import rootcause_lib as lib
from services.complaint import rootcause as rc


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="客诉根因归纳与根因库")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_an = sub.add_parser("analyze", help="AI 根因归纳")
    p_an.add_argument("--force", action="store_true", help="重跑全部非人工确认工单")
    p_an.add_argument("--limit", type=int, default=None)

    p_cl = sub.add_parser("cluster", help="归并进根因库")
    p_cl.add_argument("--limit", type=int, default=None)

    sub.add_parser("rejudge", help="按当前门禁/阈值重判低置信单（零 LLM 成本）")

    sub.add_parser("status", help="根因归纳状态")

    p_ls = sub.add_parser("clusters", help="列根因库")
    p_ls.add_argument("--status", default="")
    p_ls.add_argument("--keyword", default="")
    p_ls.add_argument("--page", type=int, default=1)
    p_ls.add_argument("--page-size", type=int, default=30)

    p_top = sub.add_parser("top", help="簇排名（压降空间）")
    p_top.add_argument("--week", default="")
    p_top.add_argument("--limit", type=int, default=20)

    p_bc = sub.add_parser("batch", help="批量投诉识别（根因口径）")
    p_bc.add_argument("--week", default="")
    p_bc.add_argument("--min-cnt", type=int, default=3)

    args = ap.parse_args(argv)
    db = SessionLocal()
    try:
        if args.cmd == "analyze":
            out = rc.run_rootcause(db, force=args.force, limit=args.limit)
        elif args.cmd == "cluster":
            out = lib.build_clusters(db, limit=args.limit)
        elif args.cmd == "rejudge":
            out = rc.rejudge(db)
        elif args.cmd == "status":
            out = rc.rootcause_status(db)
        elif args.cmd == "clusters":
            out = lib.list_clusters(db, status=args.status, keyword=args.keyword,
                                    page=args.page, page_size=args.page_size)
        elif args.cmd == "top":
            out = lib.top_clusters(db, week=args.week, limit=args.limit)
        else:
            out = lib.batch_clusters(db, week=args.week, min_cnt=args.min_cnt)
    finally:
        db.close()
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
