"""修复错乱主笔记结构（A骨架+B模板混排：H1 流窜/§顺序颠倒/frontmatter 丢失/无编号 MOC）。

用法：
    python scripts/fix_main_note_structure.py              # dry_run，6 份新领域
    python scripts/fix_main_note_structure.py --apply       # 实际写盘 + 重建 §7/§8
    python scripts/fix_main_note_structure.py --low-risk    # dry_run，11 份中低风险历史笔记
    python scripts/fix_main_note_structure.py --low-risk --apply

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
# 中低风险历史存量：人工实质内容 ≤20 行（清单 docs/主笔记结构错乱_待确认清单_20261126.md §2.2）
# 商客和目存在 ywt-hm / sk-hm 两个编码、同一路径；取有 3 条关联数据的 ywt-hm，避免 §7 重建落空。
LOW_RISK_TARGETS = [
    'wgt', 'scyypt', 'ywt-HDICT', 'zxqysp', 'sjzx', 'skcsp',
    'grxx', 'ywt-hm', 'ywt-gh', 'ywfzzb', 'group-order-delivery',
]
# 模板升级迁移：已规范但仍是旧「业务领域」骨架的公共能力笔记，强制换功能说明模板。
# GIMS 等其他公共能力多为高风险人工存量，不在本次迁移范围。
CAPABILITY_TARGETS = ['skcsp', 'DEHB']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='实际写盘（默认仅 dry_run）')
    ap.add_argument('--low-risk', action='store_true', help='改修 11 份中低风险历史主笔记')
    ap.add_argument('--capability', action='store_true', help='公共能力：强制迁移到功能说明模板')
    args = ap.parse_args()
    targets = (CAPABILITY_TARGETS if args.capability
               else LOW_RISK_TARGETS if args.low_risk else TARGETS)

    db = SessionLocal()
    changed = 0
    for code in targets:
        d = db.query(PmwbBusinessDomain).filter_by(domain_code=code).first()
        if not d:
            print(f'SKIP(no-domain) {code}')
            continue
        item = db.query(PmwbKnowledgeItem).filter_by(domain_code=code, note_type='main').first()
        # 历史笔记部分文件名无空格（如「网格通业务知识主笔记.md」），模板推算路径找不到；
        # DB 的 obsidian_path 才是权威落位，与 §7/§8 重建同一来源。
        rel = (item.obsidian_path.replace('\\', '/') if item and item.obsidian_path
               else op.main_note_rel_path(d.domain_name, d.domain_group))
        text = read_markdown(rel)
        if not text:
            print(f'SKIP(no-file) {code} {rel}')
            continue
        item_id = item.item_id if item and item.item_id else kls._gen_item_id()
        new_text = kls.restructure_main_note_content(
            text, d, item_id, now_cn().strftime('%Y-%m-%d'), force=args.capability
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
        if structured and not args.capability:
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
        for code in targets:
            r7 = kls.rebuild_main_note_section7(db, code)
            r8 = kls.rebuild_main_note_subnotes(db, code)
            print(f'  {code:20} §7={"OK" if r7 else "skip"} §8={"OK" if r8 else "skip"}')
        db.commit()

    db.close()
    print(f'\n{"已写入" if args.apply else "待写入"}: {changed}/{len(targets)}')


if __name__ == '__main__':
    main()
