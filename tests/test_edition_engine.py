"""
Comprehensive unit & integration tests for Daily Edition Engine v1.
"""

from datetime import datetime, date, timedelta, timezone
import pytest
from sqlalchemy.orm import Session

from app.models import Article, ArticleAIOutput, Country, DailyEdition, EditionArticle, Source
from services.edition import (
    ALGORITHM_VERSION,
    calculate_title_similarity,
    generate_daily_edition,
    get_utc_window_for_date,
    resolve_edition_date,
    score_article,
)
from repositories.articles import (
    get_edition_articles_by_sections,
    get_edition_top_story,
    get_persisted_daily_edition,
)


@pytest.fixture
def sample_data(test_db_session: Session):
    """Seed test sources and articles with AI outputs."""
    src1 = Source(name="Financial Times", source_family="news", trust_tier="institutional", category="Markets & Economy")
    src2 = Source(name="Reuters Tech", source_family="news", trust_tier="primary", category="AI & Technology")
    src3 = Source(name="Niche Blog", source_family="news", trust_tier="social_signal", category="AI & Technology")
    test_db_session.add_all([src1, src2, src3])
    test_db_session.flush()

    c_uk = Country(code="GB", name="United Kingdom")
    c_us = Country(code="US", name="United States")
    test_db_session.add_all([c_uk, c_us])
    test_db_session.flush()

    now_utc = datetime.now(timezone.utc)
    pub_time = now_utc

    # 1. High quality relevant article
    art1 = Article(
        source_id=src1.id,
        title="Global Central Banks Adjust Benchmark Interest Rates",
        canonical_url="https://ft.com/rates-2026",
        published_at=pub_time,
        primary_category="Markets & Economy",
    )
    art1.countries.append(c_uk)

    # 2. Tech article from Reuters
    art2 = Article(
        source_id=src2.id,
        title="Frontier Artificial Intelligence Model Benchmark Results Released",
        canonical_url="https://reuters.com/ai-benchmark-2026",
        published_at=pub_time - timedelta(seconds=10),
        primary_category="AI & Technology",
    )
    art2.countries.append(c_us)

    # 3. Near duplicate of art2
    art3 = Article(
        source_id=src3.id,
        title="Frontier Artificial Intelligence Model Benchmark Results Released Today",
        canonical_url="https://nicheblog.com/ai-benchmark-dup",
        published_at=pub_time - timedelta(seconds=20),
        primary_category="AI & Technology",
    )

    # 4. Out of scope article (Sports)
    art4 = Article(
        source_id=src1.id,
        title="Local Football Team Wins Match 3-1",
        canonical_url="https://ft.com/sports-match",
        published_at=pub_time - timedelta(seconds=30),
        primary_category="Sports",
    )

    # 5. Legacy NULL relevance article
    art5 = Article(
        source_id=src2.id,
        title="Legacy Unanalyzed News Item",
        canonical_url="https://reuters.com/legacy-news",
        published_at=pub_time - timedelta(seconds=40),
        primary_category="AI & Technology",
    )

    test_db_session.add_all([art1, art2, art3, art4, art5])
    test_db_session.flush()

    # AI Outputs
    ai1 = ArticleAIOutput(article_id=art1.id, is_relevant=True, relevance_score=95, importance_score=85, primary_category="Markets & Economy", status="success")
    ai2 = ArticleAIOutput(article_id=art2.id, is_relevant=True, relevance_score=90, importance_score=80, primary_category="AI & Technology", status="success")
    ai3 = ArticleAIOutput(article_id=art3.id, is_relevant=True, relevance_score=85, importance_score=75, primary_category="AI & Technology", status="success")
    ai4 = ArticleAIOutput(article_id=art4.id, is_relevant=False, rejection_reason="Out of scope sports news", primary_category=None, status="success")
    ai5 = ArticleAIOutput(article_id=art5.id, is_relevant=None, primary_category="AI & Technology", status="success")

    test_db_session.add_all([ai1, ai2, ai3, ai4, ai5])
    test_db_session.commit()

    return {
        "art1": art1,
        "art2": art2,
        "art3": art3,
        "art4": art4,
        "art5": art5,
        "now_utc": now_utc,
    }


def test_date_window_conversion():
    target_d = date(2026, 9, 13)
    start_utc, end_utc = get_utc_window_for_date(target_d)
    assert start_utc < end_utc
    assert (end_utc - start_utc).total_seconds() > 86300


def test_headline_similarity():
    h1 = "Global Central Banks Adjust Benchmark Interest Rates"
    h2 = "Global Central Banks Adjust Benchmark Interest Rates"
    h3 = "Local Football Team Wins Match 3-1"

    assert calculate_title_similarity(h1, h2) == 1.0
    assert calculate_title_similarity(h1, h3) < 0.40


def test_score_calculation(sample_data):
    art1 = sample_data["art1"]
    now_utc = sample_data["now_utc"]

    score, breakdown = score_article(art1, now_utc, {}, {})
    assert score > 70.0
    assert breakdown["raw_relevance"] == 95
    assert breakdown["raw_importance"] == 85
    assert breakdown["trust_tier"] == "institutional"


def test_eligibility_and_out_of_scope_exclusion(test_db_session: Session, sample_data):
    today = resolve_edition_date()
    res = generate_daily_edition(test_db_session, edition_date=today, dry_run=True)

    meta = res["metadata_json"]
    ex = meta["excluded_counts"]

    # Out of scope sports story (art4) must be excluded
    assert ex["excluded_out_of_scope"] >= 1

    # Legacy NULL relevance story (art5) must be excluded
    assert ex["excluded_null_relevance"] >= 1

    # Eligible count should include art1 and art2
    assert meta["eligible_count"] >= 2


def test_deduplication(test_db_session: Session, sample_data):
    today = resolve_edition_date()
    res = generate_daily_edition(test_db_session, edition_date=today, dry_run=True)

    meta = res["metadata_json"]
    # art3 is near duplicate of art2
    assert meta["suppressed_duplicates_count"] >= 1
    suppressed_ids = [s["article_id"] for s in meta["suppressed_duplicates"]]
    assert sample_data["art3"].id in suppressed_ids


def test_dry_run_no_database_writes(test_db_session: Session, sample_data):
    today = resolve_edition_date()
    initial_count = test_db_session.query(DailyEdition).count()

    res = generate_daily_edition(test_db_session, edition_date=today, dry_run=True)

    assert res["status"] == "dry_run"
    final_count = test_db_session.query(DailyEdition).count()
    assert initial_count == final_count == 0


def test_persisted_edition_generation(test_db_session: Session, sample_data):
    today = resolve_edition_date()

    edition = generate_daily_edition(test_db_session, edition_date=today, force=False)

    assert isinstance(edition, DailyEdition)
    assert edition.id is not None
    assert edition.edition_date == today
    assert edition.algorithm_version == ALGORITHM_VERSION
    assert len(edition.edition_articles) >= 2

    # Verify no duplicate articles in edition
    article_ids = [ea.article_id for ea in edition.edition_articles]
    assert len(article_ids) == len(set(article_ids))


def test_idempotency_and_rerun(test_db_session: Session, sample_data):
    today = resolve_edition_date()

    ed1 = generate_daily_edition(test_db_session, edition_date=today, force=False)
    ed2 = generate_daily_edition(test_db_session, edition_date=today, force=False)

    assert ed1.id == ed2.id

    # Test force regeneration
    ed3 = generate_daily_edition(test_db_session, edition_date=today, force=True)
    assert isinstance(ed3, DailyEdition)


def test_homepage_reading_persisted_edition(test_db_session: Session, sample_data):
    today = resolve_edition_date()
    edition = generate_daily_edition(test_db_session, edition_date=today, force=True)

    fetched_edition = get_persisted_daily_edition(test_db_session, today)
    assert fetched_edition is not None
    assert fetched_edition.id == edition.id

    top_story = get_edition_top_story(test_db_session, fetched_edition)
    assert top_story is not None

    sections = get_edition_articles_by_sections(test_db_session, fetched_edition)
    assert "Top Intelligence" in sections
    assert len(sections["Top Intelligence"]) >= 1


def test_missing_edition_safe_fallback(test_db_session: Session):
    past_date = date(2020, 1, 1)
    fetched_edition = get_persisted_daily_edition(test_db_session, past_date)
    assert fetched_edition is None

    top_story = get_edition_top_story(test_db_session, fetched_edition)
    assert top_story is None
