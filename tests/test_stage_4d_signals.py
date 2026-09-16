"""
Unit test suite for Stage 4D: Observed Signals & Pattern Detection Engine.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from sqlalchemy.orm import Session

from app.models import (
    Article,
    ArticleAIOutput,
    Entity,
    EntityMention,
    EventCluster,
    EventClusterArticle,
    EventEntity,
    Signal,
    SignalEvidence,
)
from services.knowledge.resolution import seed_curated_entities
from services.knowledge.signals import (
    compute_signal_fingerprint,
    contains_forbidden_predictive_language,
    detect_and_generate_signals,
)


def test_language_safety_filter():
    assert contains_forbidden_predictive_language("OpenAI will release a new model") is True
    assert contains_forbidden_predictive_language("Central banks are likely to cut rates") is True
    assert contains_forbidden_predictive_language("Inflation is forecast to fall") is True
    assert contains_forbidden_predictive_language("Outage was caused by storm") is True
    assert contains_forbidden_predictive_language("Observed 4 events involving OpenAI across 3 distinct sources") is False
    assert contains_forbidden_predictive_language("Recorded 3 policy events during the observation window") is False


def test_fingerprint_snapshot_semantics():
    fp1 = compute_signal_fingerprint("ENTITY_CONCENTRATION", "entity:openai", "2026-09-01T00:00:00Z", "2026-09-07T23:59:59Z", ["evt_1", "evt_2"])
    fp2 = compute_signal_fingerprint("ENTITY_CONCENTRATION", "entity:openai", "2026-09-01T00:00:00Z", "2026-09-07T23:59:59Z", ["evt_1", "evt_2"])
    fp3 = compute_signal_fingerprint("ENTITY_CONCENTRATION", "entity:openai", "2026-09-01T00:00:00Z", "2026-09-07T23:59:59Z", ["evt_1", "evt_2", "evt_3"])

    assert fp1 == fp2  # Identical evidence -> Identical fingerprint
    assert fp1 != fp3  # Membership changed -> Different fingerprint


def test_signal_benchmark():
    benchmark_file = Path(__file__).resolve().parent.parent / "benchmarks" / "signals_v1.json"
    assert benchmark_file.exists()

    with open(benchmark_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    total = len(cases)
    correct = 0
    false_positives = 0
    language_failures = 0

    for case in cases:
        event_count = case["event_count"]
        title = case["title"]
        description = case["description"]
        expected_qualify = case["expected_qualify"]
        expected_lang_safe = case["expected_language_safe"]

        is_lang_safe = not (contains_forbidden_predictive_language(title) or contains_forbidden_predictive_language(description))
        qualifies = (event_count >= 2) and is_lang_safe

        if is_lang_safe != expected_lang_safe:
            language_failures += 1

        if qualifies == expected_qualify:
            correct += 1
        else:
            if qualifies and not expected_qualify:
                false_positives += 1

    precision = (correct / total) * 100
    assert false_positives == 0, f"Expected 0 false positive signals, got {false_positives}"
    assert language_failures == 0, f"Expected 0 language safety failures, got {language_failures}"
    assert precision >= 95.0, f"Expected precision >= 95%, got {precision:.2f}%"


def test_null_safe_evidence_uniqueness_and_idempotency(test_db_session: Session):
    seed_curated_entities(test_db_session)
    now_dt = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)

    # Setup 2 events without specific entity (entity_id=None evidence)
    article1 = Article(title="Tech Event 1", canonical_url="http://example.com/tech-1-unique", published_at=now_dt)
    article2 = Article(title="Tech Event 2", canonical_url="http://example.com/tech-2-unique", published_at=now_dt)
    test_db_session.add_all([article1, article2])
    test_db_session.flush()

    c1 = EventCluster(cluster_id="evt_tech_001", canonical_title="Tech Event 1", primary_article_id=article1.id, category="AI & Technology", cluster_score=90.0, earliest_article_at=now_dt)
    c2 = EventCluster(cluster_id="evt_tech_002", canonical_title="Tech Event 2", primary_article_id=article2.id, category="AI & Technology", cluster_score=85.0, earliest_article_at=now_dt)
    test_db_session.add_all([c1, c2])
    test_db_session.commit()

    # First run
    res1 = detect_and_generate_signals(test_db_session, window_days=7, as_of_time=now_dt)
    assert res1["signals_created"] > 0
    assert res1["status"] == "SUCCESS"

    signals1 = test_db_session.query(Signal).all()
    evidence1 = test_db_session.query(SignalEvidence).all()
    count_sig1 = len(signals1)
    count_ev1 = len(evidence1)

    # Verify normalized subject fields (Amendment 3)
    for s in signals1:
        assert s.subject_type in ("ENTITY", "CATEGORY", "GEOGRAPHY", "POLICY_DOMAIN")
        assert s.subject_key is not None

    # Second run (idempotency & null-safe uniqueness check)
    res2 = detect_and_generate_signals(test_db_session, window_days=7, as_of_time=now_dt)
    assert res2["signals_created"] == 0
    assert res2["evidence_created"] == 0

    signals2 = test_db_session.query(Signal).all()
    evidence2 = test_db_session.query(SignalEvidence).all()
    assert len(signals2) == count_sig1
    assert len(evidence2) == count_ev1


def test_deterministic_limiting(test_db_session: Session):
    now_dt = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)

    # Setup 3 events
    a1 = Article(title="AI 1", canonical_url="http://example.com/ai-1", published_at=now_dt)
    a2 = Article(title="AI 2", canonical_url="http://example.com/ai-2", published_at=now_dt)
    a3 = Article(title="AI 3", canonical_url="http://example.com/ai-3", published_at=now_dt)
    test_db_session.add_all([a1, a2, a3])
    test_db_session.flush()

    c1 = EventCluster(cluster_id="evt_lim_01", canonical_title="AI 1", primary_article_id=a1.id, category="AI & Technology", cluster_score=90.0, earliest_article_at=now_dt)
    c2 = EventCluster(cluster_id="evt_lim_02", canonical_title="AI 2", primary_article_id=a2.id, category="AI & Technology", cluster_score=85.0, earliest_article_at=now_dt)
    c3 = EventCluster(cluster_id="evt_lim_03", canonical_title="AI 3", primary_article_id=a3.id, category="AI & Technology", cluster_score=80.0, earliest_article_at=now_dt)
    test_db_session.add_all([c1, c2, c3])
    test_db_session.commit()

    res_lim1 = detect_and_generate_signals(test_db_session, window_days=7, limit=1, as_of_time=now_dt, dry_run=True)
    res_lim2 = detect_and_generate_signals(test_db_session, window_days=7, limit=1, as_of_time=now_dt, dry_run=True)

    # Identical deterministic selection under --limit (Amendment 5)
    assert len(res_lim1["signals"]) == 1
    assert len(res_lim2["signals"]) == 1
    assert res_lim1["signals"][0]["fingerprint"] == res_lim2["signals"][0]["fingerprint"]
