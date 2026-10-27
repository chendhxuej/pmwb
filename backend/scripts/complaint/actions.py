"""客诉改进措施台账（CLI 薄封装）—— 实现见 services/complaint/actions.py。

用法（backend 目录下）：
    python -m scripts.complaint.actions list
    python -m scripts.complaint.actions add --l2 "电视与机顶盒账号未同步" --title "..." \
        --owner 吴胜捷 --due 2026-11-10 --acceptance "同类单日峰值降至5单以下" --create-issue
    python -m scripts.complaint.actions verify          # 结算所有验证中措施
    python -m scripts.complaint.actions go-live --action-no CACT-xxx --date 2026-11-01
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from typing import Optional, Sequence

from services.complaint.actions import (  # noqa: F401
    add,
    baseline_for,
    list_actions,
    mark_go_live,
    verify,
    week_count,
)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="客诉改进措施台账")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="列出全部措施")

    p_add = sub.add_parser("add", help="登记措施")
    p_add.add_argument("--l2", required=True, help="二级问题场景（须在字典中）")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--owner", required=True)
    p_add.add_argument("--due", help="要求完成日期 YYYY-MM-DD")
    p_add.add_argument("--acceptance", required=True, help="验收标准（可验证）")
    p_add.add_argument("--desc", default="", help="情况说明")
    p_add.add_argument("--create-issue", action="store_true", help="同时在运营监控建工单")

    sub.add_parser("verify", help="结算验证中的措施")

    p_live = sub.add_parser("go-live", help="标记措施生效并绑定基线")
    p_live.add_argument("--action-no", required=True)
    p_live.add_argument("--date", required=True, help="YYYY-MM-DD")

    args = ap.parse_args(argv)

    from db.base import SessionLocal
    db = SessionLocal()
    try:
        if args.cmd == "list":
            items = list_actions(db)
            if not items:
                print("措施台账为空")
                return 0
            print(f"{'编号':<18}{'场景':<24}{'责任人':<10}{'基线':>6}{'上周':>6}{'降幅':>8}  状态")
            for a in items:
                print(f"{a['action_no']:<18}{(a['category_l2'] or '-')[:22]:<24}{a['owner'] or '-':<10}"
                      f"{a['baseline_cnt'] or 0:>6}{a['last_week_cnt'] or 0:>6}"
                      f"{(a['actual_drop_pct'] if a['actual_drop_pct'] is not None else 0):>7}%  {a['status']}")
            return 0

        if args.cmd == "add":
            due = date.fromisoformat(args.due) if args.due else None
            r = add(db, args.l2, args.title, args.owner, due, args.acceptance,
                    args.create_issue, args.desc)
            print(f"已登记措施 {r['action_no']}（{r['l1']} / {args.l2}）")
            if r["issue_no"]:
                print(f"已建运营工单 {r['issue_no']}（id={r['issue_id']}），父子关联完成")
            return 0

        if args.cmd == "verify":
            rs = verify(db)
            if not rs:
                print("无验证中的措施")
                return 0
            for r in rs:
                print(f"{r['action_no']}  {r['l2']}: 基线 {r['baseline']} → 本周 {r['last_week']} "
                      f"（降幅 {r['drop']}%）→ {r['status']}")
            return 0

        if args.cmd == "go-live":
            mark_go_live(db, args.action_no, date.fromisoformat(args.date))
            print(f"{args.action_no} 已标记生效日 {args.date}，进入验证期")
            return 0
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
