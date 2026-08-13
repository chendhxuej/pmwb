"""批量回流：对所有启用且有主笔记的业务领域执行 sync_main_note_from_links（幂等可重跑）。

把各领域归属的关联工单/关联记录聚合进主笔记 AUTO 块（§2.3/§3.2/§4.2/§5/§6/§9）。
其中 §9 时间线已与 business_timeline API 对齐，纳入 domain_code 归属的需求/会议/运营工单。
"""
import sys, os
sys.path.insert(0, os.path.abspath('backend'))
from dotenv import load_dotenv
for p in ['backend/.env', os.path.join(os.getcwd(), 'backend', '.env'), '.env']:
    if os.path.exists(p):
        load_dotenv(p)
        break

from db.base import SessionLocal, engine
engine.echo = False
from services.knowledge_link_service import sync_main_note_from_links
from db.models import PmwbBusinessDomain, PmwbKnowledgeItem

db = SessionLocal()
changed_total = 0
for d in sorted(db.query(PmwbBusinessDomain).filter(PmwbBusinessDomain.enabled == True).all(),
                key=lambda x: x.domain_code):
    dc = d.domain_code
    main = db.query(PmwbKnowledgeItem).filter_by(domain_code=dc, note_type='main').first()
    if not main:
        print(f"skip(no-main) {dc}")
        continue
    r = sync_main_note_from_links(db, dc)
    if r.get('changed'):
        changed_total += 1
        print(f"FILLED {dc}: blocks={r.get('blocks_written')} reqs={r.get('requirements_scanned')} links={r.get('links_scanned')}")
    else:
        print(f"noop   {dc}")
print(f"\n共 {changed_total} 个领域主笔记被填充/更新")
db.close()
