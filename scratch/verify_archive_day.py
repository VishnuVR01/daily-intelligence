import os
import sys
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.getcwd())

from app.db import SessionLocal
from app.models import Article
from app.config import get_settings
from repositories.articles import get_paginated_articles

def audit_archive_dates():
    db = SessionLocal()
    try:
        settings = get_settings()
        tz_name = settings.app_timezone or "Europe/London"
        tz = ZoneInfo(tz_name)
        
        # Test dates
        test_dates = ["2026-09-14", "2026-09-13", "2026-09-11", "2026-09-10", "2026-09-09"]
        
        print("=" * 70)
        print("POSTGRESQL DIRECT ARCHIVE DAY ARTICLE COUNTS")
        print("=" * 70)
        print(f"Timezone configured: {tz_name}")
        
        for date_str in test_dates:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            start_local = datetime(dt.year, dt.month, dt.day, 0, 0, 0, tzinfo=tz)
            end_local = start_local + timedelta(days=1)
            start_utc = start_local.astimezone(timezone.utc)
            end_utc = end_local.astimezone(timezone.utc)
            now_utc = datetime.now(timezone.utc)
            
            # Direct SQL count
            direct_count = (
                db.query(Article)
                .filter(
                    Article.published_at.is_not(None),
                    Article.published_at >= start_utc,
                    Article.published_at < end_utc,
                    Article.published_at <= now_utc,
                )
                .count()
            )
            
            # Count via get_paginated_articles page 1, 2, 3
            p1 = get_paginated_articles(db, page=1, page_size=25, date_str=date_str)
            p3 = get_paginated_articles(db, page=3, page_size=25, date_str=date_str)
            
            print(f"\nDate: {date_str} (Local range: {start_local} to {end_local} | UTC range: {start_utc} to {end_utc})")
            print(f"  Direct PostgreSQL Count : {direct_count}")
            print(f"  get_paginated_articles P1: Total={p1['total']}, Pages={p1['total_pages']}, Items={len(p1['articles'])}")
            print(f"  get_paginated_articles P3: Total={p3['total']}, Pages={p3['total_pages']}, Page={p3['page']}, Items={len(p3['articles'])}")

        # Check total database articles
        total_db = db.query(Article).count()
        print(f"\nTotal articles in entire DB: {total_db}")

    finally:
        db.close()

if __name__ == "__main__":
    audit_archive_dates()
