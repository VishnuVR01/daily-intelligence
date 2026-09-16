"""
Unit tests for Stage 3B Event Clustering & Story Deduplication (Sprint 3 Stage 3B).
"""
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models import Article, ArticleAIOutput, EventCluster, EventClusterArticle, Source
from services.editorial.scorer import calculate_article_editorial_score
from services.editorial.clustering import (
    normalize_text,
    normalize_token,
    extract_key_entities,
    extract_numeric_markers,
    calculate_title_similarity,
    calculate_entity_overlap,
    compare_articles_similarity,
    generate_candidate_pairs,
    cluster_articles,
    save_event_clusters,
)


@pytest.fixture
def dummy_source(test_db_session: Session):
    s = Source(
        name="Test News Service",
        source_type="NEWS_OUTLET",
        category="Markets & Economy",
        active=True
    )
    test_db_session.add(s)
    test_db_session.commit()
    test_db_session.refresh(s)
    return s


@pytest.fixture
def central_bank_source(test_db_session: Session):
    s = Source(
        name="Federal Reserve",
        source_type="CENTRAL_BANK",
        category="Markets & Economy",
        active=True
    )
    test_db_session.add(s)
    test_db_session.commit()
    test_db_session.refresh(s)
    return s


def test_normalization_and_aliases():
    assert normalize_token("Fed") == "federal reserve"
    assert normalize_token("BOE") == "bank of england"
    assert normalize_token("ECB") == "european central bank"
    
    raw_text = "The Fed's FOMC announced policy changes in Washington."
    norm = normalize_text(raw_text)
    assert "federal reserve" in norm


def test_generic_entity_suppression():
    text = "United States tech market shows economic growth in AI sector."
    entities = extract_key_entities(text)
    assert "united states" not in entities
    assert "ai" not in entities
    assert "market" not in entities


def test_numeric_token_preservation():
    text1 = "Fed cuts rates by 25 bps to 4.75%"
    text2 = "Fed holds rates at 5.00%"
    
    num1 = extract_numeric_markers(text1)
    num2 = extract_numeric_markers(text2)
    
    assert "25bps" in num1 or "4.75%" in num1
    assert "5.00%" in num2
    assert num1 != num2


def test_title_similarity_matching():
    t1 = "Federal Reserve cuts interest rates by 25 basis points"
    t2 = "Fed lowers rate by 25 bps in policy shift"
    sim = calculate_title_similarity(t1, t2)
    assert sim > 0.30


def test_same_topic_different_event():
    now = datetime.now(timezone.utc)
    a1 = Article(
        id=101,
        title="Federal Reserve Board approves application of Fifth Third Bank",
        canonical_url="http://test.com/1",
        primary_category="Markets & Economy",
        published_at=now,
        collected_at=now,
    )
    a2 = Article(
        id=102,
        title="Federal Reserve Board issues enforcement action against regional bank",
        canonical_url="http://test.com/2",
        primary_category="Markets & Economy",
        published_at=now,
        collected_at=now,
    )
    comp = compare_articles_similarity(a1, a2)
    assert comp.confidence_band != "HIGH_CONFIDENCE"


def test_fed_same_event_clustering(dummy_source, central_bank_source):
    now = datetime.now(timezone.utc)
    a1 = Article(
        id=201,
        source_id=central_bank_source.id,
        source=central_bank_source,
        title="Fed holds interest rates steady at 4.75%-5.00% target range",
        canonical_url="http://fed.gov/1",
        primary_category="Markets & Economy",
        published_at=now,
        collected_at=now,
    )
    a2 = Article(
        id=202,
        source_id=dummy_source.id,
        source=dummy_source,
        title="Federal Reserve leaves interest rates unchanged at 4.75%-5.00%",
        canonical_url="http://reuters.com/1",
        primary_category="Markets & Economy",
        published_at=now - timedelta(minutes=25),
        collected_at=now,
    )

    clusters = cluster_articles([a1, a2], now=now)
    assert len(clusters) == 1
    cl = clusters[0]
    assert cl.article_count == 2
    assert cl.distinct_source_count == 2
    assert cl.primary_article_id == a1.id  # Central bank primary source preferred
    assert len(cl.supporting_articles) == 1
    assert cl.supporting_articles[0].id == a2.id


def test_distinct_source_corroboration(dummy_source, central_bank_source):
    now = datetime.now(timezone.utc)
    a1 = Article(
        id=301,
        source_id=central_bank_source.id,
        source=central_bank_source,
        title="ECB cuts Deposit Facility Rate by 25 bps to 3.25%",
        canonical_url="http://ecb.europa.eu/1",
        primary_category="Markets & Economy",
        published_at=now,
        collected_at=now,
    )
    a2 = Article(
        id=302,
        source_id=dummy_source.id,
        source=dummy_source,
        title="ECB reduces deposit rate by 25 bps to 3.25% in rate cut",
        canonical_url="http://bloomberg.com/1",
        primary_category="Markets & Economy",
        published_at=now - timedelta(minutes=10),
        collected_at=now,
    )

    clusters = cluster_articles([a1, a2], now=now)
    assert len(clusters) == 1
    cl = clusters[0]
    # Cluster score should receive corroboration bonus (+5 for 2nd distinct source)
    assert cl.cluster_score > cl.metadata_json["primary_editorial_score"]
    assert cl.metadata_json["corroboration_bonus"] == 5.0


def test_same_source_repetition_no_corroboration_bonus(dummy_source):
    now = datetime.now(timezone.utc)
    a1 = Article(
        id=401,
        source_id=dummy_source.id,
        source=dummy_source,
        title="NVIDIA announces Vera Rubin NVLink architecture at GTC 2026",
        canonical_url="http://test.com/a1",
        primary_category="AI & Technology",
        published_at=now,
        collected_at=now,
    )
    a2 = Article(
        id=402,
        source_id=dummy_source.id,
        source=dummy_source,
        title="NVIDIA unveils Vera Rubin NVLink GPU architecture at keynote",
        canonical_url="http://test.com/a2",
        primary_category="AI & Technology",
        published_at=now - timedelta(minutes=15),
        collected_at=now,
    )

    clusters = cluster_articles([a1, a2], now=now)
    assert len(clusters) == 1
    cl = clusters[0]
    assert cl.distinct_source_count == 1
    assert cl.metadata_json["corroboration_bonus"] == 0.0


def test_cluster_score_bounded_0_to_100(dummy_source):
    now = datetime.now(timezone.utc)
    a1 = Article(
        id=501,
        source_id=dummy_source.id,
        source=dummy_source,
        title="Major global economic announcement breaks market records",
        canonical_url="http://test.com/501",
        primary_category="Markets & Economy",
        published_at=now,
        collected_at=now,
    )
    clusters = cluster_articles([a1], now=now)
    assert 0.0 <= clusters[0].cluster_score <= 100.0


def test_deterministic_fingerprint_ids(dummy_source):
    now = datetime.now(timezone.utc)
    a1 = Article(id=601, source_id=dummy_source.id, title="Test Event 1", published_at=now, collected_at=now)
    a2 = Article(id=602, source_id=dummy_source.id, title="Test Event 1 Duplicate", published_at=now, collected_at=now)
    
    res1 = cluster_articles([a1, a2], now=now)
    res2 = cluster_articles([a1, a2], now=now)
    
    assert res1[0].cluster_id == res2[0].cluster_id
    assert res1[0].primary_article_id == res2[0].primary_article_id


def test_cross_midnight_events(dummy_source):
    # Event starting 23:45 Day 1, continuing 00:30 Day 2
    t1 = datetime(2026, 9, 14, 23, 45, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 15, 0, 30, tzinfo=timezone.utc)
    
    a1 = Article(id=701, source_id=dummy_source.id, title="Midnight Rate Announcement by Central Bank", published_at=t1, collected_at=t1)
    a2 = Article(id=702, source_id=dummy_source.id, title="Central Bank Midnight Rate Decision reaction", published_at=t2, collected_at=t2)
    
    candidate_pairs = generate_candidate_pairs([a1, a2], max_window_hours=48.0)
    assert len(candidate_pairs) == 1


def test_database_persistence_and_idempotency(test_db_session: Session, dummy_source):
    now = datetime.now(timezone.utc)
    a1 = Article(
        id=801,
        source_id=dummy_source.id,
        source=dummy_source,
        title="Persisted Event Title 1",
        canonical_url="http://test.com/p1",
        primary_category="Markets & Economy",
        published_at=now,
        collected_at=now,
    )
    a2 = Article(
        id=802,
        source_id=dummy_source.id,
        source=dummy_source,
        title="Persisted Event Title 1 Supporting",
        canonical_url="http://test.com/p2",
        primary_category="Markets & Economy",
        published_at=now - timedelta(minutes=5),
        collected_at=now,
    )
    test_db_session.add_all([a1, a2])
    test_db_session.commit()

    clusters = cluster_articles([a1, a2], now=now)
    save_event_clusters(test_db_session, clusters)

    # Query DB
    db_clusters = test_db_session.query(EventCluster).all()
    assert len(db_clusters) == 1
    c_db = db_clusters[0]
    assert c_db.cluster_id == clusters[0].cluster_id
    assert c_db.article_count == 2
    
    db_arts = test_db_session.query(EventClusterArticle).filter(EventClusterArticle.cluster_id == c_db.cluster_id).all()
    assert len(db_arts) == 2
    prim_art = [x for x in db_arts if x.is_primary][0]
    assert prim_art.article_id == a1.id

    # Idempotent re-run
    save_event_clusters(test_db_session, clusters)
    db_clusters_retry = test_db_session.query(EventCluster).all()
    assert len(db_clusters_retry) == 1


def test_failure_fallback_leaves_articles_intact():
    now = datetime.now(timezone.utc)
    a1 = Article(id=901, title="Article 901", published_at=now, collected_at=now)
    a2 = Article(id=902, title="Article 902", published_at=now, collected_at=now)
    
    # Passing empty or invalid inputs returns singletons/fallback cleanly
    clusters = cluster_articles([a1, a2])
    assert len(clusters) == 2  # Separates into singletons safely
