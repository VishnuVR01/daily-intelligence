"""
Unit and Integration Tests for Safe AI Processing Queue (Sprint 1 Stage 1A).
Tests eligibility, claiming, FIFO ordering, failure isolation, idempotency, race condition handling, and observability metrics.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Article, ArticleAIOutput, Source
from repositories.ai_outputs import claim_eligible_articles, save_ai_output
from repositories.ai_queue import get_ai_queue_status
from services.ai.ollama import OllamaAnalysisResult, ArticleAIAnalysis
from services.ai.worker import AIWorker, process_next_batch


@pytest.fixture
def sample_source(test_db_session):
    src = Source(
        name="Queue Test News",
        source_type="rss",
        source_family="news",
        active=True,
    )
    test_db_session.add(src)
    test_db_session.commit()
    test_db_session.refresh(src)
    return src


@pytest.fixture
def sample_articles(test_db_session, sample_source):
    now = datetime.now(timezone.utc)
    articles = []
    for i in range(1, 6):
        art = Article(
            source_id=sample_source.id,
            title=f"Test Article {i}",
            canonical_url=f"https://example.com/queue-test-{i}",
            collected_at=now - timedelta(minutes=10 - i),  # Art 1 is oldest (10 mins ago), Art 5 newest
            published_at=now - timedelta(minutes=10 - i),
            raw_summary=f"Summary for test article {i}",
        )
        test_db_session.add(art)
        articles.append(art)
    test_db_session.commit()
    for art in articles:
        test_db_session.refresh(art)
    return articles


def test_unprocessed_article_is_eligible(test_db_session, sample_articles):
    """1. Unprocessed article with no output record is eligible for claiming."""
    claimed = claim_eligible_articles(test_db_session, batch_size=5)
    assert len(claimed) == 5
    assert claimed[0].id == sample_articles[0].id


def test_completed_relevant_is_not_eligible(test_db_session, sample_articles):
    """2. Completed relevant article is not eligible for claiming."""
    art = sample_articles[0]
    out = ArticleAIOutput(
        article_id=art.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        status="success",
        is_relevant=True,
        summary="Test summary",
    )
    test_db_session.add(out)
    test_db_session.commit()

    claimed = claim_eligible_articles(test_db_session, batch_size=5)
    claimed_ids = [a.id for a in claimed]
    assert art.id not in claimed_ids
    assert len(claimed) == 4


def test_completed_out_of_scope_is_not_eligible(test_db_session, sample_articles):
    """3. Completed out-of-scope article is not eligible for claiming."""
    art = sample_articles[0]
    out = ArticleAIOutput(
        article_id=art.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        status="out_of_scope",
        is_relevant=False,
        rejection_reason="Routine sports news",
    )
    test_db_session.add(out)
    test_db_session.commit()

    claimed = claim_eligible_articles(test_db_session, batch_size=5)
    claimed_ids = [a.id for a in claimed]
    assert art.id not in claimed_ids
    assert len(claimed) == 4


def test_processing_article_cannot_be_claimed_twice(test_db_session, sample_articles):
    """4. Actively processing article cannot be claimed twice."""
    claimed_first = claim_eligible_articles(test_db_session, batch_size=2)
    assert len(claimed_first) == 2

    # Second claim attempt should skip the 2 active processing articles
    claimed_second = claim_eligible_articles(test_db_session, batch_size=2)
    assert len(claimed_second) == 2

    first_ids = {a.id for a in claimed_first}
    second_ids = {a.id for a in claimed_second}
    assert first_ids.isdisjoint(second_ids)


def test_failed_article_obeys_retry_rules(test_db_session, sample_articles):
    """5. Failed article is blocked during cooldown, eligible after cooldown."""
    art = sample_articles[0]
    now = datetime.now(timezone.utc)
    out = ArticleAIOutput(
        article_id=art.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        status="failed",
        error_message="HTTP 500 error",
        processed_at=now - timedelta(seconds=60),  # 60s ago (< 300s cooldown)
    )
    test_db_session.add(out)
    test_db_session.commit()

    # Attempt claim with 300s cooldown -> art should NOT be claimed
    claimed_1 = claim_eligible_articles(test_db_session, batch_size=5, cooldown_seconds=300)
    assert art.id not in [a.id for a in claimed_1]

    # Set processed_at to 600s ago (> 300s cooldown)
    out.processed_at = now - timedelta(seconds=600)
    test_db_session.commit()

    # Attempt claim -> art SHOULD now be claimed for retry
    claimed_2 = claim_eligible_articles(test_db_session, batch_size=5, cooldown_seconds=300)
    assert art.id in [a.id for a in claimed_2]


def test_one_failure_does_not_stop_batch(test_db_session, sample_articles):
    """6. Batch processing continues even if one article fails in Ollama."""
    mock_service = MagicMock()
    
    # Article 1 succeeds, Article 2 fails with timeout, Article 3 succeeds
    def mock_analyze(art_data):
        art_id = art_data["id"]
        if art_id == sample_articles[1].id:
            return OllamaAnalysisResult(status="timeout", error_message="Request timed out")
        analysis = ArticleAIAnalysis(
            is_relevant=True,
            primary_category="World",
            summary=f"Summary for {art_id}",
            importance_score=80,
            relevance_score=85,
        )
        return OllamaAnalysisResult(analysis=analysis, status="success")

    mock_service.analyze_article.side_effect = mock_analyze

    res = process_next_batch(test_db_session, batch_size=3, ollama_service=mock_service)
    assert res["claimed_count"] == 3
    assert res["processed_success"] == 2
    assert res["failed_count"] == 1

    # Verify Article 2 has status="timeout" stored in DB
    out_2 = test_db_session.query(ArticleAIOutput).filter(ArticleAIOutput.article_id == sample_articles[1].id).first()
    assert out_2 is not None
    assert out_2.status == "timeout"


def test_successful_output_persists(test_db_session, sample_articles):
    """7. Successful AI analysis output persists completely."""
    art = sample_articles[0]
    analysis = ArticleAIAnalysis(
        is_relevant=True,
        primary_category="AI & Technology",
        summary="AI breakthrough announced",
        importance_score=90,
        relevance_score=95,
        topics=["AI", "Tech"],
        countries=["United States"],
    )
    res = OllamaAnalysisResult(analysis=analysis, raw_output={"summary": "AI breakthrough"}, status="success")
    
    out = save_ai_output(
        db=test_db_session,
        article_id=art.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        result=res,
    )

    assert out.id is not None
    assert out.status == "success"
    assert out.summary == "AI breakthrough announced"
    assert out.primary_category == "AI & Technology"
    assert out.importance_score == 90
    assert out.is_relevant is True


def test_malformed_ollama_output_is_isolated(test_db_session, sample_articles):
    """8. Malformed Ollama JSON output is isolated with invalid_json status."""
    art = sample_articles[0]
    res = OllamaAnalysisResult(
        status="invalid_json",
        error_message="Schema validation error: missing fields",
        raw_output={"invalid": "payload"},
    )
    out = save_ai_output(
        db=test_db_session,
        article_id=art.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        result=res,
    )
    assert out.status == "invalid_json"
    assert "Schema validation error" in out.error_message


def test_ollama_unavailable_does_not_corrupt_article(test_db_session, sample_articles):
    """9. Ollama service unavailable records unavailable status without touching article."""
    art = sample_articles[0]
    res = OllamaAnalysisResult(
        status="unavailable",
        error_message="Ollama API unavailable: Connection refused",
    )
    out = save_ai_output(
        db=test_db_session,
        article_id=art.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        result=res,
    )
    assert out.status == "unavailable"

    # Verify Article table row is completely unchanged
    art_db = test_db_session.query(Article).filter(Article.id == art.id).first()
    assert art_db.title == "Test Article 1"
    assert art_db.canonical_url == "https://example.com/queue-test-1"


def test_repeated_worker_execution_is_idempotent(test_db_session, sample_articles):
    """10. Repeated worker runs do not create duplicate ArticleAIOutput rows."""
    mock_service = MagicMock()
    analysis = ArticleAIAnalysis(
        is_relevant=True,
        primary_category="World",
        summary="Test summary",
        importance_score=75,
        relevance_score=80,
    )
    mock_service.analyze_article.return_value = OllamaAnalysisResult(analysis=analysis, status="success")

    # Run batch 1
    res1 = process_next_batch(test_db_session, batch_size=5, ollama_service=mock_service)
    assert res1["claimed_count"] == 5

    total_outputs_1 = test_db_session.query(ArticleAIOutput).count()
    assert total_outputs_1 == 5

    # Run batch 2 (all articles already completed)
    res2 = process_next_batch(test_db_session, batch_size=5, ollama_service=mock_service)
    assert res2["claimed_count"] == 0

    total_outputs_2 = test_db_session.query(ArticleAIOutput).count()
    assert total_outputs_2 == 5  # Zero duplicates created!


def test_batch_size_is_respected(test_db_session, sample_articles):
    """11. Batch size constraint is strictly respected."""
    claimed = claim_eligible_articles(test_db_session, batch_size=2)
    assert len(claimed) == 2


def test_fifo_ordering(test_db_session, sample_articles):
    """12. FIFO ordering strictly prioritizes oldest collected_at ASC, id ASC."""
    claimed = claim_eligible_articles(test_db_session, batch_size=3)
    assert claimed[0].id == sample_articles[0].id
    assert claimed[1].id == sample_articles[1].id
    assert claimed[2].id == sample_articles[2].id


def test_pending_vs_failed_semantics(test_db_session, sample_articles):
    """13. Distinguishes never-processed (no output) from failed (status='failed')."""
    art_unprocessed = sample_articles[0]
    art_failed = sample_articles[1]

    save_ai_output(
        db=test_db_session,
        article_id=art_failed.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        result=OllamaAnalysisResult(status="failed", error_message="Connection lost"),
    )

    status_metrics = get_ai_queue_status(test_db_session)
    assert status_metrics["unprocessed"] == 4  # 4 articles never processed
    assert status_metrics["failed"] == 1       # 1 article explicitly failed


def test_stale_processing_recovery(test_db_session, sample_articles):
    """14. Stale processing locks (> 15 mins) are recovered and reclaimed."""
    art = sample_articles[0]
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=1000)
    out = ArticleAIOutput(
        article_id=art.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        status="processing",
        processed_at=stale_time,
    )
    test_db_session.add(out)
    test_db_session.commit()

    # Claim should recover the stale processing article
    claimed = claim_eligible_articles(test_db_session, batch_size=5, stale_processing_seconds=900)
    assert art.id in [a.id for a in claimed]


def test_unique_constraint_race_handling(test_db_session, sample_articles):
    """15. IntegrityError during concurrent claim insertion is caught cleanly."""
    art = sample_articles[0]
    # Manually insert output tuple
    out = ArticleAIOutput(
        article_id=art.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        status="processing",
    )
    test_db_session.add(out)
    test_db_session.commit()

    # Try inserting duplicate output to simulate race condition
    dup = ArticleAIOutput(
        article_id=art.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        status="processing",
    )
    test_db_session.add(dup)
    with pytest.raises(IntegrityError):
        test_db_session.commit()
    test_db_session.rollback()
