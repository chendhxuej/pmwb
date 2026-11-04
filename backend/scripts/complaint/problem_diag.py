"""方案 v4.2 只读诊断（CLI 薄封装）—— 实现见 services/complaint/problem_*.py。

用法（backend 目录下）：
    python -m scripts.complaint.problem_diag                 # 全库 L1 逐单判定
    python -m scripts.complaint.problem_diag --limit 50     # 限量
    python -m scripts.complaint.problem_diag --repeat       # 跑两遍验证可复现

只读、不写库、不调用语义通道；通道不可用时输出「待自动补跑」清单，绝不转人工队列。
"""

from __future__ import annotations

import argparse
import json
import logging
import os

# 与 problem.py 一致：CLI 只输出纯 JSON，关掉 SQL echo 并压掉引擎日志
os.environ["DEBUG"] = "false"

from db.base import SessionLocal  # noqa: E402
from services.complaint.problem_point import scan_tickets  # noqa: E402

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def main() -> None:
    ap = argparse.ArgumentParser(description="客诉问题点 v4.2 只读诊断")
    ap.add_argument("--limit", type=int, default=None, help="只扫描前 N 单")
    ap.add_argument("--repeat", action="store_true", help="同输入跑两遍，验证可复现")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        first = scan_tickets(db, limit=args.limit)
        if args.repeat:
            second = scan_tickets(db, limit=args.limit)
            same = first == second
            first["reproducible"] = same
        print(json.dumps(first, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
