import sys
sys.stdout.reconfigure(encoding='utf-8')
from db.base import SessionLocal
from db.models import PmwbBusinessDomain
db=SessionLocal()
rows=db.query(PmwbBusinessDomain).order_by(PmwbBusinessDomain.domain_group, PmwbBusinessDomain.sort_order).all()
print(f"{'code':28} {'name':12} {'group':8} {'parent_id':10} {'enabled':8}")
for r in rows:
    print(f"{r.domain_code:28} {r.domain_name:12} {str(r.domain_group):8} {str(r.parent_id):10} {str(r.enabled):8}")
print('TOTAL', len(rows))
db.close()
