import sys, traceback
sys.stdout.reconfigure(encoding='utf-8')
try:
    from db.base import SessionLocal
    from services.knowledge_link_service import ensure_domain_main_notes
    db = SessionLocal()
    try:
        r = ensure_domain_main_notes(db)
        print("OK", r)
    finally:
        db.close()
except Exception:
    traceback.print_exc()
