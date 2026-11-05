# -*- coding: utf-8 -*-
"""L2 功能模块问题归并 CLI（离线/后台执行，对应 services/complaint/module_aggregate.py）。

用法：
  python scripts/complaint/module_aggregate_cli.py --dry-run        # 只统计不落库
  python scripts/complaint/module_aggregate_cli.py --apply           # 落库（全量重建）
"""
import os
import sys

# 让脚本能 import 后端包（scripts/complaint -> 上两级到项目根 -> backend）
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.dirname(os.path.dirname(_HERE))
BACKEND = os.path.join(_PROJECT, "backend")
sys.path.insert(0, BACKEND)

from db.base import SessionLocal, engine, Base  # noqa: E402
from db.models import PmwbComplaintModuleProblem, PmwbComplaintTicketModule  # noqa: E402
from services.complaint import module_aggregate as mod_agg  # noqa: E402

# 幂等建表（新模型首次运行前确保表存在；已存在则 no-op）
Base.metadata.create_all(bind=engine)


def main():
    dry = "--apply" not in sys.argv
    db = SessionLocal()
    try:
        res = mod_agg.run_aggregate(db, dry_run=dry)
        print("dry_run=%s" % dry)
        print("总工单=%d 已归集(含咨询)=%d 未归类=%d 低置信=%d 缺陷类数=%d" % (
            res["total"], res["classified"], res["unclassified"], res["low_conf"], res["classes"]))
        print("=== 各类分布 ===")
        for c in res["module_problems"]:
            tag = "" if c["is_defect"] else "(咨询)"
            print("  %s %s 单量=%d 活跃周=%d 表象=%d%s" % (
                c["module_problem_id"], c["name"], c["ticket_cnt"], c["active_weeks"], c["surface_cnt"], tag))
        if not dry:
            print(">>> 已落库：pmwb_complaint_module_problem / pmwb_complaint_ticket_module")
    finally:
        db.close()


if __name__ == "__main__":
    main()
