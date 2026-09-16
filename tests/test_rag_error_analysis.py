"""
Unit Tests for RAG Error Analysis Diagnostic Script
Verifies classification logic, candidate tracing, and RAG-001 / Article 3797 discrepancy diagnostic utilities.
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from app.models import Article, ArticleAIOutput, Source
from scripts.analyze_rag_failures import analyze_question_failure, investigate_rag_001_discrepancy


def test_investigate_rag_001_discrepancy(test_db_session: Session):
    """Verify Article 3797 diagnostic investigation executes cleanly and returns structured findings."""
    source = Source(name="Yle News", category="World")
    test_db_session.add(source)
    test_db_session.flush()

    art_3797 = Article(
        id=3797,
        source_id=source.id,
        title="Miksi Kreml edes vaivautuu järjestämään Venäjällä vaalit",
        canonical_url="https://example.com/yle-3797",
        published_at=datetime(2026, 9, 13, 10, 0, 0, tzinfo=timezone.utc),
        collected_at=datetime(2026, 9, 13, 21, 14, 47, tzinfo=timezone.utc),
        language="fi",
    )
    test_db_session.add(art_3797)
    test_db_session.commit()

    res = investigate_rag_001_discrepancy(test_db_session)
    assert isinstance(res, dict)
    assert res["article_id"] == 3797
    assert "discrepancy_explanation" in res
    assert len(res["exclusion_reasons"]) > 0


def test_analyze_question_failure_classification(test_db_session: Session):
    """Verify analyze_question_failure traces candidate pool and returns failure classifications."""
    source = Source(name="World Grain", category="Industry")
    test_db_session.add(source)
    test_db_session.flush()

    art = Article(
        id=9901,
        source_id=source.id,
        title="Grain Transportation Logistics Record",
        canonical_url="https://example.com/grain-9901",
        collected_at=datetime.now(timezone.utc),
    )
    test_db_session.add(art)
    test_db_session.flush()

    ai_out = ArticleAIOutput(
        article_id=art.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        is_relevant=True,
        summary="Grain transport record set.",
        status="success",
        importance_score=85,
        relevance_score=90,
    )
    test_db_session.add(ai_out)
    test_db_session.commit()

    benchmark_item = {
        "id": "RAG-TEST-ERR",
        "category": "historical_synthesis",
        "question": "What trends exist in grain transport?",
        "expected_date_scope": "all",
        "expected_topics": ["Supply Chain"],
        "expected_entities": ["CN"],
        "expected_min_evidence": 1,
        "expected_article_ids": [9901, 9999],  # 9999 is non-existent to test GOLD_LABEL_ISSUE
    }

    res = analyze_question_failure(test_db_session, benchmark_item)
    assert res["benchmark_id"] == "RAG-TEST-ERR"
    assert "gold_analysis" in res

    gold_9999 = next(g for g in res["gold_analysis"] if g["gold_id"] == 9999)
    assert gold_9999["classification"] == "GOLD_LABEL_ISSUE"
