import sys
import os
sys.path.insert(0, os.path.abspath("."))
from datetime import datetime, timedelta, timezone
import json
import httpx
from app.db import SessionLocal
from app.models import Article, ArticleAIOutput, Source

def run_pipeline_audit():
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        # Latest collected article
        latest_article = db.query(Article).order_by(Article.collected_at.desc()).first()
        min_since_ingestion = (now - latest_article.collected_at).total_seconds() / 60.0 if latest_article and latest_article.collected_at else None

        # Latest AI processed article
        latest_ai = db.query(ArticleAIOutput).order_by(ArticleAIOutput.processed_at.desc()).first()
        min_since_ai = (now - latest_ai.processed_at).total_seconds() / 60.0 if latest_ai and latest_ai.processed_at else None

        # Check Ollama availability
        ollama_status = "DOWN"
        try:
            r = httpx.get("http://localhost:11434/api/tags", timeout=3.0)
            if r.status_code == 200:
                ollama_status = "UP"
        except Exception:
            ollama_status = "DOWN"

        # Check fresh vs backlog queue
        # Fresh articles: collected within 12 hours
        fresh_cutoff = now - timedelta(hours=12)
        
        # Unprocessed article IDs
        ai_subquery = db.query(ArticleAIOutput.article_id)
        unprocessed_articles = db.query(Article).filter(Article.id.not_in(ai_subquery)).all()

        fresh_unprocessed = [a for a in unprocessed_articles if a.collected_at and a.collected_at >= fresh_cutoff]
        backlog_unprocessed = [a for a in unprocessed_articles if not a.collected_at or a.collected_at < fresh_cutoff]

        oldest_fresh_wait = (now - min(a.collected_at for a in fresh_unprocessed)).total_seconds() / 60.0 if fresh_unprocessed else 0.0
        oldest_backlog_wait = (now - min(a.collected_at for a in backlog_unprocessed)).total_seconds() / 3600.0 if backlog_unprocessed else 0.0

        res = {
            "min_since_ingestion": round(min_since_ingestion, 1) if min_since_ingestion else None,
            "min_since_ai": round(min_since_ai, 1) if min_since_ai else None,
            "latest_ingestion_time": latest_article.collected_at.isoformat() if latest_article else None,
            "latest_ai_time": latest_ai.processed_at.isoformat() if latest_ai else None,
            "ollama_status": ollama_status,
            "fresh_unprocessed_count": len(fresh_unprocessed),
            "backlog_unprocessed_count": len(backlog_unprocessed),
            "oldest_fresh_wait_minutes": round(oldest_fresh_wait, 1),
            "oldest_backlog_wait_hours": round(oldest_backlog_wait, 1),
        }

        print(json.dumps(res, indent=2))
        return res
    finally:
        db.close()

if __name__ == "__main__":
    run_pipeline_audit()
