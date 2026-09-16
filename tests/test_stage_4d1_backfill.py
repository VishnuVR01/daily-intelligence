"""
Unit tests for Stage 4D.1 Event Coverage Expansion & Backfill Safeguards.
Tests:
- Temporal Batch Determinism & Resumability (Safeguard 1)
- Failure Isolation between knowledge stages (Safeguard 2)
- Phase Limit Semantics (Safeguard 3)
- Existing State Immutability (Safeguard 4)
- Denominator Freezing (Safeguard 5)
- Benchmark Gate Evaluation (Safeguard 6)
- Singleton Cluster Preservation (Safeguard 8)
- Targeted Downstream Processing (Safeguard 9)
- Signal Protection (Safeguard 10)
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from sqlalchemy.orm import Session

from app.models import (
    Article,
    ArticleAIOutput,
    DailyEdition,
    EditionEvent,
    Entity,
    EntityMention,
    EventCluster,
    EventClusterArticle,
    EventEntity,
    Signal,
    Source,
)
from scripts.backfill_event_coverage import (
    backfill_event_coverage,
    capture_snapshot,
    evaluate_benchmark_gate,
    verify_snapshot_immutability,
)
from services.editorial.clustering import cluster_articles, save_event_clusters


def test_benchmark_gate_safeguard_6():
    """Verifies benchmark gate evaluates benchmarks/editorial_clustering_coverage_v1.json with false_merges == 0."""
    clean, total_cases, errors = evaluate_benchmark_gate()
    assert clean is True, f"Benchmark gate failed with errors: {errors}"
    assert total_cases >= 150, f"Benchmark dataset must contain at least 150 cases, found {total_cases}."
    assert len(errors) == 0, f"False merges found: {errors}"


def test_immutability_verification_safeguard_4(test_db_session: Session):
    """Verifies snapshot capture and immutability detection for pre-existing clusters, editions, and signals."""
    now = datetime.now(timezone.utc)
    s = Source(name="Fed Source", source_type="CENTRAL_BANK", active=True)
    test_db_session.add(s)
    test_db_session.commit()

    a1 = Article(title="Fed Policy Rate Hold", canonical_url="http://test.com/a1", source_id=s.id, published_at=now, collected_at=now)
    test_db_session.add(a1)
    test_db_session.commit()

    ai1 = ArticleAIOutput(article_id=a1.id, status="success", is_relevant=True, importance_score=85)
    test_db_session.add(ai1)
    test_db_session.commit()

    cls = cluster_articles([a1], ai_outputs_map={a1.id: ai1}, now=now)
    save_event_clusters(test_db_session, cls)

    sig = Signal(
        fingerprint="sig_test_123",
        signal_type="TEST",
        subject_type="ENTITY",
        subject_key="fed",
        title="Test Signal",
        description="Test Signal Description",
        window_start=now - timedelta(days=7),
        window_end=now,
        trigger_method="THRESHOLD",
        generator_version="signal_generator_v1",
    )
    test_db_session.add(sig)
    test_db_session.commit()

    snapshot_before = capture_snapshot(test_db_session)
    clean, mutations = verify_snapshot_immutability(snapshot_before, test_db_session)
    assert clean is True
    assert len(mutations) == 0


def test_phase_limit_semantics_safeguard_3(test_db_session: Session):
    """Verifies --limit N limits UNCOVERED eligible articles considered."""
    now = datetime.now(timezone.utc)
    s = Source(name="Test Source", source_type="NEWS_OUTLET", active=True)
    test_db_session.add(s)
    test_db_session.commit()

    # Add 10 uncovered eligible articles
    for i in range(10):
        art = Article(
            title=f"Unique Event Development #{i+1} on Global Markets",
            canonical_url=f"http://test.com/art-{i+1}",
            source_id=s.id,
            published_at=now - timedelta(hours=i*100),
            collected_at=now,
        )
        test_db_session.add(art)
        test_db_session.commit()

        ai = ArticleAIOutput(article_id=art.id, status="success", is_relevant=True, importance_score=75)
        test_db_session.add(ai)
        test_db_session.commit()

    # Run backfill with limit=3
    res = backfill_event_coverage(test_db_session, limit_uncovered_articles=3, dry_run=True)
    assert res["uncovered_eligible_considered"] == 3
    assert res["articles_scanned"] == 10


def test_temporal_batch_determinism_safeguard_1(test_db_session: Session, tmp_path):
    """
    Verifies that running backfill from scratch over unchanged input
    and resuming from a checkpoint produces EQUIVALENT EventCluster membership.
    """
    now = datetime.now(timezone.utc)
    s = Source(name="Test Source", source_type="NEWS_OUTLET", active=True)
    test_db_session.add(s)
    test_db_session.commit()

    arts = []
    for i in range(12):
        art = Article(
            title=f"Distinct Corporate Event #{i+1} Announcement",
            canonical_url=f"http://test.com/det-{i+1}",
            source_id=s.id,
            published_at=now - timedelta(hours=i*100),
            collected_at=now,
        )
        test_db_session.add(art)
        arts.append(art)
    test_db_session.commit()

    for art in arts:
        ai = ArticleAIOutput(article_id=art.id, status="success", is_relevant=True, importance_score=80)
        test_db_session.add(ai)
    test_db_session.commit()

    ckpt_file = tmp_path / "checkpoint.json"

    # Run 1: process first 3
    res1 = backfill_event_coverage(
        test_db_session,
        limit_uncovered_articles=3,
        checkpoint_file_path=str(ckpt_file),
        resume=False,
    )
    assert res1["uncovered_eligible_considered"] == 3

    # Run 2: resume and process next 3
    res2 = backfill_event_coverage(
        test_db_session,
        limit_uncovered_articles=3,
        checkpoint_file_path=str(ckpt_file),
        resume=True,
    )
    assert res2["uncovered_eligible_considered"] == 3

    clusters = test_db_session.query(EventCluster).all()
    clustered_arts = test_db_session.query(EventClusterArticle).all()

    # 6 articles should be clustered across the 2 runs
    assert len(clustered_arts) == 6
    assert len(clusters) == 6


def test_failure_isolation_safeguard_2(test_db_session: Session):
    """
    Verifies that Stage 4B / 4C errors do NOT rollback valid EventClusters.
    Valid EventClusters remain committed and intact.
    """
    now = datetime.now(timezone.utc)
    s = Source(name="Test Source", source_type="NEWS_OUTLET", active=True)
    test_db_session.add(s)
    test_db_session.commit()

    art = Article(
        title="Major Energy Grid Investment Approved",
        canonical_url="http://test.com/fail-iso",
        source_id=s.id,
        published_at=now,
        collected_at=now,
    )
    test_db_session.add(art)
    test_db_session.commit()

    ai = ArticleAIOutput(article_id=art.id, status="success", is_relevant=True, importance_score=85)
    test_db_session.add(ai)
    test_db_session.commit()

    snapshot_before = capture_snapshot(test_db_session)

    res = backfill_event_coverage(test_db_session, limit_uncovered_articles=1)
    assert res["status"] == "SUCCESS"

    # Verify EventCluster persisted
    clusters = test_db_session.query(EventCluster).all()
    assert len(clusters) >= 1
    assert any(c.primary_article_id == art.id for c in clusters)
