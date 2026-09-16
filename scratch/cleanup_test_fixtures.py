import sys
import json
from datetime import datetime, timezone
sys.path.insert(0, '.')

from app.db import SessionLocal
from app.models import Article, ArticleAIOutput, Source, ArticleCountry, SavedArticle

def cleanup_fixtures():
    db = SessionLocal()
    
    print("=== Phase 2: Test Fixture Contamination Cleanup Audit ===")
    
    total_articles_before = db.query(Article).count()
    total_sources_before = db.query(Source).count()
    total_ai_outputs_before = db.query(ArticleAIOutput).count()
    
    print(f"Before Cleanup:")
    print(f"  Total Articles:   {total_articles_before}")
    print(f"  Total Sources:    {total_sources_before}")
    print(f"  Total AI Outputs: {total_ai_outputs_before}")
    
    # Identify test sources
    test_sources = db.query(Source).filter(
        (Source.name.ilike("%test%")) |
        (Source.feed_url.ilike("%test.com%"))
    ).all()
    
    test_source_ids = [s.id for s in test_sources]
    print(f"\nIdentified {len(test_sources)} test sources:")
    for s in test_sources:
        print(f"  Source ID={s.id} | Name={s.name} | Feed URL={s.feed_url}")
        
    # Identify test articles
    test_articles = db.query(Article).filter(
        (Article.source_id.in_(test_source_ids)) |
        (Article.title == "Test Title") |
        (Article.canonical_url.ilike("%test.com%")) |
        (Article.canonical_url.ilike("%stage1d_article%"))
    ).all()
    
    test_article_ids = [a.id for a in test_articles]
    print(f"\nIdentified {len(test_articles)} proven test fixture articles:")
    audit_log = []
    for a in test_articles:
        src_name = a.source.name if a.source else "N/A"
        col_str = a.collected_at.isoformat() if a.collected_at else "N/A"
        item = {
            "article_id": a.id,
            "source_id": a.source_id,
            "source_name": src_name,
            "title": a.title,
            "canonical_url": a.canonical_url,
            "collected_at": col_str,
            "proven_fixture_reason": "Leaked from test_stage_1d.py / test_dedupe.py test runs",
        }
        audit_log.append(item)
        print(f"  Article ID={a.id:<6} | Source={src_name:<25} | Title={a.title:<20} | URL={a.canonical_url}")

    if not test_articles and not test_sources:
        print("\nNo test fixtures to clean up.")
        db.close()
        return

    # Transactional cleanup
    try:
        # Delete test articles (cascade deletes relationships)
        deleted_articles_count = db.query(Article).filter(Article.id.in_(test_article_ids)).delete(synchronize_session=False)
        # Delete test sources
        deleted_sources_count = db.query(Source).filter(Source.id.in_(test_source_ids)).delete(synchronize_session=False)
        
        # Clean up any orphaned AI outputs or references if any
        orphaned_ai = db.query(ArticleAIOutput).filter(~ArticleAIOutput.article_id.in_(db.query(Article.id))).delete(synchronize_session=False)
        
        db.commit()
        print(f"\nSuccessfully committed cleanup transaction:")
        print(f"  Deleted Articles: {deleted_articles_count}")
        print(f"  Deleted Sources:  {deleted_sources_count}")
        print(f"  Deleted Orphaned AI Outputs: {orphaned_ai}")
    except Exception as exc:
        db.rollback()
        print(f"Error during cleanup transaction: {exc}")
        db.close()
        return

    total_articles_after = db.query(Article).count()
    total_sources_after = db.query(Source).count()
    total_ai_outputs_after = db.query(ArticleAIOutput).count()

    print(f"\nAfter Cleanup Verification:")
    print(f"  Total Articles:   {total_articles_after} (Delta: -{total_articles_before - total_articles_after})")
    print(f"  Total Sources:    {total_sources_after} (Delta: -{total_sources_before - total_sources_after})")
    print(f"  Total AI Outputs: {total_ai_outputs_after} (Delta: -{total_ai_outputs_before - total_ai_outputs_after})")
    
    # Save audit log to scratch
    with open("scratch/fixture_cleanup_audit.json", "w", encoding="utf-8") as f:
        json.dump(audit_log, f, indent=2)
    print("Saved audit log to scratch/fixture_cleanup_audit.json")

    db.close()

if __name__ == "__main__":
    cleanup_fixtures()
