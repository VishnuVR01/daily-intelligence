import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

sys.path.insert(0, os.getcwd())

from app.db import SessionLocal
from app.models import Article, Source, ArticleAIOutput
from app.config import get_settings
from repositories.articles import get_today_ai_context_stats
from ingestion.rss import fetch_feed

def audit_before_state():
    db = SessionLocal()
    try:
        settings = get_settings()
        tz = ZoneInfo(settings.app_timezone or "Europe/London")
        now_local = datetime.now(tz)
        today_local = now_local.date()
        
        # All sources
        sources = db.query(Source).order_by(Source.id.asc()).all()
        active_sources = [s for s in sources if s.active]
        inactive_sources = [s for s in sources if not s.active]
        
        # Articles count
        total_articles = db.query(Article).count()
        latest_article = db.query(Article).order_by(Article.id.desc()).first()
        
        # Latest collected_at
        latest_collected = db.query(Article).order_by(Article.collected_at.desc()).first()
        
        # AI Output counts
        total_ai_outputs = db.query(ArticleAIOutput).count()
        relevant_ai_count = db.query(ArticleAIOutput).filter(ArticleAIOutput.is_relevant == True).count()
        failed_pending_ai = total_articles - total_ai_outputs
        
        # Today's stats
        today_stats = get_today_ai_context_stats(db)
        
        print("=" * 70)
        print("BEFORE INGESTION AUDIT & SYSTEM STATE")
        print("=" * 70)
        print(f"Total Sources Configured: {len(sources)}")
        print(f"  Active Sources: {len(active_sources)}")
        print(f"  Inactive Sources: {len(inactive_sources)}")
        print(f"Total Articles in DB: {total_articles}")
        print(f"Latest Article ID: {latest_article.id if latest_article else 'None'}")
        print(f"Latest Article Title: {latest_article.title if latest_article else 'None'}")
        print(f"Latest collected_at: {latest_collected.collected_at if latest_collected else 'None'}")
        print(f"Total AI Outputs Processed: {total_ai_outputs}")
        print(f"Total Relevant AI Articles: {relevant_ai_count}")
        print(f"Failed/Pending AI Processing: {failed_pending_ai}")
        print("\nToday in Context Stats (Europe/London):")
        for k, v in today_stats.items():
            print(f"  {k}: {v}")
            
        print("\nActive Sources Detail:")
        for s in active_sources:
            # Count articles for this source
            count = db.query(Article).filter(Article.source_id == s.id).count()
            latest_src_art = db.query(Article).filter(Article.source_id == s.id).order_by(Article.published_at.desc()).first()
            last_pub = latest_src_art.published_at if latest_src_art else None
            print(f"  ID {s.id}: [{s.name}] type='{s.source_type}' url='{s.feed_url}' (Articles in DB: {count}, Latest Published: {last_pub})")

    finally:
        db.close()

if __name__ == "__main__":
    audit_before_state()
