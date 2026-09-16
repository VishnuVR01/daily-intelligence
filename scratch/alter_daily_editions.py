from app.db import engine
from sqlalchemy import text

def alter_editions():
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE daily_editions ADD COLUMN IF NOT EXISTS readiness TEXT NOT NULL DEFAULT 'PREPARING';"))
        conn.execute(text("ALTER TABLE daily_editions ADD COLUMN IF NOT EXISTS lead_event_cluster_id TEXT;"))
        conn.execute(text("ALTER TABLE daily_editions ADD COLUMN IF NOT EXISTS event_count INTEGER NOT NULL DEFAULT 0;"))
        conn.execute(text("ALTER TABLE daily_editions ADD COLUMN IF NOT EXISTS audit_json JSON;"))
        conn.commit()
    print("Postgres daily_editions columns added successfully.")

if __name__ == "__main__":
    alter_editions()
