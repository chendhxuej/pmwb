"""客诉 v4.2 全链 CLI（薄封装）—— 实现见 services/complaint/problem_pipeline.py。

用法（backend 目录下）：
    python -m scripts.complaint.problem status                # 验收状态/待补跑规模
    python -m scripts.complaint.problem run                   # 只读演练（默认，不写库）
    python -m scripts.complaint.problem run --apply           # 落库（含自动补跑）
    python -m scripts.complaint.problem run --limit 50        # 限量演练
    python -m scripts.complaint.problem run --force --apply   # 全量重算（D7 用）
    python -m scripts.complaint.problem rerun-pending --apply # 通道恢复后补跑
    python -m scripts.complaint.problem classes               # 问题点类
    python -m scripts.complaint.problem unclassified          # 未归类清单

纪律：默认 dry_run，只有显式 --apply 才写库；语义通道不可用时链路照常跑完，
输出「待自动补跑」清单，绝不转人工队列、绝不降级为关键词猜测。
"""

from __future__ import annotations

import argparse
import json
import logging
import os

# CLI 输出必须是纯 JSON：关掉 SQL echo（环境变量优先级高于 .env），
# 并在引擎创建之后再压一次日志级别（create_engine(echo=True) 会重置 logger level）。
os.environ["DEBUG"] = "false"

from db.base import SessionLocal  # noqa: E402
from services.complaint import problem_pipeline  # noqa: E402

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def _out(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def main() -> None:
    ap = argparse.ArgumentParser(description="客诉问题点 v4.2 全链编排")
    sub = ap.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="一键全链（默认只读演练）")
    run.add_argument("--apply", action="store_true", help="落库（默认只演练）")
    run.add_argument("--force", action="store_true", help="忽略已存 L1 结论，全量重算")
    run.add_argument("--limit", type=int, default=0, help="只跑前 N 单（0=全量）")
    run.add_argument("--no-semantic", action="store_true", help="禁用语义通道（纯确定性演练）")
    run.add_argument("--max-batches", type=int, default=0,
                     help="最多发几批语义调用（0=不限；演练建议 1~2）")

    rerun = sub.add_parser("rerun-pending", help="对待自动补跑单重跑全链")
    rerun.add_argument("--apply", action="store_true")

    sub.add_parser("status", help="最近一次验收与计数")
    cls = sub.add_parser("classes", help="问题点类列表")
    cls.add_argument("--status", default="")
    cls.add_argument("--keyword", default="")
    cls.add_argument("--page", type=int, default=1)
    cls.add_argument("--page-size", type=int, default=20)
    unc = sub.add_parser("unclassified", help="未归类清单")
    unc.add_argument("--reason", default="")
    unc.add_argument("--page", type=int, default=1)
    unc.add_argument("--page-size", type=int, default=20)

    args = ap.parse_args()
    db = SessionLocal()
    try:
        if args.cmd == "run":
            _out(problem_pipeline.run_full(
                db, dry_run=not args.apply, force=args.force,
                limit=(args.limit or None), allow_semantic=not args.no_semantic,
                max_semantic_batches=args.max_batches))
        elif args.cmd == "rerun-pending":
            _out(problem_pipeline.rerun_pending(db, dry_run=not args.apply))
        elif args.cmd == "status":
            _out(problem_pipeline.status(db))
        elif args.cmd == "classes":
            _out(problem_pipeline.list_classes(
                db, status_filter=args.status, keyword=args.keyword,
                page=args.page, page_size=args.page_size))
        elif args.cmd == "unclassified":
            _out(problem_pipeline.list_unclassified(
                db, reason=args.reason, page=args.page, page_size=args.page_size))
    finally:
        db.close()


if __name__ == "__main__":
    main()
