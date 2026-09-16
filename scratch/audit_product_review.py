import sys
import os
sys.path.insert(0, os.path.abspath("."))
from datetime import datetime, timezone
import json
from sqlalchemy import func, or_
from app.db import SessionLocal
from app.models import Article, Source, ArticleAIOutput
from repositories.ai_queue import get_ai_queue_status

def run_db_audit():
    db = SessionLocal()
    try:
        queue_status = get_ai_queue_status(db)

        total_articles = db.query(Article).count()
        total_sources = db.query(Source).count()
        active_sources = db.query(Source).filter(Source.active == True).count()
        ai_output_count = db.query(ArticleAIOutput).count()

        # Relevance breakdown
        relevant_count = db.query(ArticleAIOutput).filter(ArticleAIOutput.is_relevant == True).count()
        out_of_scope_count = db.query(ArticleAIOutput).filter(ArticleAIOutput.is_relevant == False).count()

        # Duplicate canonical URLs
        dupes_query = (
            db.query(Article.canonical_url, func.count(Article.id))
            .group_by(Article.canonical_url)
            .having(func.count(Article.id) > 1)
            .all()
        )
        duplicate_url_count = len(dupes_query)

        # Orphan AI outputs (AI outputs referencing non-existent article IDs)
        article_ids = set(r[0] for r in db.query(Article.id).all())
        ai_output_article_ids = [r[0] for r in db.query(ArticleAIOutput.article_id).all()]
        orphan_ai_outputs = sum(1 for aid in ai_output_article_ids if aid not in article_ids)

        # Orphan source references
        source_ids = set(r[0] for r in db.query(Source.id).all())
        article_source_ids = [r[0] for r in db.query(Article.source_id).all() if r[0] is not None]
        orphan_source_refs = sum(1 for sid in article_source_ids if sid not in source_ids)

        # Stuck / processing records
        stuck_processing = db.query(ArticleAIOutput).filter(ArticleAIOutput.status == "processing").all()

        # Future timestamps
        now = datetime.now(timezone.utc)
        future_published = db.query(Article).filter(Article.published_at > now).count()
        future_collected = db.query(Article).filter(Article.collected_at > now).count()

        # Malformed / Missing dates
        missing_published = db.query(Article).filter(Article.published_at.is_(None)).count()
        missing_collected = db.query(Article).filter(Article.collected_at.is_(None)).count()

        # Search for fixture patterns
        fixture_patterns = ["Test Title", "Dedupe Test Source", "Stage1D test sources", "Fixture"]
        fixture_article_matches = 0
        fixture_source_matches = 0

        for pat in fixture_patterns:
            fixture_article_matches += db.query(Article).filter(Article.title.ilike(f"%{pat}%")).count()
            fixture_source_matches += db.query(Source).filter(Source.name.ilike(f"%{pat}%")).count()

        res = {
            "queue_status": queue_status,
            "total_articles": total_articles,
            "total_sources": total_sources,
            "active_sources": active_sources,
            "ai_output_count": ai_output_count,
            "relevant_count": relevant_count,
            "out_of_scope_count": out_of_scope_count,
            "duplicate_url_count": duplicate_url_count,
            "orphan_ai_outputs": orphan_ai_outputs,
            "orphan_source_refs": orphan_source_refs,
            "stuck_processing_count": len(stuck_processing),
            "future_published": future_published,
            "future_collected": future_collected,
            "missing_published": missing_published,
            "missing_collected": missing_collected,
            "fixture_article_matches": fixture_article_matches,
            "fixture_source_matches": fixture_source_matches,
        }

        print(json.dumps(res, indent=2, default=str))
        return res
    finally:
        db.close()

if __name__ == "__main__":
    run_db_audit()
