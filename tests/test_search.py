"""
Unit & integration tests for Historical Search Query Service v1.
"""

from datetime import datetime, date, timedelta, timezone
import pytest
from sqlalchemy.orm import Session

from app.models import Article, ArticleAIOutput, Country, Source
from repositories.articles import search_articles_v1


@pytest.fixture
def search_sample_data(test_db_session: Session):
    """Seed test articles for search filtering and ranking tests."""
    src_ft = Source(name="Financial Times", source_family="news", trust_tier="institutional", category="Markets & Economy", country_code="GB")
    src_reuters = Source(name="Reuters Tech", source_family="news", trust_tier="primary", category="AI & Technology", country_code="US")
    test_db_session.add_all([src_ft, src_reuters])
    test_db_session.flush()

    c_uk = Country(code="GB", name="United Kingdom")
    c_us = Country(code="US", name="United States")
    test_db_session.add_all([c_uk, c_us])
    test_db_session.flush()

    now_utc = datetime.now(timezone.utc)

    # 1. Semiconductor article
    art1 = Article(
        source_id=src_reuters.id,
        title="Revolutionizing semiconductor fab operations with artificial intelligence",
        canonical_url="https://reuters.com/semiconductor-fab-ai",
        published_at=now_utc - timedelta(days=2),
        primary_category="AI & Technology",
    )
    art1.countries.append(c_us)

    # 2. Inflation article
    art2 = Article(
        source_id=src_ft.id,
        title="Reserve Bank Inflation Outlook and Economic Growth Strategy",
        canonical_url="https://ft.com/rbi-inflation-2026",
        published_at=now_utc - timedelta(days=5),
        primary_category="Markets & Economy",
    )
    art2.countries.append(c_uk)

    # 3. Oil article
    art3 = Article(
        source_id=src_ft.id,
        title="Global Oil Production Caps Agreed by Energy Ministers",
        canonical_url="https://ft.com/oil-production-2026",
        published_at=now_utc - timedelta(days=10),
        primary_category="Energy",
    )

    test_db_session.add_all([art1, art2, art3])
    test_db_session.flush()

    ai1 = ArticleAIOutput(
        article_id=art1.id,
        is_relevant=True,
        relevance_score=95,
        importance_score=88,
        primary_category="AI & Technology",
        summary="Advanced AI tools optimize semiconductor microchip manufacturing throughput.",
        output_json={"topics": ["Semiconductor", "Microchips"], "entities": [{"name": "NVIDIA"}]},
        status="success",
    )
    ai2 = ArticleAIOutput(
        article_id=art2.id,
        is_relevant=True,
        relevance_score=90,
        importance_score=82,
        primary_category="Markets & Economy",
        summary="Central bank signals policy rate adjustments to curb persistent inflation.",
        output_json={"topics": ["Inflation", "Monetary Policy"], "entities": [{"name": "RBI"}]},
        status="success",
    )
    ai3 = ArticleAIOutput(
        article_id=art3.id,
        is_relevant=True,
        relevance_score=85,
        importance_score=75,
        primary_category="Energy",
        summary="Oil market supply constraints impact global energy prices.",
        output_json={"topics": ["Oil", "Commodities"], "entities": []},
        status="success",
    )

    test_db_session.add_all([ai1, ai2, ai3])
    test_db_session.commit()

    return {"art1": art1, "art2": art2, "art3": art3, "now_utc": now_utc}


def test_search_exact_headline_match(test_db_session: Session, search_sample_data):
    res = search_articles_v1(test_db_session, query="semiconductor")
    assert res["total"] >= 1
    matched_ids = [a.id for a in res["articles"]]
    assert search_sample_data["art1"].id in matched_ids


def test_search_topic_and_entity_match(test_db_session: Session, search_sample_data):
    res = search_articles_v1(test_db_session, query="NVIDIA")
    assert res["total"] >= 1
    assert res["articles"][0].id == search_sample_data["art1"].id


def test_search_category_filter(test_db_session: Session, search_sample_data):
    res = search_articles_v1(test_db_session, query="", categories=["Markets & Economy"])
    assert res["total"] >= 1
    for a in res["articles"]:
        assert a.primary_category == "Markets & Economy" or a.source.category == "Markets & Economy"


def test_search_country_filter(test_db_session: Session, search_sample_data):
    res = search_articles_v1(test_db_session, query="", countries=["US"])
    assert res["total"] >= 1
    matched_ids = [a.id for a in res["articles"]]
    assert search_sample_data["art1"].id in matched_ids


def test_search_date_filtering(test_db_session: Session, search_sample_data):
    today = date.today()
    five_days_ago = today - timedelta(days=5)
    res = search_articles_v1(test_db_session, query="", date_from=five_days_ago, date_to=today)
    assert res["total"] >= 1


def test_search_min_importance_filter(test_db_session: Session, search_sample_data):
    res = search_articles_v1(test_db_session, query="", min_importance=85)
    assert res["total"] >= 1
    for a in res["articles"]:
        ai_out = a.ai_outputs[0]
        assert ai_out.importance_score >= 85


def test_search_empty_results(test_db_session: Session, search_sample_data):
    res = search_articles_v1(test_db_session, query="nonexistentunlikelykeywordxyz123")
    assert res["total"] == 0
    assert len(res["articles"]) == 0


def test_search_deterministic_ranking(test_db_session: Session, search_sample_data):
    res1 = search_articles_v1(test_db_session, query="inflation")
    res2 = search_articles_v1(test_db_session, query="inflation")
    assert [a.id for a in res1["articles"]] == [a.id for a in res2["articles"]]
    assert res1["scores"] == res2["scores"]
