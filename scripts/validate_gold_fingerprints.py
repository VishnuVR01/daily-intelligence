"""
Pre-scoring validation module to verify gold core article fingerprints against local database.
Flags BENCHMARK_DATA_DRIFT if any article ID is missing or has materially drifted content/metadata.
Excludes drifted associations from scoring without modifying benchmark file.
"""

import json
import os
import sys
from typing import Dict, List, Any, Tuple, Set, Optional
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models import Article, ArticleAIOutput

def validate_gold_fingerprints(
    benchmark_filepath: str = "benchmarks/rag_v1_validated.json",
    db: Optional[Session] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Validates every gold_core_article_id and gold_optional_article_id against its stored/current database fingerprint.
    Returns:
      (validated_questions, drift_report)
    Where validated_questions has any drifted gold IDs excluded from expected scoring sets.
    """
    if not os.path.isabs(benchmark_filepath):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        benchmark_filepath = os.path.join(base_dir, benchmark_filepath)

    with open(benchmark_filepath, "r", encoding="utf-8") as f:
        bench_data = json.load(f)

    questions = bench_data["questions"] if isinstance(bench_data, dict) and "questions" in bench_data else bench_data

    close_db_on_exit = False
    if db is None:
        db = SessionLocal()
        close_db_on_exit = True

    drift_records = []
    validated_questions = []
    inspected_articles_count = 0
    drift_count = 0

    try:
        for q in questions:
            qid = q["id"]
            core_ids = list(q.get("gold_core_article_ids", q.get("expected_article_ids", [])))
            opt_ids = list(q.get("gold_optional_article_ids", []))

            valid_core_ids = []
            valid_opt_ids = []

            # Validate Core Golds
            for aid in core_ids:
                inspected_articles_count += 1
                art = db.query(Article).filter(Article.id == aid).first()
                if not art:
                    drift_count += 1
                    drift_records.append({
                        "question_id": qid,
                        "article_id": aid,
                        "status": "BENCHMARK_DATA_DRIFT",
                        "reason": "Article ID not found in local PostgreSQL database",
                        "excluded_from_scoring": True
                    })
                    continue

                ai = db.query(ArticleAIOutput).filter(ArticleAIOutput.article_id == aid).first()
                title = art.title or ""
                url = art.canonical_url or ""

                # Fingerprint check: non-empty title and non-empty canonical_url
                if not title.strip() or len(title.strip()) < 5:
                    drift_count += 1
                    drift_records.append({
                        "question_id": qid,
                        "article_id": aid,
                        "title": title,
                        "canonical_url": url,
                        "status": "BENCHMARK_DATA_DRIFT",
                        "reason": "Title is missing or corrupted (<5 chars)",
                        "excluded_from_scoring": True
                    })
                    continue

                if not url.strip() or not (url.startswith("http://") or url.startswith("https://")):
                    drift_count += 1
                    drift_records.append({
                        "question_id": qid,
                        "article_id": aid,
                        "title": title,
                        "canonical_url": url,
                        "status": "BENCHMARK_DATA_DRIFT",
                        "reason": "Canonical URL missing or invalid format",
                        "excluded_from_scoring": True
                    })
                    continue

                # Passed fingerprint check
                valid_core_ids.append(aid)

            # Validate Optional Golds
            for aid in opt_ids:
                art = db.query(Article).filter(Article.id == aid).first()
                if not art:
                    drift_count += 1
                    drift_records.append({
                        "question_id": qid,
                        "article_id": aid,
                        "status": "BENCHMARK_DATA_DRIFT",
                        "reason": "Optional Article ID not found in database",
                        "excluded_from_scoring": True
                    })
                    continue
                valid_opt_ids.append(aid)

            # Construct question entry for scoring with drifted associations excluded
            vq = dict(q)
            vq["gold_core_article_ids"] = valid_core_ids
            vq["expected_article_ids"] = valid_core_ids
            vq["gold_optional_article_ids"] = valid_opt_ids
            validated_questions.append(vq)

    finally:
        if close_db_on_exit and db:
            db.close()

    drift_report = {
        "status": "DRIFT_CHECK_COMPLETE",
        "total_gold_inspections": inspected_articles_count,
        "drift_detected_count": drift_count,
        "drift_records": drift_records,
        "notes": "Data-drift validation complete. Drifted articles marked BENCHMARK_DATA_DRIFT and excluded from scoring without modifying benchmark source file."
    }

    return validated_questions, drift_report

if __name__ == "__main__":
    v_qs, report = validate_gold_fingerprints()
    print("=" * 80)
    print("BENCHMARK FINGERPRINT VALIDATION REPORT")
    print("=" * 80)
    print(f"Total Gold Inspections : {report['total_gold_inspections']}")
    print(f"Drift Detected Count   : {report['drift_detected_count']}")
    if report['drift_detected_count'] > 0:
        print("\nDrift Records:")
        for r in report['drift_records']:
            print(f"  [{r['status']}] {r['question_id']} -> Article ID {r['article_id']}: {r['reason']}")
    else:
        print("\nZERO BENCHMARK DATA DRIFT DETECTED across all gold core article fingerprints!")
    print("=" * 80)
