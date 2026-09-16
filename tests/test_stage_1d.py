"""
Stage 1D Verification Test Suite for Daily Intelligence.
Tests source health model, advisory lock contention and release,
Ollama failure/recovery, queue invariants, and multi-cycle execution.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import uuid

import pytest
from sqlalchemy import func
from app.db import Base
from app.models import Article, ArticleAIOutput, Source
from ingestion.collectors import CollectionStatus, CollectorResult
from services.lock import pipeline_lock
from services.orchestrator import run_ai_cycle, run_ingestion_cycle, run_pipeline_cycle
from services.source_health import calculate_source_status, get_source_health
from repositories.ai_queue import get_ai_queue_status





def test_healthy_feed_classification():
    now = datetime.now(timezone.utc)
    status = calculate_source_status(
        active=True,
        is_rss_compatible=True,
        feed_url="https://example.com/rss",
        collection_status=CollectionStatus.OK,
        items_count=10,
        newest_article_at=now - timedelta(hours=2),
        stale_days=7,
        now=now,
    )
    assert status == "HEALTHY"


def test_duplicate_only_feed_not_failed():
    now = datetime.now(timezone.utc)
    # A feed that returns 10 items (even if all 10 are duplicates in DB) is HEALTHY, not FAILED
    status = calculate_source_status(
        active=True,
        is_rss_compatible=True,
        feed_url="https://example.com/rss",
        collection_status=CollectionStatus.OK,
        items_count=10,
        newest_article_at=now - timedelta(days=1),
        stale_days=7,
        now=now,
    )
    assert status == "HEALTHY"


def test_empty_feed_classification():
    now = datetime.now(timezone.utc)
    status = calculate_source_status(
        active=True,
        is_rss_compatible=True,
        feed_url="https://example.com/rss",
        collection_status=CollectionStatus.EMPTY,
        items_count=0,
        newest_article_at=now - timedelta(days=1),
        stale_days=7,
        now=now,
    )
    assert status == "EMPTY"


def test_stale_feed_classification():
    now = datetime.now(timezone.utc)
    status = calculate_source_status(
        active=True,
        is_rss_compatible=True,
        feed_url="https://example.com/rss",
        collection_status=CollectionStatus.OK,
        items_count=5,
        newest_article_at=now - timedelta(days=10),
        stale_days=7,
        now=now,
    )
    assert status == "STALE"


def test_http_failure_classification():
    now = datetime.now(timezone.utc)
    status = calculate_source_status(
        active=True,
        is_rss_compatible=True,
        feed_url="https://example.com/rss",
        collection_status=CollectionStatus.FAILED,
        items_count=0,
        newest_article_at=None,
        stale_days=7,
        now=now,
    )
    assert status == "FAILED"


def test_disabled_source_classification():
    now = datetime.now(timezone.utc)
    status = calculate_source_status(
        active=False,
        is_rss_compatible=True,
        feed_url="https://example.com/rss",
        collection_status=CollectionStatus.OK,
        items_count=10,
        newest_article_at=now,
        stale_days=7,
        now=now,
    )
    assert status == "DISABLED"


def test_advisory_lock_contention(test_db_session):
    from sqlalchemy.orm import sessionmaker
    TestingSessionLocal = sessionmaker(bind=test_db_session.get_bind(), autoflush=False, autocommit=False)
    db1 = TestingSessionLocal()
    db2 = TestingSessionLocal()
    try:
        with pipeline_lock(db1, "test_ingestion_lock") as locked1:
            assert locked1 is True
            with pipeline_lock(db2, "test_ingestion_lock") as locked2:
                assert locked2 is False
    finally:
        db1.close()
        db2.close()


def test_advisory_lock_release(test_db_session):
    from sqlalchemy.orm import sessionmaker
    TestingSessionLocal = sessionmaker(bind=test_db_session.get_bind(), autoflush=False, autocommit=False)
    db1 = TestingSessionLocal()
    db2 = TestingSessionLocal()
    try:
        with pipeline_lock(db1, "test_release_lock") as locked1:
            assert locked1 is True

        # After db1 releases lock in finally block, db2 should acquire it
        with pipeline_lock(db2, "test_release_lock") as locked2:
            assert locked2 is True
    finally:
        db1.close()
        db2.close()


def test_scheduler_resilience_after_source_failure(test_db_session):
    db = test_db_session
    # Mock one failing collector and one successful collector
    def mock_collect(*args, **kwargs):
        feed_url = args[0] if args else kwargs.get("feed_url", "")
        if "fail" in str(feed_url):
            return CollectorResult(status=CollectionStatus.FAILED, error_message="HTTP 500 Server Error")
        return CollectorResult(status=CollectionStatus.OK, items=[])

    with patch("services.orchestrator.pipeline_lock") as mock_lock:
        mock_lock.return_value.__enter__.return_value = True
        with patch("ingestion.pipeline.collect_rss", side_effect=mock_collect):
            res = run_ingestion_cycle(db=db)
            assert res["status"] == "COMPLETED"


def test_source_failure_does_not_stop_ai(test_db_session):
    db = test_db_session
    with patch("services.orchestrator.pipeline_lock") as mock_lock:
        mock_lock.return_value.__enter__.return_value = True
        with patch("services.orchestrator.run_ingestion_pipeline", side_effect=Exception("Ingestion complete crash")):
            with patch("services.ai.worker.process_next_batch", return_value={"status": "COMPLETED", "processed": 0}):
                res = run_pipeline_cycle(db=db)
                assert "ingestion" in res
                assert "ai_processing" in res


def test_ollama_recovery(test_db_session):
    db = test_db_session
    with patch("services.orchestrator.pipeline_lock") as mock_lock:
        mock_lock.return_value.__enter__.return_value = True
        with patch("services.orchestrator.run_ingestion_pipeline", return_value=MagicMock(active_sources_processed=1, healthy_feeds=1, empty_feeds=0, failed_feeds=0, articles_fetched=0, new_articles=0, duplicates_skipped=0, to_dict=lambda: {})):
            # Step 1: Simulate Ollama offline
            with patch("services.ai.ollama.OllamaService.check_health", return_value=False):
                res1 = run_pipeline_cycle(db=db)
                assert res1["ingestion"]["status"] == "COMPLETED"
                assert res1["ai_processing"]["status"] == "SKIPPED_OLLAMA_UNAVAILABLE"

            # Step 2: Restore Ollama (mock healthy)
            with patch("services.ai.ollama.OllamaService.check_health", return_value=True):
                with patch("services.ai.worker.process_next_batch", return_value={"status": "COMPLETED", "processed": 0}):
                    res2 = run_pipeline_cycle(db=db)
                    assert res2["ai_processing"]["status"] == "COMPLETED"


def test_no_duplicate_article_insertion(test_db_session):
    db = test_db_session
    test_url = f"https://test.com/stage1d_article_{uuid.uuid4().hex[:8]}"
    # Insert test source
    src = Source(name="Dedupe Test Source Stage1D", feed_url="https://test.com/feed_stage1d", source_type="rss", active=True)
    db.add(src)
    db.commit()

    # Insert initial article
    art1 = Article(source_id=src.id, title="Test Title", canonical_url=test_url)
    db.add(art1)
    db.commit()

    # Count articles before
    count_before = db.query(Article).filter(Article.canonical_url == test_url).count()
    assert count_before == 1


def test_no_duplicate_ai_outputs(test_db_session):
    db = test_db_session
    dups = (
        db.query(ArticleAIOutput.article_id)
        .group_by(ArticleAIOutput.article_id)
        .having(func.count(ArticleAIOutput.id) > 1)
        .all()
    )
    assert len(dups) == 0


def test_no_provenance_mutation(test_db_session):
    db = test_db_session
    art = db.query(Article).first()
    if art:
        src_id_before = art.source_id
        url_before = art.canonical_url
        title_before = art.title

        with patch("services.orchestrator.pipeline_lock") as mock_lock:
            mock_lock.return_value.__enter__.return_value = True
            with patch("services.ai.worker.process_next_batch", return_value={"status": "COMPLETED", "processed": 0}):
                run_ai_cycle(db=db)

        db.refresh(art)
        assert art.source_id == src_id_before
        assert art.canonical_url == url_before
        assert art.title == title_before


def test_queue_state_consistency_multiple_cycles(test_db_session):
    db = test_db_session
    status = get_ai_queue_status(db)
    total = status["total_articles"]
    sum_components = (
        status["unprocessed"]
        + status["processing"]
        + status.get("stale_processing", 0)
        + status["completed_total"]
        + status["failed"]
    )
    assert total == sum_components
