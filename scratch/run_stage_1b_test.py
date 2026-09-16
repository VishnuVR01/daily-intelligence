"""
Script to execute Stage 1B Controlled Prioritisation Test (Sprint 1 Stage 1B Part D).
Phase 1: Generates 20-article dry-run priority report.
Phase 2: Runs controlled processing batch on maximum 10 articles.
Phase 3: Performs verification audit of duplicates and provenance preservation.
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
from services.ai.priority import calculate_article_priority
from services.ai.worker import AIWorker


def run_stage_1b_controlled_test():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        print("=" * 90)
        print("STAGE 1B — INTELLIGENT PRIORITISATION & RETRY CONTROLLED TEST")
        print("=" * 90)

        # -------------------------------------------------------------------------
        # PHASE 1: 20-ARTICLE DRY-RUN PRIORITY REPORT
        # -------------------------------------------------------------------------
        print("\n[PHASE 1: 20-ARTICLE DRY-RUN PRIORITY REPORT]")
        unprocessed_sample = (
            db.query(Article)
            .filter(~Article.ai_outputs.any())
            .order_by(Article.collected_at.asc().nullslast(), Article.id.asc())
            .limit(20)
            .all()
        )

        dry_run_table = []
        for art in unprocessed_sample:
            p_info = calculate_article_priority(art, now=now)
            src_name = art.source.name if art.source else "Unknown Source"
            col_at = art.collected_at.isoformat() if art.collected_at else None

            dry_run_table.append({
                "article_id": art.id,
                "source": src_name,
                "title": art.title,
                "collected_at": col_at,
                "base_score": p_info["base_score"],
                "aging_bonus": p_info["aging_bonus"],
                "effective_score": p_info["effective_score"],
                "priority_tier": p_info["priority_tier"],
                "reasons": p_info["reasons"],
            })

        # Sort dry run table by effective_score DESC, collected_at ASC, article_id ASC
        dry_run_table.sort(key=lambda x: (-x["effective_score"], x["collected_at"] or "", x["article_id"]))

        print(f"{'ID':<6} | {'TIER':<11} | {'EFF_SCORE':<9} | {'BASE':<5} | {'AGING':<6} | {'SOURCE':<20} | {'TITLE':<30}")
        print("-" * 100)
        for row in dry_run_table:
            print(f"{row['article_id']:<6} | {row['priority_tier']:<11} | {row['effective_score']:<9.1f} | {row['base_score']:<5} | {row['aging_bonus']:<6.1f} | {row['source'][:20]:<20} | {row['title'][:30]}")

        # -------------------------------------------------------------------------
        # PHASE 2: CONTROLLED BATCH PROCESSING (MAXIMUM 10 ARTICLES)
        # -------------------------------------------------------------------------
        print("\n" + "=" * 90)
        print("[PHASE 2: CONTROLLED BATCH PROCESSING (MAXIMUM 10 ARTICLES)]")
        before_status = get_ai_queue_status(db)

        service = OllamaService()
        print(f"Ollama Service Health: {service.get_health_status()}")

        worker = AIWorker(ollama_service=service)
        batch_result = worker.run_batch(db=db, batch_size=10)

        after_status = get_ai_queue_status(db)

        print("\nPER-ARTICLE EXECUTED RESULTS (IN CLAIMED PRIORITY ORDER):")
        print(f"{'CLAIM ORDER':<12} | {'ID':<6} | {'TIER':<11} | {'SCORE':<6} | {'STATE':<24} | {'TIME':<8} | {'TITLE':<35}")
        print("-" * 110)
        for idx, res in enumerate(batch_result["article_results"], 1):
            print(f"{idx:<12} | {res['article_id']:<6} | {res['priority_tier']:<11} | {res['effective_score']:<6.1f} | {res['final_queue_state']:<24} | {res['processing_time_ms']}ms | {res['title'][:35]}")

        # -------------------------------------------------------------------------
        # PHASE 3: VERIFICATION AUDIT
        # -------------------------------------------------------------------------
        print("\n" + "=" * 90)
        print("[PHASE 3: VERIFICATION AUDIT]")

        # Duplicate check
        all_output_article_ids = [out.article_id for out in db.query(ArticleAIOutput).all()]
        duplicate_count = len(all_output_article_ids) - len(set(all_output_article_ids))

        # Provenance check
        provenance_corruptions = 0
        claimed_ids = [res["article_id"] for res in batch_result["article_results"]]
        for art_id in claimed_ids:
            art = db.query(Article).filter(Article.id == art_id).first()
            if art and art.source:
                if art.source.provenance not in ("independent", "official", "aggregated", "rss", "institutional", None):
                    provenance_corruptions += 1

        print(f"  Duplicate ArticleAIOutput Rows: {duplicate_count}")
        print(f"  Article Provenance Corruptions: {provenance_corruptions}")
        print(f"  AI Processing Coverage: {after_status['ai_processing_coverage_percent']}%")

        report_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dry_run_priority_table": dry_run_table,
            "before_queue_status": before_status,
            "after_queue_status": after_status,
            "executed_batch": batch_result,
            "verification": {
                "duplicate_ai_outputs": duplicate_count,
                "provenance_corruptions": provenance_corruptions,
            },
        }

        with open("scratch/stage_1b_test_results.json", "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

        print("\n" + "=" * 90)
        print("STAGE 1B CONTROLLED TEST COMPLETE! Results saved to scratch/stage_1b_test_results.json")
        print("=" * 90)

        return report_data

    finally:
        db.close()


if __name__ == "__main__":
    run_stage_1b_controlled_test()
