"""
Unit Tests for Today in Context Statistics and RAG Date Semantics
Verifies temporal scoping, Europe/London UTC conversions, and RAG retrieval semantics.
"""

from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session

from app.models import Article, ArticleAIOutput, Source
from repositories.articles import get_today_ai_context_stats, search_articles_v1
from services.rag import parse_date_semantics, ask_archive


def test_today_in_context_excludes_historical_outputs(test_db_session: Session):
    """Requirement 1: Today in Context excludes historical AI outputs from previous days."""
    london_tz = ZoneInfo("Europe/London")
    now_london = datetime.now(london_tz)
    today_start_london = now_london.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_utc = today_start_london.astimezone(timezone.utc)

    # Historical article & AI output from 2 days ago
    past_dt = today_start_utc - timedelta(days=2)
    source = Source(name="Test Source", category="AI")
    test_db_session.add(source)
    test_db_session.flush()

    art_past = Article(
        source_id=source.id,
        title="Historical AI Breakthrough",
        canonical_url="https://example.com/past-ai",
        collected_at=past_dt,
        published_at=past_dt,
    )
    test_db_session.add(art_past)
    test_db_session.flush()

    ai_past = ArticleAIOutput(
        article_id=art_past.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        is_relevant=True,
        summary="Historical summary",
        status="success",
        processed_at=past_dt,
        created_at=past_dt,
    )
    test_db_session.add(ai_past)
    test_db_session.commit()

    stats = get_today_ai_context_stats(test_db_session, tz_name="Europe/London")
    assert stats["total_processed"] == 0
    assert stats["relevant_today"] == 0


def test_europe_london_utc_conversion_bst():
    """Requirement 2: Europe/London -> UTC conversion handles BST correctly."""
    # Test during BST (e.g. September 14, 2026 UTC+1)
    bst_tz = ZoneInfo("Europe/London")
    dt_bst = datetime(2026, 9, 14, 0, 0, 0, tzinfo=bst_tz)
    dt_utc = dt_bst.astimezone(timezone.utc)

    # Midnight 2026-09-14 BST equals 2026-09-13 23:00 UTC
    assert dt_utc == datetime(2026, 9, 13, 23, 0, 0, tzinfo=timezone.utc)


def test_unrestricted_rag_question_retrieves_historical_evidence():
    """Requirement 3: An unrestricted RAG question searches the complete archive."""
    parsed_from, parsed_to = parse_date_semantics("What are the key developments in AI?", filters=None)

    assert parsed_from is None
    assert parsed_to is None


def test_rag_today_phrase_restricts_to_today():
    """Requirement 4: 'today' in question restricts to today's local calendar day."""
    today_local = datetime.now(ZoneInfo("Europe/London")).date()
    parsed_from, parsed_to = parse_date_semantics("What happened today in technology?", filters=None)

    assert parsed_from == today_local
    assert parsed_to == today_local


def test_rag_yesterday_phrase_restricts_to_yesterday():
    """Requirement 5: 'yesterday' in question restricts to yesterday's local calendar day."""
    today_local = datetime.now(ZoneInfo("Europe/London")).date()
    yesterday_local = today_local - timedelta(days=1)

    parsed_from, parsed_to = parse_date_semantics("Show me yesterday's intelligence summary", filters=None)

    assert parsed_from == yesterday_local
    assert parsed_to == yesterday_local


def test_rag_this_week_phrase_restricts_to_recent_period():
    """Requirement 6: 'this week' / 'past 7 days' restricts to the recent 7 days."""
    today_local = datetime.now(ZoneInfo("Europe/London")).date()
    expected_start = today_local - timedelta(days=6)

    parsed_from, parsed_to = parse_date_semantics("What were the top stories this week?", filters=None)

    assert parsed_from == expected_start
    assert parsed_to == today_local


def test_explicit_date_filters_override_inferred_dates():
    """Requirement 7: Explicit date filters override inferred dates from question."""
    explicit_from = date(2025, 1, 24)
    explicit_to = date(2025, 1, 24)

    filters = {"date_from": explicit_from, "date_to": explicit_to}
    parsed_from, parsed_to = parse_date_semantics("What happened today?", filters=filters)

    assert parsed_from == explicit_from
    assert parsed_to == explicit_to


def test_existing_search_rag_behavior_intact(test_db_session: Session):
    """Requirement 8: Existing search & RAG ranking / filtering behavior remains intact."""
    source = Source(name="Global News", category="World")
    test_db_session.add(source)
    test_db_session.flush()

    art = Article(
        source_id=source.id,
        title="Global Economic Summit",
        canonical_url="https://example.com/summit-2026",
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
        summary="Summit discusses global economy.",
        status="success",
        importance_score=85,
        relevance_score=90,
    )
    test_db_session.add(ai_out)
    test_db_session.commit()

    res = search_articles_v1(test_db_session, query="Economic Summit", relevant_only=True)
    assert res["total"] >= 1
    assert any(a.id == art.id for a in res["articles"])
