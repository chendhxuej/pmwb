"""专用修复 GIMS 反向地址同步主笔记（转义编号 + H1 章节头，通用重排会丢正文）。

背景：
- 该笔记用 `## 1\\.1 背景与目标`、`# 4、同步数据说明` 等非标准编号；
  通用 _parse_note_blocks 只认 `## N.`，把这些块错配后丢 75 行人工正文。
- 因此专用脚本：按「块标题」识别 1.1~9.1，整块搬入功能说明模板 §1-§4，
  正文逐行原样保留，AUTO 块按 key 取最丰富版本，§7/§8 交 rebuild 重建。

用法：
    python scripts/fix_gims_main_note.py          # dry_run
    python scripts/fix_gims_main_note.py --apply  # 写盘 + 重建 §7/§8
"""
import argparse
import os
import re
import shutil
import sys
from collections import defaultdict

sys.path.insert(0, os.path.abspath('backend'))
from dotenv import load_dotenv
for _p in ['backend/.env', os.path.join(os.getcwd(), 'backend', '.env'), '.env']:
    if os.path.exists(_p):
        load_dotenv(_p)
        break

from db.base import SessionLocal
from db.models import PmwbBusinessDomain, PmwbKnowledgeItem, now_cn
from services import knowledge_link_service as kls
from utils.obsidian import read_markdown, write_markdown

CODE = 'fxtb'
BACKUP_DIR = 'D:/项目/个人工作台系统/data/backup_main_note_capability_20261126'

# 映射：源块编号前缀 -> 功能说明模板章节号
# 1.x 功能概述 / 2.x 覆盖对象 / 3.x+6.x 实现流程与配置 / 4.x+5.x+7.x+8.x+9.x 数据说明与规则
PREFIX_TO_SEC = {
    '1': '1', '2': '2', '3': '3', '6': '3',
    '4': '4', '5': '4', '7': '4', '8': '4', '9': '4',
}
# 模板里已有的子节标题（占位），归位时跳过其空壳正文，由真实块填
STANDARD_SUB_NOS = {'2.1', '2.2', '3.1', '3.2', '4.1', '4.2'}
AUTO_SPLIT = re.compile(
    r'<!--\s*PMWB:AUTO:BEGIN\s+key=(\w+)\s*-->.*?<!--\s*PMWB:AUTO:END\s+key=\1\s*-->',
    re.DOTALL,
)


def parse_blocks(content: str):
    """返回 [(prefix, leaf_title, body)]，识别 N. / N、 / N\\.M 三种编号。"""
    lines = content.splitlines()
    marks = []
    for idx, line in enumerate(lines):
        s = line.strip()
        m = re.match(r'^#{1,4}\s+(.*)$', s)
        if not m:
            continue
        text = m.group(1)
        # 转义编号 1\.1 或普通 1.1 或 H1 章节 4、
        nm = re.match(r'^(\d+)\s*(?:\\?\.\s*(\d+)\s*|、\s*)(.*)$', text)
        if nm:
            prefix = nm.group(1)
            leaf = nm.group(2) or ''
            marks.append((idx, prefix, leaf, text))
    blocks = []
    for k, (idx, prefix, leaf, text) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else len(lines)
        body = '\n'.join(lines[idx + 1:end]).strip('\n')
        blocks.append((prefix, leaf, text, body))
    return blocks


def meaningful_art(body: str) -> list:
    """抽取实质人工正文行（排除 AUTO 块/占位/表头分隔/自动区说明）。"""
    out = []
    txt = AUTO_SPLIT.sub('', body)
    for line in txt.splitlines():
        s = line.strip()
        if not s or s.startswith('<!--') or s.startswith('#'):
            continue
        if s.startswith('> ') or s.startswith('_暂无'):
            continue
        if re.match(r'^\|[-:|]+\|$', s) or set(s) <= set('|- '):
            continue
        if any(p in s for p in ('自动区：由', '人工维护区，自动沉淀不覆盖', '由系统自动维护')):
            continue
        out.append(s)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    db = SessionLocal()
    d = db.query(PmwbBusinessDomain).filter_by(domain_code=CODE).first()
    item = db.query(PmwbKnowledgeItem).filter_by(domain_code=CODE, note_type='main').first()
    rel = item.obsidian_path.replace('\\', '/')
    text = read_markdown(rel)
    assert d and item and text, 'GIMS 领域/主笔记缺失'

    std = kls.build_main_note_markdown(d, item.item_id, now_cn().strftime('%Y-%m-%d'))
    blocks = parse_blocks(text)

    # 原人工正文（基准）：所有 block 的实质行
    # 尾部 B 模板残留（### 2.1 产品矩阵 / ### 3.1 常见服务场景 ...）是空壳，
    # 无实质人工正文；其 H1「GIMS反向地址同步 业务知识主笔记」也无正文，
    # 提取时排除，避免重排后出现第二个 H1 / 孤儿 MOC。
    original_art = []
    for prefix, leaf, title, body in blocks:
        if re.match(r'^#{1,4}\s+GIMS反向地址同步 业务知识主笔记', title):
            continue
        original_art.extend(meaningful_art(body))
    # H1 `# 1. 业务概述` 无编号前缀的正文（文档定位/需求来源）也属人工内容：
    # prefix 已识别为 '1'，上面循环已覆盖；这里再兜底扫描全文非块实质行。
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('**文档定位：') or s.startswith('**需求来源：'):
            if s not in original_art:
                original_art.append(s)

    # 按目标章节收集子块：{sec: [(leaf_no, leaf_title, art_lines)]}
    sec_buckets = defaultdict(list)
    for prefix, leaf, title, body in blocks:
        art = meaningful_art(body)
        if not art:
            continue
        sec = PREFIX_TO_SEC.get(prefix)
        if not sec:
            continue
        sec_buckets[sec].append((leaf, title, art))

    # AUTO 块：按 key 取最丰富内容
    auto_best = {}
    # 只匹配 BEGIN/END 成对且 END key 与 BEGIN 一致的完整块——
    # 原文尾部有 BEGIN 无 END 的截断块，非贪婪正则会吞掉其后全部内容（含 B 模板残留）。
    for m in re.finditer(
        r'<!--\s*PMWB:AUTO:BEGIN\s+key=(\w+)\s*-->(.*?)<!--\s*PMWB:AUTO:END\s+key=\1\s*-->',
        text, re.DOTALL,
    ):
        key, body = m.group(1), m.group(2).strip()
        if not body or body.startswith('_暂无'):
            continue
        # 丢弃「跨 BEGIN」的伪配对：正文里又出现 PMWB:AUTO:BEGIN，
        # 说明该 END 属于后面的块（原文 369 BEGIN 无 END，408 才成对）。
        if 'PMWB:AUTO:BEGIN' in body:
            continue
        if key not in auto_best or len(body) > len(auto_best[key]):
            auto_best[key] = body

    new = std
    # §1-§4 填入真实内容（替换占位子节）
    sec_titles = {
        '1': '1. 功能概述',
        '2': '2. 覆盖对象与差异化规则',
        '3': '3. 实现流程与配置',
        '4': '4. 数据说明与规则',
    }
    for sec, subs in sec_buckets.items():
        parts = []
        for leaf, title, art in subs:
            clean_title = re.sub(r'^(?:\d+\s*\\?\.\s*\d+\s*|\d+\s*、\s*)', '', title).strip()
            # 三级子节用中文标题（不带 N.M 数字前缀），避免 _is_standard_structure
            # 把 ### 1.1 误计为 ## 1. 的重复编号；内容一行不改。
            parts.append(f'### {clean_title}\n\n' + '\n'.join(art))
        merged = '\n\n'.join(parts)
        new = kls._prepend_to_section(new, sec_titles[sec], merged)

    for key, body in auto_best.items():
        new = kls._replace_auto_block(new, key, body)

    # 防丢校验：原文实质行逐行必须仍在新文本中（按整行内容，不受切片影响）
    new_lines = set(x.strip() for x in new.splitlines())
    missing = [x for x in original_art if x not in new_lines]
    print(f'{CODE} 原人工行 {len(original_art)}，丢失 {len(missing)}')
    for m in missing[:8]:
        print('  缺失:', m[:90])

    if missing:
        print('ABORT: 人工正文有丢失，拒绝写盘')
        db.close()
        return

    ok = kls._is_standard_structure(new)
    lines = new.splitlines()
    h1pos = [n for n, l in enumerate(lines, 1) if l.startswith('# ')]
    heads = [int(m.group(1)) for l in lines for m in [re.match(r'^## (\d+)\.', l)] if m]
    orph_moc = [n for n, l in enumerate(lines, 1) if l.strip() == '## 相关子笔记 MOC']
    print(f'结构规范={ok} fm={new.startswith("---")} H1={h1pos[:3]} heads={heads[:15]} 孤儿MOC={orph_moc}')
    print(f'行数 {len(text.splitlines())} -> {len(new.splitlines())}')
    for n in range(360, min(378, len(lines))):
        print('  L%d %s' % (n, lines[n-1][:80]))
    if not ok:
        print('ABORT: 结构不规范')
        db.close()
        return

    if args.apply:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        shutil.copy2(os.path.join('D:/项目/知识图谱', rel),
                     os.path.join(BACKUP_DIR, CODE + '-before-gims.md'))
        write_markdown(rel, new, protect_if_modified=False)
        kls.rebuild_main_note_section7(db, CODE)
        kls.rebuild_main_note_subnotes(db, CODE)
        db.commit()
        print('APPLIED', CODE, rel)
    else:
        print('DRY-RUN only')
    db.close()


if __name__ == '__main__':
    main()
