import os
import sys
import json
from datetime import datetime, timezone

sys.path.insert(0, os.getcwd())

from app.db import SessionLocal
from app.models import Article, Source, ArticleAIOutput
from ingestion.pipeline import run_ingestion_pipeline

def run_controlled_ingestion():
    db = SessionLocal()
    try:
        # Record BEFORE state
        total_before = db.query(Article).count()
        latest_before = db.query(Article).order_by(Article.id.desc()).first()
        latest_before_id = latest_before.id if latest_before else 0
        latest_before_collected = latest_before.collected_at.isoformat() if (latest_before and latest_before.collected_at) else None
        
        print("=" * 70)
        print("RECORDING BEFORE INGESTION STATE")
        print("=" * 70)
        print(f"Total Articles BEFORE: {total_before}")
        print(f"Latest Article ID BEFORE: {latest_before_id}")
        print(f"Latest collected_at BEFORE: {latest_before_collected}")
        
        print("\nRunning Live Ingestion Pipeline across all sources...")
        summary = run_ingestion_pipeline(db)
        
        # Record AFTER state
        total_after = db.query(Article).count()
        latest_after = db.query(Article).order_by(Article.id.desc()).first()
        newest_after_id = latest_after.id if latest_after else 0
        newest_after_collected = latest_after.collected_at.isoformat() if (latest_after and latest_after.collected_at) else None
        
        print("\n" + "=" * 70)
        print("RECORDING AFTER INGESTION STATE")
        print("=" * 70)
        print(f"Active Sources Processed: {summary.active_sources_processed}")
        print(f"Healthy Feeds: {summary.healthy_feeds}")
        print(f"Empty Feeds: {summary.empty_feeds}")
        print(f"Failed Feeds: {summary.failed_feeds}")
        print(f"Articles Fetched/Discovered: {summary.articles_fetched}")
        print(f"NEW Articles Inserted: {summary.new_articles}")
        print(f"Duplicates Skipped: {summary.duplicates_skipped}")
        print(f"Total Articles AFTER: {total_after}")
        print(f"Newest Article ID AFTER: {newest_after_id}")
        print(f"Newest collected_at AFTER: {newest_after_collected}")
        
        # Query newly inserted articles
        new_articles = db.query(Article).filter(Article.id > latest_before_id).order_by(Article.id.asc()).all()
        print(f"\nDetails for {len(new_articles)} Newly Inserted Articles:")
        
        inserted_log = []
        for art in new_articles:
            src_name = art.source.name if art.source else "Unknown"
            has_summary = bool(art.raw_summary and len(art.raw_summary.strip()) > 0)
            ai_out = db.query(ArticleAIOutput).filter(ArticleAIOutput.article_id == art.id).first()
            ai_status = "PROCESSED" if ai_out else "PENDING"
            
            info = {
                "article_id": art.id,
                "source": src_name,
                "title": art.title,
                "canonical_url": art.canonical_url,
                "published_at": art.published_at.isoformat() if art.published_at else None,
                "collected_at": art.collected_at.isoformat() if art.collected_at else None,
                "raw_summary_present": has_summary,
                "ai_processing_status": ai_status
            }
            inserted_log.append(info)
            print(f"  [ID {art.id}] Source: '{src_name}' | Title: '{art.title[:50]}...' | Pub: {art.published_at}")

        output_data = {
            "before_state": {
                "total_articles": total_before,
                "latest_article_id": latest_before_id,
                "latest_collected_at": latest_before_collected
            },
            "after_state": {
                "total_articles": total_after,
                "newest_article_id": newest_after_id,
                "newest_collected_at": newest_after_collected,
                "articles_discovered": summary.articles_fetched,
                "new_articles_inserted": summary.new_articles,
                "duplicates_skipped": summary.duplicates_skipped,
                "healthy_feeds": summary.healthy_feeds,
                "empty_feeds": summary.empty_feeds,
                "failed_feeds": summary.failed_feeds,
            },
            "inserted_articles": inserted_log
        }
        
        with open("scratch/controlled_ingestion_results.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)
            
        print("\nControlled ingestion results saved to scratch/controlled_ingestion_results.json")

    finally:
        db.close()

if __name__ == "__main__":
    run_controlled_ingestion()
