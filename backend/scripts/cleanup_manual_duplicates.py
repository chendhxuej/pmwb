# -*- coding: utf-8 -*-
"""一次性清理：操作手册被重复登记成「需求交付物」+「需求操作手册」两份材料。

背景（老大 2026-09-11 反馈）：需求与交付模块上传操作手册时，除了写 PmwbReqManual，
还往 pmwb_requirement_ext.deliverables 写了一条「操作手册-{系统}」兼容条目，
业务资料库汇聚后同一文件出现两条记录（需求交付物 / 需求操作手册）。

本脚本做两件事（均幂等，可重复执行；只动索引，不删物理文件）：
1. 从 deliverables JSON 中剔除 note 以「操作手册-」开头的历史兼容条目；
2. 删除与 req_manual 指向同一文件的「需求交付物」材料索引。

用法：cd backend && .\\venv\\Scripts\\python.exe scripts/cleanup_manual_duplicates.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.base import SessionLocal  # noqa: E402
from db.models import PmwbMaterial, PmwbRequirementExt
from services.material_sync import purge_manual_duplicates

PREFIX = "操作手册-"


def main() -> int:
    db = SessionLocal()
    cleaned_ext = 0
    removed_entries = 0
    try:
        exts = (
            db.query(PmwbRequirementExt)
            .filter(PmwbRequirementExt.deliverables.isnot(None))
            .all()
        )
        for ext in exts:
            raw = ext.deliverables or ""
            try:
                items = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(items, list):
                continue
            kept = [
                it
                for it in items
                if not (
                    isinstance(it, dict)
                    and str(it.get("note") or "").startswith(PREFIX)
                )
            ]
            if len(kept) != len(items):
                removed_entries += len(items) - len(kept)
                ext.deliverables = json.dumps(kept, ensure_ascii=False)
                cleaned_ext += 1
        db.commit()

        purged = purge_manual_duplicates(db)
        left = (
            db.query(PmwbMaterial)
            .filter(PmwbMaterial.source_type.in_(["req_manual", "requirement"]))
            .count()
        )
        print(f"清理的需求交付物兼容条目：{removed_entries} 条（涉及 {cleaned_ext} 个需求）")
        print(f"删除的重复材料索引：{purged} 条")
        print(f"剩余 需求操作手册/需求交付物 材料总数：{left}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
