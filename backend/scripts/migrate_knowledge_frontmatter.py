#!/usr/bin/env python
"""存量知识笔记 frontmatter 补全脚本（kc-2-6 收尾）。

背景：
  kc-2 引入「业务领域维度 + pmwb_knowledge_item 索引 + 多对多关联表」后，
  早期进入 Vault 的过程性笔记（运营工单 / 会议 / 需求沉淀等）frontmatter 可能缺少
  与索引表对齐的字段，导致按领域浏览 / 关联时间线依赖 frontmatter 时元数据缺失。

目标：
  为「已在 pmwb_knowledge_item 索引、且带 domain_code」的笔记，补齐其 Obsidian 文件中
  缺失的 frontmatter 字段：domain_code / source_type / item_id。
  说明：PmwbKnowledgeItem 模型无 note_type 列（kc-2-2 的主笔记/子笔记模型未落地），
  故本脚本不补 note_type，仅补与索引表一一对应的真实字段。

安全原则：
  - 仅「新增缺失字段」，绝不修改已有字段值，绝不改动正文（body）。
  - 默认 --dry-run 只出报告；--fix 才写回文件。
  - 写回前务必先 --dry-run 审阅待变更清单，并经用户确认。

用法：
  python migrate_knowledge_frontmatter.py --dry-run
  python migrate_knowledge_frontmatter.py --fix
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, ".")

from db.base import SessionLocal
from db.models import PmwbKnowledgeItem
from utils.obsidian import get_vault_path, read_markdown, parse_frontmatter, write_markdown_safe


def add_missing_frontmatter_fields(content: str, additions: Dict[str, str]) -> Tuple[str, List[str]]:
    """以最 Surgical 的方式，仅为缺失字段追加 frontmatter 行，保留原文其余字节不变。

    返回 (新内容, 实际新增的字段名列表)。
    """
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", content, re.DOTALL)
    if not m:
        # 无 frontmatter：在文首新增一个 frontmatter 块
        lines = ["---"]
        for k, v in additions.items():
            lines.append(f"{k}: {v}")
        lines.append("---")
        return "\n".join(lines) + "\n" + content, list(additions.keys())

    raw = m.group(1)
    body = m.group(2)
    existing_keys = set()
    for line in raw.split("\n"):
        if ":" in line:
            existing_keys.add(line.split(":", 1)[0].strip())

    changed: List[str] = []
    new_raw_lines = raw.split("\n")
    for k, v in additions.items():
        if k not in existing_keys:
            new_raw_lines.append(f"{k}: {v}")
            changed.append(k)

    if not changed:
        return content, []

    new_raw = "\n".join(new_raw_lines)
    return f"---\n{new_raw}\n---\n{body}", changed


def needs_quote(v: str) -> bool:
    return ("," in v) or (" " in v) or (v == "")


def main():
    parser = argparse.ArgumentParser(description="存量知识笔记 frontmatter 补全")
    parser.add_argument("--dry-run", action="store_true", help="只生成报告，不写入")
    parser.add_argument("--fix", action="store_true", help="正式写回文件")
    args = parser.parse_args()
    if not args.dry_run and not args.fix:
        print("请指定 --dry-run 或 --fix")
        sys.exit(1)

    mode = "DRY-RUN" if args.dry_run else "WRITE"
    print(f"[INFO] 模式: {mode}")

    vault = get_vault_path().resolve()
    print(f"[INFO] Vault: {vault}")

    db = SessionLocal()
    items = (
        db.query(PmwbKnowledgeItem)
        .filter(PmwbKnowledgeItem.domain_code.isnot(None))
        .filter(PmwbKnowledgeItem.domain_code != "")
        .all()
    )
    print(f"[INFO] 带 domain_code 的索引条目: {len(items)}")

    total_changed = 0
    total_skipped_missing_file = 0
    by_domain: Dict[str, int] = defaultdict(int)
    missing_file_by_domain: Dict[str, int] = defaultdict(int)
    preview: List[Tuple[str, str, List[str]]] = []

    for item in items:
        rel = (item.obsidian_path or "").replace("\\", "/")
        if not rel:
            continue
        content = read_markdown(rel)
        if content is None:
            total_skipped_missing_file += 1
            missing_file_by_domain[item.domain_code] += 1
            continue

        fm = parse_frontmatter(content)
        additions: Dict[str, str] = {}
        if not (fm.get("domain_code") or "").strip():
            additions["domain_code"] = item.domain_code
        if not (fm.get("source_type") or "").strip():
            additions["source_type"] = item.source_type or "manual"
        if not (fm.get("item_id") or "").strip():
            additions["item_id"] = item.item_id

        if not additions:
            continue

        # 值做安全引用
        safe = {k: f'"{v}"' if needs_quote(v) else v for k, v in additions.items()}

        if args.fix:
            new_content, changed = add_missing_frontmatter_fields(content, safe)
            if changed:
                write_markdown_safe(rel, new_content)
                total_changed += 1
                by_domain[item.domain_code] += 1
        else:
            _, changed = add_missing_frontmatter_fields(content, safe)
            if changed:
                total_changed += 1
                by_domain[item.domain_code] += 1
                if len(preview) < 30:
                    preview.append((rel, item.domain_code, changed))

    db.close()

    print("\n=== 将变更 / 已变更 的笔记（按领域）===")
    for d in sorted(by_domain):
        print(f"  {d}: {by_domain[d]} 篇")
    print(f"\n[汇总] 待补/已补 frontmatter: {total_changed} 篇")
    print(f"[汇总] 索引存在但 Vault 文件缺失（跳过）: {total_skipped_missing_file} 篇")
    if missing_file_by_domain:
        print("  缺失文件分布:", dict(missing_file_by_domain))

    if preview:
        print("\n=== 预览（前 30 篇，格式：路径 | 领域 | 新增字段）===")
        for rel, dom, changed in preview:
            print(f"  {rel} | {dom} | +{','.join(changed)}")

    if args.dry_run:
        print("\n(dry-run 模式，未实际写入；确认无误后加 --fix 执行)")
    else:
        print("\n(已写回 Vault 文件，仅新增缺失字段，未改动正文)")


if __name__ == "__main__":
    main()
