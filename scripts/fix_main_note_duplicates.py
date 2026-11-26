"""存量主笔记重复模板修复（方案A 落地后的存量清理，幂等、非破坏）。

根因：建领域时 ensure_domain_dir 写 A 骨架，随后 create_main_note 又用
merge_with_existing_content 叠加 B 标准模板 → 章节标题不匹配 → 整份追加，
frontmatter 丢失、AUTO 块同 key 重复 2 次，自动回流只写其中一处。

本脚本：对每个目标主笔记做「去重复章节 + 同 key AUTO 块去重 + 补 frontmatter」，
保留人工正文，绝不覆盖。默认 dry_run 只报告；确认后显式 --apply 才落盘。

用法：
    python scripts/fix_main_note_duplicates.py                 # dry_run，列全部候选
    python scripts/fix_main_note_duplicates.py --apply          # 修复全部候选
    python scripts/fix_main_note_duplicates.py --apply --codes jtqly,GYKD   # 只修指定领域
    python scripts/fix_main_note_duplicates.py --apply --rebuild-empty      # 空壳额外按标准模板重建
"""
import argparse
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.abspath('backend'))
from dotenv import load_dotenv
for _p in ['backend/.env', os.path.join(os.getcwd(), 'backend', '.env'), '.env']:
    if os.path.exists(_p):
        load_dotenv(_p)
        break

from db.base import SessionLocal
from db.models import PmwbBusinessDomain, PmwbKnowledgeItem
from services import knowledge_link_service as kls
from services import obsidian_paths as op
from utils.obsidian import read_markdown, write_markdown
from core.config import settings

# 空壳判定阈值：实质内容行 < 8 视为模板残留，可安全重建
PLACEHOLDER = [
    '人工维护区，自动沉淀不覆盖', '自动区：由业务事件自动回流',
    '系统维护区，由 vault_sync', '_暂无数据_',
    '本笔记由 PMWB 知识中心自动生成骨架', '本笔记为该业务领域的唯一主入口',
    '以下链接由系统自动维护',
]


def real_line_count(text: str) -> int:
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s or any(p in s for p in PLACEHOLDER):
            continue
        if re.match(r'^<!--\s*PMWB:AUTO', s) or re.match(r'^#{1,6}\s', s):
            continue
        if re.match(r'^\|[-:|]+\|$', s) or set(s) <= set('|- '):
            continue
        out.append(s)
    return len(out)


def problem_signature(text: str):
    keys = re.findall(r'PMWB:AUTO:BEGIN key=(\w+)', text)
    dup_auto = {k: v for k, v in Counter(keys).items() if v > 1}
    heads = [h.strip() for h in re.findall(r'^#{1,2}\s+(.+)$', text, re.M)]
    dup_head = {k: v for k, v in Counter(heads).items() if v > 1}
    return dup_auto, dup_head


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='实际写盘（默认仅 dry_run）')
    ap.add_argument('--codes', type=str, default='', help='逗号分隔的 domain_code 白名单')
    ap.add_argument('--rebuild-empty', action='store_true', help='空壳(<8实质行)按标准模板重建')
    args = ap.parse_args()

    db = SessionLocal()
    codes = [c.strip() for c in args.codes.split(',') if c.strip()]
    domains = db.query(PmwbBusinessDomain).filter(PmwbBusinessDomain.enabled == True).all()
    if codes:
        domains = [d for d in domains if d.domain_code in codes]

    vault = Path(settings.OBSIDIAN_VAULT_PATH).resolve()
    candidates = []
    seen_rel = set()  # general / general-group 同指向一份文件，避免重复处理
    for d in domains:
        rel = op.main_note_rel_path(d.domain_name, d.domain_group)
        if rel in seen_rel:
            continue
        seen_rel.add(rel)
        path = vault / rel.replace('\\', '/')
        if not path.exists():
            print(f'SKIP(no-file) {d.domain_code} {rel}')
            continue
        text = path.read_text(encoding='utf-8')
        dup_auto, dup_head = problem_signature(text)
        if not dup_auto and not dup_head:
            continue
        candidates.append((d, rel, path, text, dup_auto, dup_head, real_line_count(text)))

    print(f'候选问题主笔记: {len(candidates)} 个\n')
    changed = 0
    for d, rel, path, text, dup_auto, dup_head, real_cnt in candidates:
        empty = real_cnt < 8
        mode = 'REBUILD(空壳)' if (empty and args.rebuild_empty) else 'DEDUP(去重)'
        print(f'[{mode}] {d.domain_code} {d.domain_name} | 实质行={real_cnt} 重复AUTO={dup_auto}')
        if not args.apply:
            continue

        # item_id 单一真相源：优先取 DB 主笔记索引，缺失则用项目统一生成器
        from db.models import now_cn
        item = (
            db.query(PmwbKnowledgeItem)
            .filter_by(domain_code=d.domain_code, note_type='main').first()
        )
        item_id = item.item_id if item else kls._gen_item_id()
        today = now_cn().strftime('%Y-%m-%d')
        if empty and args.rebuild_empty:
            new_text = kls.build_main_note_markdown(d, item_id, today)
        else:
            new_text = kls.normalize_main_note_content(text)
            new_text = kls.ensure_frontmatter(new_text, d, item_id, today)

        if new_text != text:
            write_markdown(rel, new_text, protect_if_modified=False)
            _, after_auto = {}, problem_signature(new_text)[0]
            assert not after_auto, f'修复后仍有重复AUTO块: {rel}'
            changed += 1
            print(f'    FIXED {rel}')
        else:
            print(f'    NOOP')

    db.close()
    print(f'\n{"已修复" if args.apply else "待修复"}: {changed}/{len(candidates)}')


if __name__ == '__main__':
    main()
