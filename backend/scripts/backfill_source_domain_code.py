#!/usr/bin/env python
"""存量源记录 domain_code 回填脚本（kc-3 / P3）。

背景：
  领域浏览页出现"时间线有信息、但需求/运营/会议卡片为空"的错位，根因是：
  过程性对象（需求/运营工单/会议）经 KnowledgeLinker 关联时，pmwb_knowledge_link
  被回填了 domain_code，但源记录自身的 domain_code 仍为 NULL。
  get_related 之前只按「源表 domain_code」聚合，导致链接驱动的数据无法在卡片中呈现。

  P3 已把 get_related / _related_counts 改为「源表归属 + 链接回溯」并集口径，
  本脚本作为一次性数据修复：把"链接有 domain_code、但源记录 domain_code 为空"
  的存量记录补填，使源表与关联链接口径一致（未来新建关联已由 link_note 自动回填）。

安全原则：
  - 默认 --dry-run 只出报告；--apply 才写库。
  - 仅填充【源记录 domain_code 为空】的记录，绝不覆盖已有领域。

用法：
  python backfill_source_domain_code.py --dry-run
  python backfill_source_domain_code.py --apply
"""
from __future__ import annotations

import argparse
import sys

sys.path.insert(0, ".")

from db.base import SessionLocal
from db.models import (
    PmwbDevTicket,
    PmwbKeyWork,
    PmwbKnowledgeLink,
    PmwbMeeting,
    PmwbOperationIssue,
    PmwbRequirementExt,
)

# source_type -> (模型, 匹配字段)
_SOURCE_MAP = {
    "requirement": (PmwbRequirementExt, "req_id"),
    "operation": (PmwbOperationIssue, "id"),
    "meeting": (PmwbMeeting, "id"),
    "ticket": (PmwbDevTicket, "ticket_no"),
    "key_work": (PmwbKeyWork, "id"),
}


def _resolve_rec(db, source_type: str, source_id: str):
    spec = _SOURCE_MAP.get(source_type)
    if not spec:
        return None
    model, field = spec
    col = getattr(model, field)
    try:
        if field == "id":
            val = int(source_id)
        else:
            val = source_id
    except (ValueError, TypeError):
        return None
    return db.query(model).filter(col == val).first()


def main():
    parser = argparse.ArgumentParser(description="回填存量源记录的 domain_code")
    parser.add_argument("--apply", action="store_true", help="真正写库（默认 dry-run）")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        links = (
            db.query(
                PmwbKnowledgeLink.source_type,
                PmwbKnowledgeLink.source_id,
                PmwbKnowledgeLink.domain_code,
            )
            .filter(PmwbKnowledgeLink.domain_code.isnot(None))
            .all()
        )
        print(f"[scan] 带 domain_code 的关联链接: {len(links)}")

        changed = 0
        skipped = 0
        for st, sid, dc in links:
            rec = _resolve_rec(db, st, sid)
            if rec is None:
                skipped += 1
                continue
            if rec.domain_code:
                # 已有领域，不覆盖（即便不同也保留源记录自身归属）
                continue
            if not args.apply:
                print(f"  [dry-run] 回填 {st}#{sid} -> domain_code={dc}")
                changed += 1
                continue
            rec.domain_code = dc
            changed += 1
            print(f"  [apply] 回填 {st}#{sid} -> domain_code={dc}")

        if args.apply:
            db.commit()
            print(f"[done] 已回填 {changed} 条，跳过（无匹配/已有领域）{skipped} 条")
        else:
            print(f"[dry-run] 预计回填 {changed} 条，跳过 {skipped} 条；加 --apply 执行")
    finally:
        db.close()


if __name__ == "__main__":
    main()
