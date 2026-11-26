"""近期新增业务领域的轨迹错挂迁移（dry_run 默认，--apply 才写）。

背景：公寓宽带/公寓电视/跨省企业宽带/E企组网/集团千里眼 等领域新建后，
此前保存在旧领域下的会议/需求/运营工单未改挂，导致主笔记 §7 索引缺失。

覆盖：主表 domain_code + 沉淀表 pmwb_knowledge_item + 关联表 pmwb_knowledge_link
（沉淀键：meeting=id，requirement=req_id，operation_issue 无沉淀）。
每条先校验原 domain_code 与预期一致，不一致则跳过并报错，避免误迁。
最后对涉及的旧/新领域重建主笔记 §7 索引。

用法：
    python scripts/migrate_misassigned_domains.py            # dry_run
    python scripts/migrate_misassigned_domains.py --apply     # 实际迁移
"""
import argparse
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.abspath('backend'))
from dotenv import load_dotenv
for _p in ['backend/.env', os.path.join(os.getcwd(), 'backend', '.env'), '.env']:
    if os.path.exists(_p):
        load_dotenv(_p)
        break

from db.base import SessionLocal
from db.models import now_cn
from services import knowledge_link_service as kls

# (主表, 主键id, 预期原domain_code, 目标domain_code, 沉淀source_type)
# requirement 的 source_id 在运行时从 req_id 读取
JOBS = [
    # 公寓宽带 GYKD
    ('pmwb_meeting', 41, 'ywt-broadband', 'GYKD', 'meeting'),
    ('pmwb_meeting', 52, 'ywt-broadband', 'GYKD', 'meeting'),
    ('pmwb_meeting', 89, 'ywt-broadband', 'GYKD', 'meeting'),
    ('pmwb_requirement_ext', 58, 'ywt-broadband', 'GYKD', 'requirement'),
    ('pmwb_requirement_ext', 86, 'ywt-broadband', 'GYKD', 'requirement'),
    ('pmwb_operation_issue', 19, 'ywt-broadband', 'GYKD', 'operation'),
    ('pmwb_operation_issue', 51, 'ywt-broadband', 'GYKD', 'operation'),
    ('pmwb_operation_issue', 70, 'ywt-broadband', 'GYKD', 'operation'),
    ('pmwb_operation_issue', 183, 'ywt-broadband', 'GYKD', 'operation'),
    ('pmwb_operation_issue', 227, 'ywt-broadband', 'GYKD', 'operation'),
    ('pmwb_operation_issue', 237, 'ywt-broadband', 'GYKD', 'operation'),
    ('pmwb_operation_issue', 257, 'ywt-broadband', 'GYKD', 'operation'),
    # 公寓电视 GKDS
    ('pmwb_meeting', 113, 'ywt-tv', 'GKDS', 'meeting'),
    ('pmwb_requirement_ext', 105, 'ywt-tv', 'GKDS', 'requirement'),
    ('pmwb_operation_issue', 217, 'ywt-tv', 'GKDS', 'operation'),
    # 跨省企业宽带 KSQYKD
    ('pmwb_meeting', 141, 'ywt-broadband', 'KSQYKD', 'meeting'),
    ('pmwb_requirement_ext', 116, None, 'KSQYKD', 'requirement'),
    # E企组网 EQZW
    ('pmwb_requirement_ext', 85, 'ywt-eqyk', 'EQZW', 'requirement'),
    ('pmwb_requirement_ext', 115, None, 'EQZW', 'requirement'),
    # 集团千里眼 jtqly
    ('pmwb_requirement_ext', 61, 'security', 'jtqly', 'requirement'),
    ('pmwb_requirement_ext', 118, None, 'jtqly', 'requirement'),
]

TITLE_COL = {
    'pmwb_meeting': 'title',
    'pmwb_requirement_ext': 'req_name',
    'pmwb_operation_issue': 'title',
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='实际迁移（默认仅 dry_run）')
    args = ap.parse_args()

    db = SessionLocal()
    planned = []
    errors = []
    touched_domains = set()

    for table, rid, expect, target, stype in JOBS:
        tcol = TITLE_COL[table]
        # 使用原生 SQL，避免 ORM 映射差异
        from sqlalchemy import text
        r = db.execute(text(f'SELECT domain_code, {tcol} AS ttl FROM {table} WHERE id=:i'), {'i': rid}).fetchone()
        if not r:
            errors.append(f'{table}:{rid} 记录不存在')
            continue
        cur = r[0]
        if cur != expect:
            errors.append(f'{table}:{rid} 原领域={cur!r} 预期={expect!r}，跳过')
            continue

        source_id = None
        if stype in ('meeting', 'operation'):
            source_id = str(rid)
        elif stype == 'requirement':
            rr = db.execute(text('SELECT req_id FROM pmwb_requirement_ext WHERE id=:i'), {'i': rid}).fetchone()
            source_id = rr[0] if rr else None

        ki_cnt = kl_cnt = 0
        if source_id:
            ki_cnt = db.execute(
                text('SELECT COUNT(*) FROM pmwb_knowledge_item WHERE source_type=:st AND source_id=:sid'),
                {'st': stype, 'sid': source_id},
            ).scalar()
            kl_cnt = db.execute(
                text('SELECT COUNT(*) FROM pmwb_knowledge_link WHERE source_type=:st AND source_id=:sid'),
                {'st': stype, 'sid': source_id},
            ).scalar()

        planned.append((table, rid, r[1], cur, target, stype, source_id, ki_cnt, kl_cnt))
        touched_domains.update(x for x in (cur, target) if x)

    print(f'待迁移: {len(planned)} 条，校验失败: {len(errors)} 条\n')
    for table, rid, ttl, cur, target, stype, sid, ki, kl in planned:
        print(f'[{table}:{rid}] {str(cur):15} -> {target:8} | KI={ki} KL={kl} | {str(ttl)[:48]}')
    for e in errors:
        print(f'[ERROR] {e}')

    if not args.apply:
        print('\nDRY RUN，未写库。加 --apply 执行。')
        db.close()
        return

    if errors:
        print('\n存在校验失败，拒绝执行（避免部分迁移）。')
        db.close()
        sys.exit(2)

    from sqlalchemy import text
    stamp = now_cn()
    for table, rid, ttl, cur, target, stype, sid, ki, kl in planned:
        db.execute(text(f'UPDATE {table} SET domain_code=:t, updated_at=:ts WHERE id=:i'),
                   {'t': target, 'i': rid, 'ts': stamp})
        if sid:
            # 原领域限定，避免同 source_id 跨领域记录被批量误改（库中存在此类反例）
            scope = ' AND domain_code=:old' if cur else ' AND domain_code IS NULL'
            params = {'t': target, 'ts': stamp, 'st': stype, 'sid': sid}
            if cur:
                params['old'] = cur
            db.execute(text('UPDATE pmwb_knowledge_item SET domain_code=:t, updated_at=:ts '
                            'WHERE source_type=:st AND source_id=:sid' + scope), params)
            db.execute(text('UPDATE pmwb_knowledge_link SET domain_code=:t, updated_at=:ts '
                            'WHERE source_type=:st AND source_id=:sid' + scope), params)
        print(f'MIGRATED {table}:{rid} -> {target}')
    db.commit()

    # 重建涉及领域的 §7 索引
    rebuilt = []
    for code in sorted(touched_domains):
        try:
            if kls.rebuild_main_note_section7(db, code):
                rebuilt.append(code)
        except Exception as ex:
            print(f'[WARN] 重建 {code} §7 失败: {ex}')
    db.commit()
    print(f'\n已迁移 {len(planned)} 条；§7 重建: {rebuilt}')
    db.close()


if __name__ == '__main__':
    main()
