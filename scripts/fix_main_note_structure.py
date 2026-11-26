"""修复错乱主笔记结构（A骨架+B模板混排：H1 流窜/§顺序颠倒/frontmatter 丢失/无编号 MOC）。

用法：
    python scripts/fix_main_note_structure.py            # dry_run，只读报告
    python scripts/fix_main_note_structure.py --apply     # 实际写盘 + 重建 §7/§8

铁律：
- 人工区正文零改写（只换位置，不改字）；
- AUTO 块按 key 保留全文最丰富内容；
- §7/§8 关联索引不搬运旧文件（会叠加），由 rebuild 从 DB 全量重建；
- 幂等：规范化函数对已规范文件再跑结果一致。
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath('backend'))
from dotenv import load_dotenv
for _p in ['backend/.env', os.path.join(os.getcwd(), 'backend', '.env'), '.env']:
    if os.path.exists(_p):
        load_dotenv(_p)
        break

from db.base import SessionLocal
from db.models import PmwbBusinessDomain, PmwbKnowledgeItem, now_cn
from services import knowledge_link_service as kls
from services import obsidian_paths as op
from utils.obsidian import read_markdown, write_markdown

# 本次修复对象：6 份新领域主笔记（上一轮亲自填充、结构被 dedup 固化的）
TARGETS = ['GYKD', 'GKDS', 'KSQYKD', 'EQZW', 'jtqly', 'DEHB']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='实际写盘（默认仅 dry_run）')
    args = ap.parse_args()

    db = SessionLocal()
    changed = 0
    for code in TARGETS:
        d = db.query(PmwbBusinessDomain).filter_by(domain_code=code).first()
        if not d:
            print(f'SKIP(no-domain) {code}')
            continue
        rel = op.main_note_rel_path(d.domain_name, d.domain_group)
        text = read_markdown(rel)
        if not text:
            print(f'SKIP(no-file) {code} {rel}')
            continue
        item = db.query(PmwbKnowledgeItem).filter_by(domain_code=code, note_type='main').first()
        item_id = item.item_id if item and item.item_id else kls._gen_item_id()
        new_text = kls.restructure_main_note_content(
            text, d, item_id, now_cn().strftime('%Y-%m-%d')
        )
        # 幂等判据：结构已规范即跳过（规范化会清空 §7/§8 交给 rebuild，
        # 所以 new_text==text 永远不成立；用结构特征判断，避免每次复跑都误报 DRY）
        lines = text.splitlines()
        h1 = [i for i, l in enumerate(lines, 1) if l.startswith('# ')]
        heads = [int(m.group(1)) for l in lines for m in [re.match(r'^## (\d+)\.', l)] if m]
        structured = (
            text.startswith('---')
            and len(h1) == 1 and h1[0] <= 25
            and heads == sorted(heads)
            and not any(l.strip() == '## 相关子笔记 MOC' for l in lines)
        )
        if structured:
            print(f'[NOOP] {code} {d.domain_name} | {rel} (结构已规范)')
            continue
        print(f'[{"WRITE" if args.apply else "DRY"}] {code} {d.domain_name} | {rel} | '
              f'{len(text.splitlines())}行 -> {len(new_text.splitlines())}行')
        if args.apply:
            write_markdown(rel, new_text, protect_if_modified=False)
            changed += 1

    if args.apply:
        # 重建 §7/§8 索引（§7 由关联数据回填、§8 由子笔记回填）
        print('\n=== 重建 §7/§8 索引 ===')
        for code in TARGETS:
            r7 = kls.rebuild_main_note_section7(db, code)
            r8 = kls.rebuild_main_note_subnotes(db, code)
            print(f'  {code:8} §7={"OK" if r7 else "skip"} §8={"OK" if r8 else "skip"}')
        db.commit()

    db.close()
    print(f'\n{"已写入" if args.apply else "待写入"}: {changed}/{len(TARGETS)}')


if __name__ == '__main__':
    main()
