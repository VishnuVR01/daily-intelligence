"""
Script to execute Controlled Backlog Test (Sprint 1 Stage 1A Phase 6).
Processes maximum 5 real unprocessed articles using the AIWorker and outputs structured metrics.
"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.getcwd())

from app.db import SessionLocal
from app.models import Article, ArticleAIOutput, Source
from repositories.ai_queue import get_ai_queue_status
from services.ai.ollama import OllamaService
from services.ai.worker import AIWorker


def run_controlled_test():
    db = SessionLocal()
    try:
        print("=" * 80)
        print("STAGE 1A — CONTROLLED BACKLOG TEST (MAXIMUM 5 ARTICLES)")
        print("=" * 80)

        # 1. Capture BEFORE Queue Status
        before_status = get_ai_queue_status(db)
        print("\n[BEFORE QUEUE METRICS]")
        print(f"  Total Articles: {before_status['total_articles']}")
        print(f"  Unprocessed (Eligible): {before_status['unprocessed']}")
        print(f"  Processing: {before_status['processing']}")
        print(f"  Completed Relevant: {before_status['completed_relevant']}")
        print(f"  Completed Out of Scope: {before_status['completed_out_of_scope']}")
        print(f"  Failed: {before_status['failed']}")
        print(f"  Oldest Unprocessed Timestamp: {before_status['oldest_unprocessed_timestamp']}")

        # Capture snapshot of target articles before processing to verify 0 article row modifications
        unprocessed_candidates = (
            db.query(Article)
            .filter(~Article.ai_outputs.any())
            .order_by(Article.collected_at.asc().nullslast(), Article.id.asc())
            .limit(5)
            .all()
        )

        before_art_snapshots = {
            art.id: {
                "title": art.title,
                "canonical_url": art.canonical_url,
                "published_at": art.published_at.isoformat() if art.published_at else None,
                "collected_at": art.collected_at.isoformat() if art.collected_at else None,
                "raw_summary": art.raw_summary,
                "extracted_text": art.extracted_text,
                "source_id": art.source_id,
                "language": art.language,
            }
            for art in unprocessed_candidates
        }

        # 2. Run Worker on max 5 articles
        service = OllamaService()
        print(f"\nOllama Service Health: {service.get_health_status()}")

        worker = AIWorker(ollama_service=service)
        batch_result = worker.run_batch(db=db, batch_size=5)

        # 3. Capture AFTER Queue Status
        after_status = get_ai_queue_status(db)
        print("\n[AFTER QUEUE METRICS]")
        print(f"  Total Articles: {after_status['total_articles']}")
        print(f"  Unprocessed (Eligible): {after_status['unprocessed']}")
        print(f"  Processing: {after_status['processing']}")
        print(f"  Completed Relevant: {after_status['completed_relevant']}")
        print(f"  Completed Out of Scope: {after_status['completed_out_of_scope']}")
        print(f"  Failed: {after_status['failed']}")
        print(f"  Newest Processed Timestamp: {after_status['newest_processed_timestamp']}")

        # 4. Verify Article Table Row & Provenance Preservation
        article_modifications = 0
        provenance_corruptions = 0

        for art_id, snap in before_art_snapshots.items():
            current_art = db.query(Article).filter(Article.id == art_id).first()
            if not current_art:
                article_modifications += 1
                continue
            if (
                current_art.title != snap["title"]
                or current_art.canonical_url != snap["canonical_url"]
                or current_art.raw_summary != snap["raw_summary"]
                or current_art.source_id != snap["source_id"]
            ):
                article_modifications += 1

            # Check source provenance
            if current_art.source:
                if current_art.source.provenance not in ("independent", "official", "aggregated", "rss", "institutional", None):
                    provenance_corruptions += 1

        # 5. Check Duplicate ArticleAIOutput rows
        duplicate_outputs = 0
        all_output_article_ids = [out.article_id for out in db.query(ArticleAIOutput).all()]
        if len(all_output_article_ids) != len(set(all_output_article_ids)):
            from collections import Counter
            counts = Counter(all_output_article_ids)
            duplicate_outputs = sum(c - 1 for c in counts.values())

        report_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "batch_summary": {
                "claimed_count": batch_result["claimed_count"],
                "processed_success": batch_result["processed_success"],
                "relevant_count": batch_result["relevant_count"],
                "out_of_scope_count": batch_result["out_of_scope_count"],
                "failed_count": batch_result["failed_count"],
                "batch_duration_ms": batch_result["batch_duration_ms"],
            },
            "before_queue_status": before_status,
            "after_queue_status": after_status,
            "article_results": batch_result["article_results"],
            "verification": {
                "article_rows_modified": article_modifications,
                "provenance_corruptions": provenance_corruptions,
                "duplicate_ai_outputs": duplicate_outputs,
            },
        }

        os.makedirs("scratch", exist_ok=True)
        with open("scratch/controlled_test_results.json", "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

        print("\n" + "=" * 80)
        print("PER-ARTICLE RESULTS:")
        for res in batch_result["article_results"]:
            print(f"  ID {res['article_id']} | Source: {res['source'][:20]} | Claim: {res['claim_status']} | Ollama: {res['ollama_result']} | State: {res['final_queue_state']} | Time: {res['processing_time_ms']}ms")
            print(f"    Title: {res['title'][:70]}...")

        print("\n[VERIFICATION]")
        print(f"  Article Rows Modified: {article_modifications}")
        print(f"  Source/Provenance Corruptions: {provenance_corruptions}")
        print(f"  Duplicate ArticleAIOutput Rows: {duplicate_outputs}")
        print("=" * 80)

        return report_data

    finally:
        db.close()


if __name__ == "__main__":
    run_controlled_test()
