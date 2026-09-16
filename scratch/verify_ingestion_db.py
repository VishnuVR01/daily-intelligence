import os
import sys
import json
from datetime import datetime, timezone

sys.path.insert(0, os.getcwd())

from app.db import SessionLocal
from app.models import Article, Source, ArticleAIOutput

def verify_db_ingestion():
    db = SessionLocal()
    try:
        latest_before_id = 3819
        total_now = db.query(Article).count()
        latest_article = db.query(Article).order_by(Article.id.desc()).first()
        
        new_articles = db.query(Article).filter(Article.id > latest_before_id).order_by(Article.id.asc()).all()
        
        print("=" * 70)
        print("POSTGRESQL INGESTION VERIFICATION")
        print("=" * 70)
        print(f"Total Articles in DB: {total_now}")
        print(f"New Articles Inserted: {len(new_articles)}")
        print(f"Newest Article ID: {latest_article.id if latest_article else 'None'}")
        print(f"Newest collected_at: {latest_article.collected_at if latest_article else 'None'}")
        print(f"Newest published_at: {latest_article.published_at if latest_article else 'None'}")
        
        # Verify source relationships and raw summary presence
        sources_represented = set()
        summaries_present = 0
        canonical_urls_present = 0
        
        inserted_list = []
        for a in new_articles:
            sources_represented.add(a.source.name if a.source else "Unknown")
            if a.raw_summary and len(a.raw_summary.strip()) > 0:
                summaries_present += 1
            if a.canonical_url and len(a.canonical_url.strip()) > 0:
                canonical_urls_present += 1
                
            inserted_list.append({
                "article_id": a.id,
                "source_name": a.source.name if a.source else "Unknown",
                "title": a.title,
                "canonical_url": a.canonical_url,
                "published_at": a.published_at.isoformat() if a.published_at else None,
                "collected_at": a.collected_at.isoformat() if a.collected_at else None,
                "raw_summary_present": bool(a.raw_summary and len(a.raw_summary.strip()) > 0),
                "ai_processing_status": "PENDING"
            })
            
        print(f"\nSummary of New Articles:")
        print(f"  Distinct Sources Represented: {len(sources_represented)}")
        print(f"  Articles with Canonical URLs: {canonical_urls_present} / {len(new_articles)}")
        print(f"  Articles with Raw Summaries: {summaries_present} / {len(new_articles)}")
        
        # Save verification details to JSON
        with open("scratch/db_ingestion_verified.json", "w", encoding="utf-8") as f:
            json.dump({
                "total_articles_now": total_now,
                "new_articles_count": len(new_articles),
                "newest_article_id": latest_article.id if latest_article else 0,
                "newest_collected_at": latest_article.collected_at.isoformat() if (latest_article and latest_article.collected_at) else None,
                "distinct_sources_count": len(sources_represented),
                "new_articles": inserted_list
            }, f, indent=2)

    finally:
        db.close()

if __name__ == "__main__":
    verify_db_ingestion()
