"""
Unit test suite for Stage 4C: Event Participant Linking & Grounded Timelines.
"""

import json
from datetime import date, datetime, timezone
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
)
from services.knowledge.event_linking import (
    determine_entity_role,
    determine_evidence_class,
    link_event_entities,
)
from services.knowledge.resolution import seed_curated_entities
from services.knowledge.timeline import get_entity_timeline


def test_evidence_class_determination():
    assert determine_evidence_class(is_title_hit=True, is_primary_hit=False, supporting_article_count=1, distinct_source_count=1) == "PRIMARY_EXPLICIT"
    assert determine_evidence_class(is_title_hit=False, is_primary_hit=True, supporting_article_count=1, distinct_source_count=1) == "PRIMARY_EXPLICIT"
    assert determine_evidence_class(is_title_hit=False, is_primary_hit=False, supporting_article_count=2, distinct_source_count=2) == "MULTI_ARTICLE"
    assert determine_evidence_class(is_title_hit=False, is_primary_hit=False, supporting_article_count=1, distinct_source_count=1) == "INCIDENTAL"



def test_role_determination(test_db_session: Session):
    seed_curated_entities(test_db_session)

    fed = test_db_session.query(Entity).filter(Entity.normalized_name == "federal reserve").first()
    assert fed is not None
    assert determine_entity_role(fed, {"Central Bank"}, is_title_hit=True, is_primary_hit=True, cluster_category="MONETARY_POLICY") == "ISSUER"

    us = test_db_session.query(Entity).filter(Entity.normalized_name == "united states").first()
    assert us is not None
    assert determine_entity_role(us, {"Country"}, is_title_hit=False, is_primary_hit=True, cluster_category="MONETARY_POLICY") == "LOCATION"

    openai = test_db_session.query(Entity).filter(Entity.normalized_name == "openai").first()
    assert openai is not None
    assert determine_entity_role(openai, {"Company"}, is_title_hit=True, is_primary_hit=True, cluster_category="TECHNOLOGY") == "ACTOR"

    brent = test_db_session.query(Entity).filter(Entity.normalized_name == "brent crude").first()
    assert brent is not None
    assert determine_entity_role(brent, {"Commodity"}, is_title_hit=True, is_primary_hit=True, cluster_category="COMMODITIES") == "SUBJECT"


def test_event_entity_benchmark():
    benchmark_file = Path(__file__).resolve().parent.parent / "benchmarks" / "event_entity_v1.json"
    assert benchmark_file.exists()

    with open(benchmark_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    total = len(cases)
    correct = 0
    false_links = 0

    for case in cases:
        is_title_hit = case["is_title_hit"]
        is_primary_hit = case["is_primary_hit"]
        sup_articles = case["supporting_article_count"]
        sup_sources = case["distinct_source_count"]
        expected_link = case["expected_link"]
        expected_role = case["expected_role"]

        e_class = determine_evidence_class(is_title_hit, is_primary_hit, sup_articles, sup_sources)
        should_link = not (e_class == "INCIDENTAL" and not is_title_hit and not is_primary_hit and sup_articles < 2)

        if should_link == expected_link:
            correct += 1
        else:
            if should_link and not expected_link:
                false_links += 1

    precision = (correct / total) * 100
    assert false_links == 0, f"Expected 0 false links, got {false_links}"
    assert precision >= 95.0, f"Expected precision >= 95%, got {precision:.2f}%"


def test_link_event_entities_and_idempotency(test_db_session: Session):
    seed_curated_entities(test_db_session)

    # Setup Article & AI Output
    article = Article(
        title="Federal Reserve Raises Rates Test 4C",
        canonical_url="http://example.com/fed-rates-test-4c-unique",
        extracted_text="The Federal Reserve raised interest rates in the United States.",
        published_at=datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc),
    )
    test_db_session.add(article)
    test_db_session.flush()

    ai_output = ArticleAIOutput(
        article_id=article.id,
        status="success",
        is_relevant=True,
        importance_score=90,
        primary_category="MONETARY_POLICY",
        output_json={
            "entities": [
                {"name": "Federal Reserve", "type": "CENTRAL_BANK"},
                {"name": "United States", "type": "COUNTRY"},
            ]
        },
    )
    test_db_session.add(ai_output)
    test_db_session.flush()

    # Create mentions
    fed = test_db_session.query(Entity).filter(Entity.normalized_name == "federal reserve").first()
    us = test_db_session.query(Entity).filter(Entity.normalized_name == "united states").first()

    m1 = EntityMention(
        entity_id=fed.id,
        article_id=article.id,
        surface_form="Federal Reserve",
        raw_entity_type="Central Bank",
        resolved_entity_type="CENTRAL_BANK",
        confidence_class="HIGH",
        extraction_method="EXACT_CANONICAL",
    )
    m2 = EntityMention(
        entity_id=us.id,
        article_id=article.id,
        surface_form="United States",
        raw_entity_type="Country",
        resolved_entity_type="COUNTRY",
        confidence_class="HIGH",
        extraction_method="COUNTRY_ALIAS",
    )
    test_db_session.add_all([m1, m2])
    test_db_session.flush()

    # Create EventCluster & EventClusterArticle
    cluster_id = "test-cluster-stage-4c-001"
    cluster = EventCluster(
        cluster_id=cluster_id,
        canonical_title="Federal Reserve Interest Rate Decision",
        primary_article_id=article.id,
        category="MONETARY_POLICY",
        distinct_source_count=1,
        article_count=1,
        cluster_score=95.0,
        earliest_article_at=datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc),
    )
    test_db_session.add(cluster)
    test_db_session.flush()

    cluster_art = EventClusterArticle(
        cluster_id=cluster_id,
        article_id=article.id,
        is_primary=True,
        article_relationship="PRIMARY",
    )
    test_db_session.add(cluster_art)
    test_db_session.commit()

    # First run
    res1 = link_event_entities(test_db_session, cluster_id)
    assert res1["links_created"] == 2
    assert res1["status"] == "SUCCESS"

    links1 = test_db_session.query(EventEntity).filter(EventEntity.event_cluster_id == cluster_id).all()
    assert len(links1) == 2

    # Verify roles
    roles = {link.entity.normalized_name: link.role for link in links1}
    assert roles["federal reserve"] == "ISSUER"
    assert roles["united states"] == "LOCATION"

    # Second run (idempotency check)
    res2 = link_event_entities(test_db_session, cluster_id)
    assert res2["links_created"] == 0
    assert res2["links_updated"] == 2

    links2 = test_db_session.query(EventEntity).filter(EventEntity.event_cluster_id == cluster_id).all()
    assert len(links2) == 2


def test_timeline_service(test_db_session: Session):
    seed_curated_entities(test_db_session)
    fed = test_db_session.query(Entity).filter(Entity.normalized_name == "federal reserve").first()
    assert fed is not None

    # Retrieve timeline
    timeline = get_entity_timeline(test_db_session, fed.id)
    assert timeline["entity"]["canonical_name"] == "Federal Reserve"
    assert "events" in timeline
    assert isinstance(timeline["events"], list)
