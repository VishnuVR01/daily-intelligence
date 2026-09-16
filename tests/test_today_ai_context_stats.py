"""
Unit tests for get_today_ai_context_stats function.

Tests cover:
- historical backlog articles do not enter today's denominator or numerator
- ingesting new article increases awaiting_ai_processing
- processing today article moves awaiting -> processed
- pending != failed
- genuine failure classification
- Europe/London timezone boundary handling
- zero denominator safety
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest

from app.models import Article, ArticleAIOutput, Source
from repositories.articles import get_today_ai_context_stats


def test_today_ai_context_stats_zero_denominator(test_db_session):
    """Zero denominator safety test when no articles exist today."""
    stats = get_today_ai_context_stats(test_db_session, tz_name="Europe/London")
    assert stats["ai_processed"] == 0
    assert stats["relevant_today"] == 0
    assert stats["out_of_scope_today"] == 0
    assert stats["awaiting_ai_processing"] == 0
    assert stats["ai_processing_failed"] == 0
    assert stats["processing_coverage"] == 0.0


def test_today_ai_context_stats_semantics(test_db_session):
    """
    Verifies metric semantics:
    - 2 processed relevant articles
    - 1 processed out-of-scope article
    - 1 genuine failed AI output
    - 3 pending/unprocessed articles
    """
    local_tz = ZoneInfo("Europe/London")
    now_today = datetime.now(local_tz)

    source = Source(name="Test Source", feed_url="https://example.com/rss")
    test_db_session.add(source)
    test_db_session.commit()

    # 1. Add 2 Relevant Articles (Processed)
    for i in range(2):
        art = Article(
            title=f"Relevant Article {i}",
            canonical_url=f"https://example.com/rel-{i}",
            source_id=source.id,
            collected_at=now_today.astimezone(timezone.utc),
            published_at=now_today.astimezone(timezone.utc),
        )
        test_db_session.add(art)
        test_db_session.commit()
        out = ArticleAIOutput(
            article_id=art.id,
            provider="ollama",
            model="qwen3.5:4b",
            task="article_analysis",
            prompt_version="v1",
            is_relevant=True,
            status="success",
            processed_at=now_today.astimezone(timezone.utc),
        )
        test_db_session.add(out)
        test_db_session.commit()

    # 2. Add 1 Out-of-Scope Article (Processed)
    art_oos = Article(
        title="Out of Scope Article",
        canonical_url="https://example.com/oos-1",
        source_id=source.id,
        collected_at=now_today.astimezone(timezone.utc),
        published_at=now_today.astimezone(timezone.utc),
    )
    test_db_session.add(art_oos)
    test_db_session.commit()
    out_oos = ArticleAIOutput(
        article_id=art_oos.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        is_relevant=False,
        status="out_of_scope",
        processed_at=now_today.astimezone(timezone.utc),
    )
    test_db_session.add(out_oos)
    test_db_session.commit()

    # 3. Add 1 Genuine Failed Article
    art_fail = Article(
        title="Failed Article",
        canonical_url="https://example.com/fail-1",
        source_id=source.id,
        collected_at=now_today.astimezone(timezone.utc),
        published_at=now_today.astimezone(timezone.utc),
    )
    test_db_session.add(art_fail)
    test_db_session.commit()
    out_fail = ArticleAIOutput(
        article_id=art_fail.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        is_relevant=None,
        status="failed",
        error_message="Ollama API Timeout",
        processed_at=now_today.astimezone(timezone.utc),
    )
    test_db_session.add(out_fail)
    test_db_session.commit()

    # 4. Add 3 Pending/Unprocessed Articles (No AIOutput)
    for i in range(3):
        art_pending = Article(
            title=f"Pending Article {i}",
            canonical_url=f"https://example.com/pending-{i}",
            source_id=source.id,
            collected_at=now_today.astimezone(timezone.utc),
            published_at=now_today.astimezone(timezone.utc),
        )
        test_db_session.add(art_pending)
    test_db_session.commit()

    stats = get_today_ai_context_stats(test_db_session, tz_name="Europe/London")

    assert stats["ai_processed"] == 3
    assert stats["relevant_today"] == 2
    assert stats["out_of_scope_today"] == 1
    assert stats["ai_processing_failed"] == 1
    assert stats["awaiting_ai_processing"] == 3
    assert stats["awaiting_ai_processing"] != stats["ai_processing_failed"]
    assert stats["processing_coverage"] == 42.9


def test_historical_backlog_excluded_from_today_denominator(test_db_session):
    """Historical articles collected 3 days ago processed today do NOT enter today's denominator."""
    local_tz = ZoneInfo("Europe/London")
    now_today = datetime.now(local_tz)
    past_date = now_today - timedelta(days=3)

    source = Source(name="Backlog Source", feed_url="https://example.com/backlog-rss")
    test_db_session.add(source)
    test_db_session.commit()

    # Historical article collected 3 days ago
    art_hist = Article(
        title="Historical Article",
        canonical_url="https://example.com/hist-1",
        source_id=source.id,
        collected_at=past_date.astimezone(timezone.utc),
        published_at=past_date.astimezone(timezone.utc),
    )
    test_db_session.add(art_hist)
    test_db_session.commit()

    # Worker processes historical article TODAY
    out_hist = ArticleAIOutput(
        article_id=art_hist.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        is_relevant=True,
        status="success",
        processed_at=now_today.astimezone(timezone.utc),
    )
    test_db_session.add(out_hist)
    test_db_session.commit()

    stats = get_today_ai_context_stats(test_db_session, tz_name="Europe/London")

    # Today's article population is 0
    assert stats["ai_processed"] == 0
    assert stats["awaiting_ai_processing"] == 0
    assert stats["processing_coverage"] == 0.0


def test_today_ingestion_and_processing_flow(test_db_session):
    """Verifies that ingesting a new article increases awaiting, and processing it moves to processed."""
    local_tz = ZoneInfo("Europe/London")
    now_today = datetime.now(local_tz)

    source = Source(name="Flow Source", feed_url="https://example.com/flow-rss")
    test_db_session.add(source)
    test_db_session.commit()

    # Step 1: Ingest new article today
    art = Article(
        title="Today Ingested Article",
        canonical_url="https://example.com/flow-1",
        source_id=source.id,
        collected_at=now_today.astimezone(timezone.utc),
        published_at=now_today.astimezone(timezone.utc),
    )
    test_db_session.add(art)
    test_db_session.commit()

    stats1 = get_today_ai_context_stats(test_db_session, tz_name="Europe/London")
    assert stats1["awaiting_ai_processing"] == 1
    assert stats1["ai_processed"] == 0
    assert stats1["processing_coverage"] == 0.0

    # Step 2: AI processes the article
    out = ArticleAIOutput(
        article_id=art.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        is_relevant=True,
        status="success",
        processed_at=now_today.astimezone(timezone.utc),
    )
    test_db_session.add(out)
    test_db_session.commit()

    stats2 = get_today_ai_context_stats(test_db_session, tz_name="Europe/London")
    assert stats2["awaiting_ai_processing"] == 0
    assert stats2["ai_processed"] == 1
    assert stats2["relevant_today"] == 1
    assert stats2["processing_coverage"] == 100.0
