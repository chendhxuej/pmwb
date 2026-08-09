#!/usr/bin/env python
"""沉淀笔记归入领域树迁移脚本（kc-3 / P4）。

背景：
  kc-3 P4 之前，运营工单/会议纪要/开发工单的沉淀笔记分别写死在
  `11-业务运营/`、`05-会议纪要/`、`14-知识沉淀/开发交付/` 等非领域树路径，
  与"业务知识主笔记"所在的 `01-业务知识/{group}/{name}/` 树割裂，结构不清晰。
  P4 已把 sediment_* 改为经 obsidian_paths.resolve_domain_path 归入领域树。
  本脚本把存量笔记从旧路径迁移到新领域树位置，并同步更新 pmwb_knowledge_item.obsidian_path。

映射规则（按 source_type + 旧路径前缀）：
  operation: 11-业务运营/{cat}/FILE → 01-业务知识/{group}/{name}/运营/{cat}/FILE
  meeting:   05-会议纪要/FILE        → 01-业务知识/{group}/{name}/会议/FILE
  ticket:    14-知识沉淀/开发交付/FILE → 01-业务知识/{group}/{name}/开发交付/FILE

安全原则：
  - 默认 --dry-run 只出报告；--apply 才移动文件 + 更新索引。
  - 仅迁移 source_type in (operation/meeting/ticket) 且 obsidian_path 命中旧前缀的索引。
  - 仅迁移 item.domain_code 非空者（否则无法解析领域树位置，跳过并打印告警）。
  - 目标文件已存在则跳过该条（不覆盖），并打印告警。

用法：
  python migrate_sediment_to_domain_tree.py --dry-run
  python migrate_sediment_to_domain_tree.py --apply
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

sys.path.insert(0, ".")

from core.config import settings
from db.base import SessionLocal
from db.models import PmwbKnowledgeItem
from services import obsidian_paths
from utils.obsidian import get_vault_path

# (source_type, 旧路径前缀, 领域树子目录)
_OLD_PREFIXES = [
    ("operation", "11-业务运营/", obsidian_paths.SUBDIR_OPERATION),
    ("meeting", "05-会议纪要/", obsidian_paths.SUBDIR_MEETING),
    ("ticket", "14-知识沉淀/开发交付/", obsidian_paths.SUBDIR_DEV_TICKET),
]


def _compute_new_rel(db, item) -> str | None:
    """根据旧路径计算新领域树相对路径；无法解析返回 None。"""
    if not item.domain_code:
        return None
    try:
        base = obsidian_paths.resolve_domain_path(db, item.domain_code)
    except Exception:
        return None
    for source_type, old_prefix, subdir in _OLD_PREFIXES:
        if item.source_type == source_type and item.obsidian_path.startswith(old_prefix):
            rest = item.obsidian_path[len(old_prefix):]  # 旧前缀之后的部分
            return f"{base}/{subdir}/{rest}"
    return None


def main():
    parser = argparse.ArgumentParser(description="把沉淀笔记迁移到领域树")
    parser.add_argument("--apply", action="store_true", help="真正移动文件（默认 dry-run）")
    args = parser.parse_args()

    vault = get_vault_path()
    db = SessionLocal()
    try:
        items = (
            db.query(PmwbKnowledgeItem)
            .filter(PmwbKnowledgeItem.source_type.in_(["operation", "meeting", "ticket"]))
            .all()
        )
        print(f"[scan] 运营/会议/开发交付 知识索引: {len(items)}")

        moved = 0
        skipped = 0
        for item in items:
            new_rel = _compute_new_rel(db, item)
            if not new_rel:
                if item.obsidian_path and any(
                    item.obsidian_path.startswith(p) for _, p, _ in _OLD_PREFIXES
                ):
                    print(f"  [skip] domain_code 为空，无法解析领域树: id={item.id} {item.obsidian_path}")
                    skipped += 1
                continue

            src = vault / item.obsidian_path
            dst = vault / new_rel
            if not src.exists():
                print(f"  [skip] 源文件不存在: id={item.id} {item.obsidian_path}")
                skipped += 1
                continue
            if dst.exists():
                print(f"  [skip] 目标已存在（不覆盖）: id={item.id} -> {new_rel}")
                skipped += 1
                continue

            if not args.apply:
                print(f"  [dry-run] 迁移: {item.obsidian_path} -> {new_rel}")
                moved += 1
                continue

            os.makedirs(dst.parent, exist_ok=True)
            shutil.move(str(src), str(dst))
            item.obsidian_path = new_rel
            moved += 1
            print(f"  [apply] 迁移: {item.obsidian_path} -> {new_rel}")

        if args.apply:
            db.commit()
            print(f"[done] 已迁移 {moved} 条，跳过 {skipped} 条")
        else:
            print(f"[dry-run] 预计迁移 {moved} 条，跳过 {skipped} 条；加 --apply 执行")
    finally:
        db.close()


if __name__ == "__main__":
    main()
