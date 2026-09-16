import sys
import os
sys.path.insert(0, os.path.abspath("."))
import json
from app.db import SessionLocal
from repositories.articles import get_today_ai_context_stats

def run_today_audit():
    db = SessionLocal()
    try:
        stats = get_today_ai_context_stats(db, tz_name="Europe/London")
        print(json.dumps(stats, indent=2))

        collected = stats["articles_collected_today"]
        published = stats["articles_published_today"]
        ai_processed = stats["ai_processed"]
        relevant = stats["relevant_today"]
        oos = stats["out_of_scope_today"]
        awaiting = stats["awaiting_ai_processing"]
        failed = stats["ai_processing_failed"]
        cov = stats["processing_coverage"]

        # Verification check
        total_pop = ai_processed + awaiting + failed
        print(f"\nVERIFICATION CHECK:")
        print(f"AI Processed ({ai_processed}) + Awaiting ({awaiting}) + Failed ({failed}) = {total_pop}")
        print(f"Coverage %: {cov}%")
        return stats
    finally:
        db.close()

if __name__ == "__main__":
    run_today_audit()
