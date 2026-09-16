import sys
import os
sys.path.insert(0, os.path.abspath("."))
from datetime import datetime, timedelta, timezone
import json
from sqlalchemy import func
from app.db import SessionLocal
from app.models import Article, Source

def run_source_audit():
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        sources = db.query(Source).all()
        results = []

        healthy_count = 0
        stale_count = 0
        empty_count = 0

        for s in sources:
            # Articles for this source
            articles = db.query(Article).filter(Article.source_id == s.id).order_by(Article.collected_at.desc()).all()
            art_count = len(articles)
            
            latest_art = articles[0] if art_count > 0 else None
            last_collected = latest_art.collected_at if latest_art else None
            latest_published = latest_art.published_at if latest_art else None

            hours_since_last = (now - last_collected).total_seconds() / 3600.0 if last_collected else None

            if art_count == 0:
                status = "EMPTY"
                empty_count += 1
            elif hours_since_last is not None and hours_since_last > 48.0:
                status = "STALE"
                stale_count += 1
            else:
                status = "HEALTHY"
                healthy_count += 1

            results.append({
                "id": s.id,
                "name": s.name,
                "type": s.source_type,
                "active": s.active,
                "article_count": art_count,
                "status": status,
                "hours_since_last_fetch": round(hours_since_last, 1) if hours_since_last else None,
                "latest_collected_at": last_collected.isoformat() if last_collected else None,
                "latest_published_at": latest_published.isoformat() if latest_published else None,
                "sample_title": latest_art.title[:60] if latest_art else None
            })

        summary = {
            "total_sources": len(sources),
            "healthy_sources": healthy_count,
            "stale_sources": stale_count,
            "empty_sources": empty_count,
            "failed_sources": 0,
            "disabled_sources": sum(1 for s in sources if not s.active),
            "sources_detail": results
        }

        print(json.dumps(summary, indent=2))
        return summary
    finally:
        db.close()

if __name__ == "__main__":
    run_source_audit()
