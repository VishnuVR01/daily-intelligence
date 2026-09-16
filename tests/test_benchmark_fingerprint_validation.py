"""
Unit tests for pre-scoring gold article fingerprint validation.
"""

import json
import pytest
from app.models import Article, ArticleAIOutput
from scripts.validate_gold_fingerprints import validate_gold_fingerprints


def test_validate_gold_fingerprints_on_current_db(test_db_session):
    """Verify pre-scoring fingerprint validation runs against benchmarks/rag_v1_validated.json."""
    with open("benchmarks/rag_v1_validated.json", "r", encoding="utf-8") as f:
        bench_data = json.load(f)
    questions = bench_data["questions"] if isinstance(bench_data, dict) and "questions" in bench_data else bench_data

    gold_ids = set()
    for q in questions:
        for aid in q.get("gold_core_article_ids", []):
            gold_ids.add(aid)
        for aid in q.get("gold_optional_article_ids", []):
            gold_ids.add(aid)

    for aid in gold_ids:
        test_db_session.add(Article(id=aid, title=f"Gold Article {aid}", canonical_url=f"https://example.com/gold_{aid}"))
    test_db_session.commit()

    validated_questions, drift_report = validate_gold_fingerprints("benchmarks/rag_v1_validated.json", db=test_db_session)

    assert drift_report["status"] == "DRIFT_CHECK_COMPLETE"
    assert drift_report["total_gold_inspections"] > 0
    assert drift_report["drift_detected_count"] == 0
    assert len(drift_report["drift_records"]) == 0
    assert len(validated_questions) == len(questions)


def test_fingerprint_validation_excludes_drifted_id_without_modifying_file(tmp_path, test_db_session):
    """Verify that if a bogus article ID is introduced, it is marked BENCHMARK_DATA_DRIFT and excluded from scoring."""
    mock_benchmark = [
        {
            "id": "RAG-TEST-DRIFT",
            "question": "Test question with bogus ID",
            "gold_core_article_ids": [99999999],  # Non-existent ID
            "gold_optional_article_ids": [],
            "expected_article_ids": [99999999],
            "should_be_answerable": True
        }
    ]

    bench_file = tmp_path / "mock_rag.json"
    bench_file.write_text(json.dumps(mock_benchmark), encoding="utf-8")

    # Run validation
    validated_qs, drift_report = validate_gold_fingerprints(str(bench_file), db=test_db_session)

    assert drift_report["drift_detected_count"] == 1
    assert len(drift_report["drift_records"]) == 1
    record = drift_report["drift_records"][0]

    assert record["status"] == "BENCHMARK_DATA_DRIFT"
    assert record["article_id"] == 99999999
    assert record["excluded_from_scoring"] is True

    # Verify validated questions set excluded the drifted ID
    assert validated_qs[0]["gold_core_article_ids"] == []

    # Verify original file was NOT modified
    unmodified_content = json.loads(bench_file.read_text(encoding="utf-8"))
    assert unmodified_content[0]["gold_core_article_ids"] == [99999999]
