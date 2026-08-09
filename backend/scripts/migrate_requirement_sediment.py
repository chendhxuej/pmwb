#!/usr/bin/env python
"""需求沉淀笔记同置迁移脚本（kc-3 / P1）。

背景：
  kc-3 P1 将「沉淀需求为知识笔记」的落盘位置从独立的 10-业务建设/需求沉淀/
  改为需求自身文件夹 业务建设/需求分析说明书/{req_id}_{safe(req_name)}/（与需求分析说明书/附件同目录）。
  本脚本把存量需求知识笔记从旧目录迁移到新位置，并同步更新 pmwb_knowledge_item.obsidian_path。

安全原则：
  - 默认 --dry-run 只出报告；--apply 才移动文件 + 更新索引。
  - 仅移动来源为 requirement 且路径以 10-业务建设/需求沉淀/ 开头的索引条目。
  - 目标文件已存在则跳过该条（不覆盖），并打印告警。

用法：
  python migrate_requirement_sediment.py --dry-run
  python migrate_requirement_sediment.py --apply
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

sys.path.insert(0, ".")

from core.config import settings
from db.base import SessionLocal
from db.models import PmwbKnowledgeItem, PmwbRequirementExt, SentEmail
from services import requirement_delivery
from utils.obsidian import get_vault_path


def main():
    parser = argparse.ArgumentParser(description="迁移需求沉淀笔记到需求自身文件夹")
    parser.add_argument("--apply", action="store_true", help="真正执行移动（默认 dry-run）")
    args = parser.parse_args()

    vault = get_vault_path()
    db = SessionLocal()
    try:
        items = (
            db.query(PmwbKnowledgeItem)
            .filter(PmwbKnowledgeItem.source_type == "requirement")
            .filter(PmwbKnowledgeItem.obsidian_path.like("10-业务建设/需求沉淀/%"))
            .all()
        )
        print(f"[scan] 命中需求沉淀索引条目: {len(items)}")
        moves = 0
        for item in items:
            req_id = item.source_id
            ext = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == req_id).first()
            email = db.query(SentEmail).filter(SentEmail.req_id == req_id).first()
            req_name = (ext.req_name if ext and ext.req_name else (email.req_name if email else req_id))
            folder_abs = requirement_delivery._resolve_paths(req_id, req_name)["folder"]
            rel_folder = os.path.relpath(folder_abs, str(vault))
            new_filename = f"{requirement_delivery._safe_name(req_name or req_id)}-知识沉淀.md"
            new_rel = os.path.join(rel_folder, new_filename)

            src = vault / item.obsidian_path
            dst = vault / new_rel
            print(f"  req_id={req_id}")
            print(f"    FROM: {item.obsidian_path}")
            print(f"    TO  : {new_rel}")

            if not src.exists():
                print("    [SKIP] 源文件不存在")
                continue
            if dst.exists():
                print("    [SKIP] 目标已存在，避免覆盖")
                continue

            if args.apply:
                os.makedirs(dst.parent, exist_ok=True)
                shutil.move(str(src), str(dst))
                item.obsidian_path = new_rel
                db.commit()
                moves += 1
                print("    [MOVED]")
            else:
                print("    [dry-run] 未执行")
        print(f"[done] 实际移动: {moves}（apply={args.apply}）")
    finally:
        db.close()


if __name__ == "__main__":
    main()
