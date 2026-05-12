"""
Initialize database tables. Run once on first startup.
Also creates the Qdrant collection if not exists.
"""
import sys
import os
sys.path.insert(0, '/app')

from db.database import engine
from db import models

def init_db():
    print("[InitDB] Creating tables...")
    models.Base.metadata.create_all(bind=engine)
    print("[InitDB] Tables created:")
    for table in models.Base.metadata.tables:
        print(f"  - {table}")

    print("[InitDB] Checking Qdrant...")
    try:
        from db.qdrant_store import get_qdrant_store
        store = get_qdrant_store()
        store._get_client()  # This creates collection if not exists
        print("[InitDB] Qdrant ready")
    except Exception as e:
        print(f"[InitDB] Qdrant not available (will use fallback): {e}")

if __name__ == '__main__':
    init_db()
    print("[InitDB] Done!")
