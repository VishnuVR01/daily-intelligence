"""
Unit and Integration Tests for Stage 1B Intelligent Prioritisation and Safe Retry Policy.
Validates priority scoring (P0-P3), aging starvation protection, FIFO tie-breaking,
retry cooldown, failure classification, and observability metrics.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Article, ArticleAIOutput, Source
from repositories.ai_outputs import claim_eligible_articles, save_ai_output
from repositories.ai_queue import get_ai_queue_status
from services.ai.ollama import OllamaAnalysisResult, ArticleAIAnalysis
from services.ai.priority import calculate_article_priority
from services.ai.worker import AIWorker, process_next_batch


@pytest.fixture
def high_trust_source(test_db_session):
    src = Source(
        name="Primary Central Bank Source",
        source_type="rss",
        source_family="central_bank",
        trust_tier="primary",
        category="Markets & Economy",
        active=True,
    )
    test_db_session.add(src)
    test_db_session.commit()
    test_db_session.refresh(src)
    return src


@pytest.fixture
def low_trust_source(test_db_session):
    src = Source(
        name="Routine Blog Source",
        source_type="rss",
        source_family="news",
        trust_tier="useful",
        category="World",
        active=True,
    )
    test_db_session.add(src)
    test_db_session.commit()
    test_db_session.refresh(src)
    return src


def test_critical_topic_outranks_routine(test_db_session, high_trust_source, low_trust_source):
    """1. Critical strategic topic article outranks a routine sports article."""
    now = datetime.now(timezone.utc)
    art_critical = Article(
        source_id=high_trust_source.id,
        title="Nvidia and TSMC announce new AI semiconductor breakthrough",
        canonical_url="https://example.com/critical-topic-1",
        collected_at=now,
    )
    art_routine = Article(
        source_id=low_trust_source.id,
        title="Local football match score and celebrity gossip news",
        canonical_url="https://example.com/routine-topic-1",
        collected_at=now - timedelta(minutes=5),  # Collected earlier but routine topic
    )
    test_db_session.add_all([art_critical, art_routine])
    test_db_session.commit()

    claimed = claim_eligible_articles(test_db_session, batch_size=1)
    assert len(claimed) == 1
    assert claimed[0].id == art_critical.id


def test_high_trust_signal_affects_priority(test_db_session, high_trust_source, low_trust_source):
    """2. High trust tier source signal increases priority score relative to low trust source."""
    now = datetime.now(timezone.utc)
    art_high = Article(
        source_id=high_trust_source.id,
        title="Quarterly Economic Outlook Report",
        canonical_url="https://example.com/trust-high-1",
        collected_at=now,
    )
    art_low = Article(
        source_id=low_trust_source.id,
        title="Quarterly Economic Outlook Report",
        canonical_url="https://example.com/trust-low-1",
        collected_at=now,
    )
    test_db_session.add_all([art_high, art_low])
    test_db_session.commit()

    p_high = calculate_article_priority(art_high, now=now)
    p_low = calculate_article_priority(art_low, now=now)

    assert p_high["base_score"] > p_low["base_score"]


def test_multiple_strategic_signals_combine_deterministically(test_db_session, high_trust_source):
    """3. Multiple strategic signals combine deterministically to achieve P0_CRITICAL tier."""
    now = datetime.now(timezone.utc)
    art = Article(
        source_id=high_trust_source.id,
        title="Federal Reserve and ECB discuss interest rate decisions amidst semiconductor supply chain shifts",
        canonical_url="https://example.com/multi-strat-1",
        collected_at=now,
    )
    test_db_session.add(art)
    test_db_session.commit()

    p_info = calculate_article_priority(art, now=now)
    assert p_info["priority_tier"] == "P0_CRITICAL"
    assert p_info["base_score"] >= 80


def test_low_priority_article_remains_eligible(test_db_session, low_trust_source):
    """4. Low priority article receives P3_LOW tier but remains eligible for queue processing."""
    now = datetime.now(timezone.utc)
    art_sports = Article(
        source_id=low_trust_source.id,
        title="Routine local sports match score update",
        canonical_url="https://example.com/sports-1",
        collected_at=now,
    )
    test_db_session.add(art_sports)
    test_db_session.commit()

    p_info = calculate_article_priority(art_sports, now=now)
    assert p_info["priority_tier"] == "P3_LOW"

    claimed = claim_eligible_articles(test_db_session, batch_size=1)
    assert len(claimed) == 1
    assert claimed[0].id == art_sports.id


def test_aging_prevents_starvation(test_db_session, low_trust_source, high_trust_source):
    """5. Aging starvation protection increases effective score for older articles over time."""
    now = datetime.now(timezone.utc)
    # Old low-priority article collected 20 hours ago
    art_old = Article(
        source_id=low_trust_source.id,
        title="Routine local event update",
        canonical_url="https://example.com/aging-old-1",
        collected_at=now - timedelta(hours=20),
    )
    # Brand new normal priority article collected just now
    art_new = Article(
        source_id=high_trust_source.id,
        title="Standard economic update",
        canonical_url="https://example.com/aging-new-1",
        collected_at=now,
    )
    test_db_session.add_all([art_old, art_new])
    test_db_session.commit()

    p_old = calculate_article_priority(art_old, now=now)
    assert p_old["aging_bonus"] == 40.0  # 20 hours * 2.0 = 40.0 pts bonus
    assert p_old["effective_score"] > p_old["base_score"]


def test_equal_scores_use_fifo(test_db_session, low_trust_source):
    """6. Articles with identical priority scores fallback to FIFO ordering (collected_at ASC, id ASC)."""
    now = datetime.now(timezone.utc)
    art_first = Article(source_id=low_trust_source.id, title="Identical Story Title", canonical_url="https://example.com/fifo-1", collected_at=now - timedelta(minutes=10))
    art_second = Article(source_id=low_trust_source.id, title="Identical Story Title", canonical_url="https://example.com/fifo-2", collected_at=now - timedelta(minutes=5))
    test_db_session.add_all([art_first, art_second])
    test_db_session.commit()

    claimed = claim_eligible_articles(test_db_session, batch_size=2)
    assert len(claimed) == 2
    assert claimed[0].id == art_first.id
    assert claimed[1].id == art_second.id


def test_priority_ordering_is_deterministic(test_db_session, high_trust_source, low_trust_source):
    """7. Queue claiming order is 100% deterministic across multiple queries."""
    now = datetime.now(timezone.utc)
    art_p0 = Article(source_id=high_trust_source.id, title="Federal Reserve interest rate AI chip crisis", canonical_url="https://example.com/det-p0", collected_at=now)
    art_p2 = Article(source_id=low_trust_source.id, title="General business news", canonical_url="https://example.com/det-p2", collected_at=now)
    test_db_session.add_all([art_p0, art_p2])
    test_db_session.commit()

    q1 = claim_eligible_articles(test_db_session, batch_size=2)
    # Reset processing records so articles become eligible again
    test_db_session.query(ArticleAIOutput).delete()
    test_db_session.commit()

    q2 = claim_eligible_articles(test_db_session, batch_size=2)

    assert [a.id for a in q1] == [a.id for a in q2]
    assert q1[0].id == art_p0.id


def test_timeout_becomes_retryable(test_db_session, low_trust_source):
    """8. Timeout status failure is retryable after cooldown."""
    now = datetime.now(timezone.utc)
    art = Article(source_id=low_trust_source.id, title="Test Timeout Article", canonical_url="https://example.com/timeout-1", collected_at=now)
    test_db_session.add(art)
    test_db_session.commit()

    out = ArticleAIOutput(
        article_id=art.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        status="timeout",
        error_message="Request timed out after 120s",
        processed_at=now - timedelta(seconds=600),  # 10m ago (> 5m cooldown)
    )
    test_db_session.add(out)
    test_db_session.commit()

    claimed = claim_eligible_articles(test_db_session, batch_size=1, cooldown_seconds=300)
    assert len(claimed) == 1
    assert claimed[0].id == art.id


def test_unavailable_becomes_retryable(test_db_session, low_trust_source):
    """9. Unavailable status failure is retryable after cooldown."""
    now = datetime.now(timezone.utc)
    art = Article(source_id=low_trust_source.id, title="Test Unavailable Article", canonical_url="https://example.com/unavail-1", collected_at=now)
    test_db_session.add(art)
    test_db_session.commit()

    out = ArticleAIOutput(
        article_id=art.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        status="unavailable",
        error_message="Ollama API unavailable",
        processed_at=now - timedelta(seconds=600),  # 10m ago (> 5m cooldown)
    )
    test_db_session.add(out)
    test_db_session.commit()

    claimed = claim_eligible_articles(test_db_session, batch_size=1, cooldown_seconds=300)
    assert len(claimed) == 1
    assert claimed[0].id == art.id


def test_retry_cooldown_respected(test_db_session, low_trust_source):
    """10. Failed articles inside active cooldown period are not claimed."""
    now = datetime.now(timezone.utc)
    art = Article(source_id=low_trust_source.id, title="Test Cooldown Article", canonical_url="https://example.com/cooldown-1", collected_at=now)
    test_db_session.add(art)
    test_db_session.commit()

    out = ArticleAIOutput(
        article_id=art.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        status="failed",
        error_message="HTTP 500",
        processed_at=now - timedelta(seconds=60),  # 1m ago (< 5m cooldown)
    )
    test_db_session.add(out)
    test_db_session.commit()

    claimed = claim_eligible_articles(test_db_session, batch_size=1, cooldown_seconds=300)
    assert len(claimed) == 0


def test_invalid_json_does_not_rapid_loop(test_db_session, low_trust_source):
    """11. Non-retryable invalid_json output is excluded from auto-retry claiming."""
    now = datetime.now(timezone.utc)
    art = Article(source_id=low_trust_source.id, title="Test Invalid JSON Article", canonical_url="https://example.com/invalid-json-1", collected_at=now)
    test_db_session.add(art)
    test_db_session.commit()

    out = ArticleAIOutput(
        article_id=art.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        status="invalid_json",
        error_message="Schema validation error",
        processed_at=now - timedelta(seconds=1000),  # Old timestamp
    )
    test_db_session.add(out)
    test_db_session.commit()

    claimed = claim_eligible_articles(test_db_session, batch_size=1, cooldown_seconds=300)
    assert len(claimed) == 0  # invalid_json does not rapid-loop!


def test_fresh_processing_cannot_be_reclaimed(test_db_session, low_trust_source):
    """12. Active PROCESSING lock under 15 minutes old cannot be claimed."""
    now = datetime.now(timezone.utc)
    art = Article(source_id=low_trust_source.id, title="Test Active Processing", canonical_url="https://example.com/fresh-proc-1", collected_at=now)
    test_db_session.add(art)
    test_db_session.commit()

    out = ArticleAIOutput(
        article_id=art.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        status="processing",
        processed_at=now - timedelta(minutes=5),  # 5m ago (< 15m stale threshold)
    )
    test_db_session.add(out)
    test_db_session.commit()

    claimed = claim_eligible_articles(test_db_session, batch_size=1, stale_processing_seconds=900)
    assert len(claimed) == 0


def test_stale_processing_can_be_recovered(test_db_session, low_trust_source):
    """13. Stale PROCESSING lock older than 15 minutes is safely recovered."""
    now = datetime.now(timezone.utc)
    art = Article(source_id=low_trust_source.id, title="Test Stale Processing", canonical_url="https://example.com/stale-proc-1", collected_at=now)
    test_db_session.add(art)
    test_db_session.commit()

    out = ArticleAIOutput(
        article_id=art.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        status="processing",
        processed_at=now - timedelta(minutes=20),  # 20m ago (> 15m stale threshold)
    )
    test_db_session.add(out)
    test_db_session.commit()

    claimed = claim_eligible_articles(test_db_session, batch_size=1, stale_processing_seconds=900)
    assert len(claimed) == 1
    assert claimed[0].id == art.id


def test_pending_vs_failed_observability(test_db_session, low_trust_source):
    """14. Observability correctly distinguishes pending, retryable, and non-retryable failed states."""
    now = datetime.now(timezone.utc)
    art_unprocessed = Article(source_id=low_trust_source.id, title="Unprocessed Art", canonical_url="https://example.com/unproc-obs-1", collected_at=now)
    art_invalid = Article(source_id=low_trust_source.id, title="Invalid JSON Art", canonical_url="https://example.com/invalid-obs-1", collected_at=now)
    test_db_session.add_all([art_unprocessed, art_invalid])
    test_db_session.commit()

    save_ai_output(
        db=test_db_session,
        article_id=art_invalid.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        result=OllamaAnalysisResult(status="invalid_json", error_message="Malformed output"),
    )

    status_metrics = get_ai_queue_status(test_db_session)
    assert status_metrics["unprocessed"] == 1
    assert status_metrics["non_retryable"] == 1
    assert status_metrics["failed"] == 1


def test_prioritisation_never_modifies_article_provenance(test_db_session, high_trust_source):
    """15. Priority scoring calculation and queue claiming never modify raw Article or Source rows."""
    now = datetime.now(timezone.utc)
    art = Article(
        source_id=high_trust_source.id,
        title="Federal Reserve policy meeting and interest rates",
        canonical_url="https://example.com/prov-test",
        collected_at=now,
        raw_summary="Raw summary text",
    )
    test_db_session.add(art)
    test_db_session.commit()

    # Run priority calculation & claiming
    p_info = calculate_article_priority(art, now=now)
    claimed = claim_eligible_articles(test_db_session, batch_size=1)

    art_check = test_db_session.query(Article).filter(Article.id == art.id).first()
    assert art_check.title == "Federal Reserve policy meeting and interest rates"
    assert art_check.canonical_url == "https://example.com/prov-test"
    assert art_check.source.provenance == "institutional" or art_check.source.trust_tier == "primary"


def test_repeated_execution_remains_idempotent(test_db_session, high_trust_source):
    """16. Repeated worker batch execution remains idempotent (0 duplicate outputs created)."""
    now = datetime.now(timezone.utc)
    art = Article(source_id=high_trust_source.id, title="Idempotency Test Article", canonical_url="https://example.com/idemp-1", collected_at=now)
    test_db_session.add(art)
    test_db_session.commit()

    mock_service = MagicMock()
    analysis = ArticleAIAnalysis(
        is_relevant=True,
        primary_category="Markets & Economy",
        summary="Test summary",
        importance_score=85,
        relevance_score=90,
    )
    mock_service.analyze_article.return_value = OllamaAnalysisResult(analysis=analysis, status="success")

    # Run batch 1
    res1 = process_next_batch(test_db_session, batch_size=1, ollama_service=mock_service)
    assert res1["claimed_count"] == 1

    # Run batch 2
    res2 = process_next_batch(test_db_session, batch_size=1, ollama_service=mock_service)
    assert res2["claimed_count"] == 0

    total_outputs = test_db_session.query(ArticleAIOutput).filter(ArticleAIOutput.article_id == art.id).count()
    assert total_outputs == 1


def test_unique_constraint_race_protection_remains_working(test_db_session, low_trust_source):
    """17. Unique constraint race protection operates reliably during claim collision."""
    now = datetime.now(timezone.utc)
    art = Article(source_id=low_trust_source.id, title="Race Condition Article", canonical_url="https://example.com/race-1", collected_at=now)
    test_db_session.add(art)
    test_db_session.commit()

    # Pre-insert output record
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

    # Attempt duplicate insert
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
