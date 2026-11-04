"""客诉根因归纳与根因库（CLI 薄封装）—— 实现见 services/complaint/rootcause*.py。

用法（backend 目录下）：
    python -m scripts.complaint.rootcause analyze              # 增量：只分析待分析工单
    python -m scripts.complaint.rootcause analyze --force      # 全量重跑（不覆盖人工确认）
    python -m scripts.complaint.rootcause analyze --limit 20   # 限量
    python -m scripts.complaint.rootcause cluster              # 归并进根因库（新簇为候选）
    python -m scripts.complaint.rootcause status               # 根因覆盖率/质量率
    python -m scripts.complaint.rootcause clusters             # 列根因库
    python -m scripts.complaint.rootcause top --week 2026-W44  # 当周簇排名（压降空间）
    python -m scripts.complaint.rootcause known --week 2026-W44 # 已知/新增判定（核心 KPI）
    python -m scripts.complaint.rootcause relabel [--dry-run] [--only-missing]  # 簇模式标定（RC-2.0）
    python -m scripts.complaint.rootcause consolidate [--apply]  # 按三元组合并同键簇
    python -m scripts.complaint.rootcause health               # 簇健康度（簇数/单簇率/覆盖率）
    python -m scripts.complaint.rootcause closing              # 簇闭合校验
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

    p_kn = sub.add_parser("known", help="已知/新增判定回填（核心 KPI）")
    p_kn.add_argument("--week", default="", help="只刷指定周；空=全部重判")

    p_bc = sub.add_parser("batch", help="批量投诉识别（根因口径）")
    p_bc.add_argument("--week", default="")
    p_bc.add_argument("--min-cnt", type=int, default=3)

    p_rl = sub.add_parser("relabel", help="簇模式标定（RC-2.0：环节/机制/对象三要素）")
    p_rl.add_argument("--limit", type=int, default=None)
    p_rl.add_argument("--only-missing", action="store_true", help="只标未标定的簇（可反复跑到收敛）")
    p_rl.add_argument("--dry-run", action="store_true", help="只看结果不写库")

    p_cs = sub.add_parser("consolidate", help="按三元组键合并同键簇（0 LLM）")
    p_cs.add_argument("--apply", action="store_true", help="真正执行合并（默认 dry_run 只出报告）")

    sub.add_parser("rekey", help="重算 pattern_key（纯规则自愈）")
    p_lt = sub.add_parser("longtail", help="长尾归并：单量≤N 且非高危的簇并入同桶「其他」")
    p_lt.add_argument("--max-cnt", type=int, default=1)
    p_lt.add_argument("--apply", action="store_true", help="真正执行（默认 dry_run）")
    sub.add_parser("health", help="簇健康度（簇数/单簇率/覆盖率/兜底率）")
    sub.add_parser("closing", help="簇闭合校验（Σ簇单量 vs 已判定单量）")

    p_new = sub.add_parser("new", help="人工新建根因簇（新业务/新场景先立簇）")
    p_new.add_argument("--stage", required=True, help="订单环节（受控枚举）")
    p_new.add_argument("--mechanism", required=True, help="失败机制（受控枚举）")
    p_new.add_argument("--object", required=True, help="业务对象（可自由命名）")
    p_new.add_argument("--trigger", default="", help="触发条件/场景限定")
    p_new.add_argument("--title", default="")
    p_new.add_argument("--desc", default="", help="判定边界：什么算、什么不算")
    p_new.add_argument("--tickets", default="", help="建簇后挂入的工单号，逗号分隔")

    p_ed = sub.add_parser("edit", help="人工编辑簇（改键会重算 pattern_key 并查重）")
    p_ed.add_argument("--no", required=True, help="根因簇号 RC-xxxx")
    p_ed.add_argument("--stage", default=None)
    p_ed.add_argument("--mechanism", default=None)
    p_ed.add_argument("--object", default=None)
    p_ed.add_argument("--trigger", default=None)
    p_ed.add_argument("--title", default=None)
    p_ed.add_argument("--desc", default=None)

    p_sp = sub.add_parser("split", help="簇内拆单（并入其他簇或另立新簇）")
    p_sp.add_argument("--no", required=True, help="源簇号")
    p_sp.add_argument("--tickets", required=True, help="要拆出的工单号，逗号分隔")
    p_sp.add_argument("--target", default="", help="目标簇号（空=新建簇）")
    p_sp.add_argument("--stage", default="")
    p_sp.add_argument("--mechanism", default="")
    p_sp.add_argument("--object", default="")

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
        elif args.cmd == "known":
            from services.complaint.known import mark, summary
            from services.complaint.metrics import latest_week
            wk = args.week or latest_week(db)
            marked = mark(db, weeks=[wk] if args.week else None)
            out = {"mark": marked, "summary": summary(db, wk)}
        elif args.cmd == "top":
            out = lib.top_clusters(db, week=args.week, limit=args.limit)
        elif args.cmd == "relabel":
            out = lib.relabel_clusters(db, limit=args.limit,
                                       only_missing=args.only_missing,
                                       dry_run=args.dry_run)
        elif args.cmd == "consolidate":
            out = lib.consolidate_by_pattern(db, dry_run=not args.apply)
        elif args.cmd == "rekey":
            out = lib.rekey_clusters(db)
        elif args.cmd == "longtail":
            out = lib.merge_long_tail(db, max_cnt=args.max_cnt, dry_run=not args.apply)
        elif args.cmd == "health":
            out = lib.cluster_health(db)
        elif args.cmd == "closing":
            out = lib.closing_check(db)
        elif args.cmd == "new":
            out = lib.create_cluster(
                db, args.stage, args.mechanism, args.object, trigger=args.trigger,
                title=args.title, description=args.desc,
                ticket_nos=[x.strip() for x in args.tickets.split(",") if x.strip()])
        elif args.cmd == "edit":
            payload = {k: v for k, v in (("fault_stage", args.stage),
                                         ("mechanism", args.mechanism),
                                         ("biz_object", args.object),
                                         ("trigger", args.trigger),
                                         ("title", args.title),
                                         ("description", args.desc)) if v is not None}
            out = lib.update_cluster(db, args.no, payload)
        elif args.cmd == "split":
            nc = {"fault_stage": args.stage, "mechanism": args.mechanism,
                  "biz_object": args.object} if not args.target else None
            out = lib.split_cluster(db, args.no,
                                    [x.strip() for x in args.tickets.split(",") if x.strip()],
                                    target_no=args.target, new_cluster=nc)
        else:
            out = lib.batch_clusters(db, week=args.week, min_cnt=args.min_cnt)
    finally:
        db.close()
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
