# -*- coding: utf-8 -*-
"""客诉「主要投诉点」标准名重新发布（v2 口径落库，不改判定式）。

用途：字典标准名升级后，页面类表读的是 pmwb_complaint_module_problem.name
快照；本脚本用新进程（加载 v2 字典）重跑闭集归并，把新名写进快照，
使页面无须重启服务即可显示修正后的标准类名。

安全设计：
1. 默认 dry_run，只对比不写；--apply 才落库。
2. 落库前比对「已归类/未归类/各标准类单量」与库内现状，任一漂移即中止。
3. 落库前检查人工台 override/accepted 记录并明示（重跑会覆盖人工改派）；
   若存在，须显式 --force 才继续，避免静默丢失人工操作。
4. 全程只重建 module_problem / ticket_module 两张派生表，不动工单主表与台账。

用法：
  backend/venv/Scripts/python.exe scripts/complaint_republish_module_names.py
  backend/venv/Scripts/python.exe scripts/complaint_republish_module_names.py --apply
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from db.base import SessionLocal  # noqa: E402
from db.models import (  # noqa: E402
    PmwbComplaintModuleProblem,
    PmwbComplaintTicketModule,
)
from services.complaint import module_aggregate as AGG  # noqa: E402
from constants import complaint_module as M  # noqa: E402


def snapshot(db):
    """读当前库内派生表状态（只读）。"""
    mp = {
        r.module_problem_id: {
            "name": r.name, "cnt": r.ticket_cnt, "version": r.version,
        }
        for r in db.query(PmwbComplaintModuleProblem).all()
    }
    total = db.query(PmwbComplaintTicketModule).count()
    unclassified = (
        db.query(PmwbComplaintTicketModule)
        .filter(PmwbComplaintTicketModule.module_problem_id.is_(None))
        .count()
    )
    manual = (
        db.query(PmwbComplaintTicketModule)
        .filter(PmwbComplaintTicketModule.review_status.in_(["override", "accepted"]))
        .count()
    )
    return {"mp": mp, "total": total, "unclassified": unclassified, "manual": manual}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正落库（默认只对比）")
    ap.add_argument("--force", action="store_true", help="存在人工改派记录时仍继续")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        before = snapshot(db)
        print("=== 落库前 ===")
        print("字典版本 v%s / 库内快照版本 %s" %
              (M.MODULE_DICT_VERSION,
               sorted({v["version"] for v in before["mp"].values()})))
        print("ticket_module 行数=%d 未归类=%d 人工改派=%d 标准类=%d" %
              (before["total"], before["unclassified"], before["manual"], len(before["mp"])))
        print("样本旧名 MP-ORDER-CLOSE = %s" %
              before["mp"].get("MP-ORDER-CLOSE", {}).get("name"))

        # dry_run：用 v2 字典重算，不写库
        dry = AGG.run_aggregate(db, dry_run=True)
        print("\n=== dry_run 重算 ===")
        print("total=%d classified=%d unclassified=%d classes=%d" %
              (dry["total"], dry["classified"], dry["unclassified"], dry["classes"]))
        dry_map = {x["module_problem_id"]: x["ticket_cnt"] for x in dry["module_problems"]}
        before_map = {k: v["cnt"] for k, v in before["mp"].items()}
        drift = {
            k: {"before": before_map.get(k), "dry": dry_map.get(k)}
            for k in set(before_map) | set(dry_map)
            if before_map.get(k) != dry_map.get(k)
        }
        print("单量漂移类目数 = %d %s" %
              (len(drift), json.dumps(drift, ensure_ascii=False) if drift else ""))
        print("未归类：库内 %d / 重算 %d" % (before["unclassified"], dry["unclassified"]))

        problems = []
        if drift:
            problems.append("各标准类单量与库内不一致，判定式可能被改动")
        if before["unclassified"] != dry["unclassified"]:
            problems.append("未归类数与库内不一致")
        if before["manual"] and not args.force:
            problems.append("存在 %d 条人工改派记录，重跑会覆盖（需 --force）" % before["manual"])

        if problems:
            print("\n[ABORT] " + "；".join(problems))
            return 2

        if not args.apply:
            print("\n[DRY-RUN OK] 数字零漂移，可加 --apply 落库")
            return 0

        # 落库
        AGG.run_aggregate(db, dry_run=False)
        db.expire_all()
        after = snapshot(db)
        after_map = {k: v["cnt"] for k, v in after["mp"].items()}
        post_drift = {k: (before_map.get(k), after_map.get(k))
                      for k in set(before_map) | set(after_map)
                      if before_map.get(k) != after_map.get(k)}
        changed = [
            {"id": k, "old": before["mp"].get(k, {}).get("name"),
             "new": after["mp"].get(k, {}).get("name")}
            for k in after["mp"]
            if before["mp"].get(k, {}).get("name") != after["mp"][k]["name"]
        ]
        print("\n=== 落库后 ===")
        print("ticket_module 行数=%d 未归类=%d 标准类=%d 快照版本=%s" %
              (after["total"], after["unclassified"], len(after["mp"]),
               sorted({v["version"] for v in after["mp"].values()})))
        print("改名类目 = %d / %d；落库后单量漂移 = %d" %
              (len(changed), len(after["mp"]), len(post_drift)))
        print("MP-ORDER-CLOSE: %s -> %s" %
              (before["mp"].get("MP-ORDER-CLOSE", {}).get("name"),
               after["mp"].get("MP-ORDER-CLOSE", {}).get("name")))

        out = {
            "dict_version": M.MODULE_DICT_VERSION,
            "before": {"total": before["total"], "unclassified": before["unclassified"],
                       "manual": before["manual"]},
            "after": {"total": after["total"], "unclassified": after["unclassified"],
                      "snapshot_version": sorted({v["version"] for v in after["mp"].values()})},
            "count_drift": len(post_drift),
            "renamed": changed,
            "names": [{"id": k, "name": v["name"], "cnt": v["cnt"]}
                      for k, v in sorted(after["mp"].items(), key=lambda x: -x[1]["cnt"])],
        }
        dst = os.path.join(ROOT, "data", "complaint_module_republish_result.json")
        with io.open(dst, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print("结果 -> %s" % dst)
        if post_drift or len(changed) != 20:
            print("[WARN] 存在单量漂移或改名条数不足，请复核")
            return 1
        print("[APPLY OK] 20 条标准名已发布，归类单量零漂移")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
