"""
Tests for Sprint 2 Stage 2C.2 — Pipeline Freshness Recovery & Test Isolation.
Verifies test database safety guard, 2-lane fresh/backlog queue allocation,
freshness SLA metrics calculation, and UI / route robustness.
"""
from datetime import datetime, timedelta, timezone
import pytest

from app.models import Article, ArticleAIOutput, Source, Base
from repositories.ai_outputs import claim_eligible_articles
from repositories.ai_queue import get_freshness_sla_metrics


def make_utc(dt: datetime) -> datetime:
    """Helper to convert SQLite naive datetime to UTC aware datetime."""
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def test_canonical_db_safety_guard_prevents_direct_writes(monkeypatch):
    """Verify that attempting to connect to canonical PostgreSQL inside tests triggers safety guard."""
    from tests.conftest import pytest_sessionstart
    from app.config import Settings
    import app.db

    dummy_settings = Settings()
    monkeypatch.setattr(dummy_settings, "database_url", "postgresql://user:pass@localhost:5432/daily_intelligence")
    monkeypatch.setattr("tests.conftest.get_settings", lambda: dummy_settings)

    class DummyConfig:
        main_input = None

    pytest_sessionstart(DummyConfig())

    with pytest.raises(RuntimeError, match="CANONICAL DB PROTECTION SAFETY GUARD TRIGGERED"):
        app.db.SessionLocal()


def test_isolated_db_fixture_uses_sqlite_in_memory(test_db_session):
    """Verify test_db_session fixture uses SQLite in-memory and isolates writes."""
    bind = test_db_session.get_bind()
    assert bind.dialect.name == "sqlite"
    
    # Create test source & article
    src = Source(name="Fixture Test Source", feed_url="https://example.com/feed", active=True)
    test_db_session.add(src)
    test_db_session.commit()

    art = Article(
        source_id=src.id,
        title="Isolated Test Article",
        canonical_url="https://example.com/isolated-1",
        published_at=datetime.now(timezone.utc),
        collected_at=datetime.now(timezone.utc),
    )
    test_db_session.add(art)
    test_db_session.commit()

    assert test_db_session.query(Article).count() == 1


def test_two_lane_fresh_vs_backlog_allocation(test_db_session):
    """
    Verify 2-lane allocation policy (7 FRESH / 3 BACKLOG target for a 10-item batch).
    Fresh articles (<2 hours old) are claimed in fresh lane.
    Older articles (>=2 hours old) are claimed in backlog lane.
    """
    now = datetime.now(timezone.utc)
    src = Source(name="Test Freshness Source", feed_url="https://example.com/rss", active=True)
    test_db_session.add(src)
    test_db_session.commit()

    # Create 10 Fresh Articles (<2 hours old)
    fresh_articles = []
    for i in range(10):
        art = Article(
            source_id=src.id,
            title=f"Fresh Article {i}",
            canonical_url=f"https://example.com/fresh-{i}",
            published_at=now - timedelta(minutes=10 + i),
            collected_at=now - timedelta(minutes=10 + i),
            raw_summary="Urgent critical security breach market shift",
        )
        test_db_session.add(art)
        fresh_articles.append(art)

    # Create 10 Backlog Articles (>2 hours old)
    backlog_articles = []
    for i in range(10):
        art = Article(
            source_id=src.id,
            title=f"Backlog Article {i}",
            canonical_url=f"https://example.com/backlog-{i}",
            published_at=now - timedelta(hours=5 + i),
            collected_at=now - timedelta(hours=5 + i),
            raw_summary="Historical archival text",
        )
        test_db_session.add(art)
        backlog_articles.append(art)

    test_db_session.commit()

    # Claim a batch of 10 articles
    claimed = claim_eligible_articles(test_db_session, batch_size=10)
    assert len(claimed) == 10

    # Count fresh vs backlog claimed
    claimed_fresh = [a for a in claimed if make_utc(a.collected_at) >= now - timedelta(hours=2)]
    claimed_backlog = [a for a in claimed if make_utc(a.collected_at) < now - timedelta(hours=2)]

    # Expected target allocation: 7 fresh, 3 backlog
    assert len(claimed_fresh) == 7
    assert len(claimed_backlog) == 3


def test_unused_fresh_capacity_flows_to_backlog(test_db_session):
    """If only 2 fresh articles exist, remaining 8 slots in a 10-item batch flow to backlog."""
    now = datetime.now(timezone.utc)
    src = Source(name="Test Capacity Source", feed_url="https://example.com/rss2", active=True)
    test_db_session.add(src)
    test_db_session.commit()

    # 2 Fresh
    for i in range(2):
        art = Article(
            source_id=src.id,
            title=f"Fresh Article {i}",
            canonical_url=f"https://example.com/fresh-flow-{i}",
            published_at=now - timedelta(minutes=15),
            collected_at=now - timedelta(minutes=15),
        )
        test_db_session.add(art)

    # 10 Backlog
    for i in range(10):
        art = Article(
            source_id=src.id,
            title=f"Backlog Article {i}",
            canonical_url=f"https://example.com/backlog-flow-{i}",
            published_at=now - timedelta(hours=10 + i),
            collected_at=now - timedelta(hours=10 + i),
        )
        test_db_session.add(art)

    test_db_session.commit()

    claimed = claim_eligible_articles(test_db_session, batch_size=10)
    assert len(claimed) == 10

    claimed_fresh = [a for a in claimed if make_utc(a.collected_at) >= now - timedelta(hours=2)]
    claimed_backlog = [a for a in claimed if make_utc(a.collected_at) < now - timedelta(hours=2)]

    assert len(claimed_fresh) == 2
    assert len(claimed_backlog) == 8


def test_empty_backlog_gives_full_capacity_to_fresh(test_db_session):
    """If 0 backlog articles exist, all 10 slots go to fresh articles."""
    now = datetime.now(timezone.utc)
    src = Source(name="Test Fresh Only Source", feed_url="https://example.com/rss3", active=True)
    test_db_session.add(src)
    test_db_session.commit()

    for i in range(10):
        art = Article(
            source_id=src.id,
            title=f"Fresh Article {i}",
            canonical_url=f"https://example.com/fresh-only-{i}",
            published_at=now - timedelta(minutes=20 + i),
            collected_at=now - timedelta(minutes=20 + i),
        )
        test_db_session.add(art)

    test_db_session.commit()

    claimed = claim_eligible_articles(test_db_session, batch_size=10)
    assert len(claimed) == 10
    for a in claimed:
        assert make_utc(a.collected_at) >= now - timedelta(hours=2)


def test_freshness_sla_metrics_calculation(test_db_session):
    """Verify get_freshness_sla_metrics returns truthful operational status."""
    now = datetime.now(timezone.utc)
    src = Source(name="SLA Test Source", feed_url="https://example.com/sla", active=True)
    test_db_session.add(src)
    test_db_session.commit()

    art1 = Article(
        source_id=src.id,
        title="SLA Fresh Article",
        canonical_url="https://example.com/sla-1",
        published_at=now - timedelta(minutes=10),
        collected_at=now - timedelta(minutes=10),
    )
    test_db_session.add(art1)
    test_db_session.commit()

    sla = get_freshness_sla_metrics(test_db_session)
    assert sla["fresh_queue_count"] == 1
    assert sla["backlog_queue_count"] == 0
    assert sla["minutes_since_ingestion"] is not None
    assert sla["minutes_since_ingestion"] <= 15.0
    assert sla["ingestion_status"] in ["FRESH", "HEALTHY"]


def test_duplicate_ai_outputs_remain_impossible(test_db_session):
    """Verify claiming an article twice creates locks and prevents duplicate AI processing outputs."""
    now = datetime.now(timezone.utc)
    src = Source(name="Dup Test Source", feed_url="https://example.com/dup", active=True)
    test_db_session.add(src)
    test_db_session.commit()

    art = Article(
        source_id=src.id,
        title="Unique Claim Article",
        canonical_url="https://example.com/unique-claim-1",
        published_at=now - timedelta(minutes=5),
        collected_at=now - timedelta(minutes=5),
    )
    test_db_session.add(art)
    test_db_session.commit()

    # First claim
    claimed1 = claim_eligible_articles(test_db_session, batch_size=5)
    assert len(claimed1) == 1
    assert claimed1[0].id == art.id

    # Second claim should find 0 eligible articles because article output is in status='processing'
    claimed2 = claim_eligible_articles(test_db_session, batch_size=5)
    assert len(claimed2) == 0
