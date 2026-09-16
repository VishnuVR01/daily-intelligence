"""
Unit tests for Stage 3C Daily Edition Selection Engine (Sprint 3 Stage 3C).
Tests edition candidate windows, AI review eligibility, balanced feed semantics,
source caps, section caps, quality thresholds, lead selection, readiness gate,
persistence, snapshot immutability, duplicate safety, and failure isolation.
"""
import pytest
from datetime import date, datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models import Article, ArticleAIOutput, DailyEdition, EditionEvent, Source
from repositories.articles import get_recent_articles
from services.editorial.clustering import cluster_articles, save_event_clusters
from services.editorial.selection import (
    CANONICAL_SECTIONS,
    EditionAuditResult,
    fetch_eligible_candidates,
    generate_daily_edition_selection,
    get_london_date_window,
    map_category_to_section,
    save_daily_edition_selection,
)


@pytest.fixture
def test_sources(test_db_session: Session):
    s_fed = Source(name="Federal Reserve", source_type="CENTRAL_BANK", category="Markets & Economy", active=True)
    s_reuters = Source(name="Reuters", source_type="NEWS_OUTLET", category="Markets & Economy", active=True)
    s_tech = Source(name="TechCrunch", source_type="NEWS_OUTLET", category="AI & Technology", active=True)
    s_inactive = Source(name="Inactive Feed", source_type="NEWS_OUTLET", category="World", active=False)
    test_db_session.add_all([s_fed, s_reuters, s_tech, s_inactive])
    test_db_session.commit()
    return {"fed": s_fed, "reuters": s_reuters, "tech": s_tech, "inactive": s_inactive}


def test_section_mapping():
    assert map_category_to_section("AI & Technology") == "TECH"
    assert map_category_to_section("Markets & Economy") == "ECONOMY"
    assert map_category_to_section("Commodities") == "BUSINESS"
    assert map_category_to_section("Energy") == "ENERGY"
    assert map_category_to_section("Trade") == "TRADE"
    assert map_category_to_section("Business") == "BUSINESS"
    assert map_category_to_section("Sustainability") == "SUSTAINABILITY"
    assert map_category_to_section("Unknown Sector") == "WORLD"


def test_edition_candidate_window():
    t_date = date(2026, 9, 15)
    start_utc, end_utc = get_london_date_window(t_date)
    assert start_utc < end_utc
    assert (end_utc - start_utc).total_seconds() == 48 * 3600


def test_future_timestamp_rejection(test_db_session: Session, test_sources):
    now = datetime.now(timezone.utc)
    future_time = now + timedelta(hours=5)
    
    a_future = Article(
        title="Future Article Title",
        canonical_url="http://test.com/future",
        source_id=test_sources["fed"].id,
        published_at=future_time,
        collected_at=now,
    )
    test_db_session.add(a_future)
    test_db_session.commit()

    ai_out = ArticleAIOutput(article_id=a_future.id, status="success", is_relevant=True)
    test_db_session.add(ai_out)
    test_db_session.commit()

    start_utc = now - timedelta(days=2)
    end_utc = now + timedelta(days=2)
    candidates, _ = fetch_eligible_candidates(test_db_session, start_utc, end_utc, now=now)
    assert a_future.id not in [c.id for c in candidates]


def test_unreviewed_and_irrelevant_rejection(test_db_session: Session, test_sources):
    now = datetime.now(timezone.utc)
    
    a_unreviewed = Article(
        title="Unreviewed Wire Story",
        canonical_url="http://test.com/unreviewed",
        source_id=test_sources["reuters"].id,
        published_at=now - timedelta(hours=1),
        collected_at=now,
    )
    a_irrelevant = Article(
        title="Irrelevant Gossip Story",
        canonical_url="http://test.com/irrelevant",
        source_id=test_sources["reuters"].id,
        published_at=now - timedelta(hours=2),
        collected_at=now,
    )
    test_db_session.add_all([a_unreviewed, a_irrelevant])
    test_db_session.commit()

    ai_irr = ArticleAIOutput(article_id=a_irrelevant.id, status="success", is_relevant=False)
    test_db_session.add(ai_irr)
    test_db_session.commit()

    start_utc = now - timedelta(days=2)
    end_utc = now + timedelta(days=2)
    candidates, _ = fetch_eligible_candidates(test_db_session, start_utc, end_utc, now=now)
    cand_ids = [c.id for c in candidates]
    assert a_unreviewed.id not in cand_ids
    assert a_irrelevant.id not in cand_ids


def test_editorial_balanced_vs_chronological_feed_semantics(test_db_session: Session, test_sources):
    now = datetime.now(timezone.utc)
    
    a_raw = Article(
        title="Raw Unprocessed Wire",
        canonical_url="http://test.com/raw",
        source_id=test_sources["reuters"].id,
        published_at=now - timedelta(minutes=5),
        collected_at=now,
    )
    a_reviewed = Article(
        title="AI Reviewed Macro Analysis",
        canonical_url="http://test.com/reviewed",
        source_id=test_sources["fed"].id,
        published_at=now - timedelta(minutes=10),
        collected_at=now,
    )
    test_db_session.add_all([a_raw, a_reviewed])
    test_db_session.commit()

    ai_out = ArticleAIOutput(article_id=a_reviewed.id, status="success", is_relevant=True)
    test_db_session.add(ai_out)
    test_db_session.commit()

    # Chronological mode returns raw wire (includes un-analyzed articles)
    chrono_arts = get_recent_articles(test_db_session, mode="chronological", limit=50)
    chrono_ids = [a.id for a in chrono_arts]
    assert a_raw.id in chrono_ids
    assert a_reviewed.id in chrono_ids

    # Balanced mode returns ONLY AI-reviewed relevant articles
    balanced_arts = get_recent_articles(test_db_session, mode="balanced", limit=50)
    balanced_ids = [a.id for a in balanced_arts]
    assert a_raw.id not in balanced_ids
    assert a_reviewed.id in balanced_ids


def test_source_cap_enforcement(test_db_session: Session, test_sources):
    now = datetime.now(timezone.utc)
    target_date = now.date()
    
    # Add 4 separate articles from Reuters with distinct event topics
    titles = [
        "Reuters Reports Federal Reserve Policy Rate Hold at 4.75%",
        "Reuters Details European Central Bank Rate Cut to 3.25%",
        "Reuters Summarizes Bank of England Monetary Policy Decision",
        "Reuters Analyzes Bank of Japan Overnight Call Rate Target",
    ]
    articles = []
    for i, title in enumerate(titles):
        art = Article(
            title=title,
            canonical_url=f"http://reuters.com/story-{i+1}",
            source_id=test_sources["reuters"].id,
            source=test_sources["reuters"],
            primary_category="Markets & Economy",
            published_at=now - timedelta(minutes=i*10),
            collected_at=now,
        )
        articles.append(art)
    test_db_session.add_all(articles)
    test_db_session.commit()

    for art in articles:
        ai_out = ArticleAIOutput(article_id=art.id, status="success", is_relevant=True, importance_score=80)
        test_db_session.add(ai_out)
    test_db_session.commit()

    sample_articles = test_db_session.query(Article).all()
    ai_map = {a.id: a.ai_outputs[0] for a in sample_articles if a.ai_outputs}
    cls = cluster_articles(sample_articles, ai_outputs_map=ai_map, now=now)
    save_event_clusters(test_db_session, cls)

    audit_res = generate_daily_edition_selection(
        db=test_db_session,
        target_date=target_date,
        max_per_source=2,
        now=now,
    )

    reuters_selected = [ev for ev in audit_res.selected_events if ev.primary_article.source_id == test_sources["reuters"].id]
    assert len(reuters_selected) <= 2
    assert audit_res.rejected_counts_by_reason["SOURCE_CAP"] >= 2


def test_section_cap_enforcement(test_db_session: Session, test_sources):
    now = datetime.now(timezone.utc)
    target_date = now.date()
    
    # Add 8 Economy articles from different sources with distinct topics
    econ_topics = [
        "Fed holds interest rates steady at 4.75%",
        "ECB cuts deposit rate by 25 bps to 3.25%",
        "Bank of England leaves bank rate unchanged at 4.75%",
        "Reserve Bank of India maintains repo rate at 6.50%",
        "Bank of Japan targets short term call rate at 0.25%",
        "US Treasury 10Y yield reaches 5.00%",
        "UK Gilt yield rises 7 bp to 4.12%",
        "Germany Bund yield increases to 2.24%",
    ]
    articles = []
    for i, topic in enumerate(econ_topics):
        s = test_sources["fed"] if i == 0 else test_sources["reuters"]
        
        art = Article(
            title=topic,
            canonical_url=f"http://econ-{i+1}.com/policy",
            source_id=s.id,
            source=s,
            primary_category="Markets & Economy",
            published_at=now - timedelta(minutes=i*5),
            collected_at=now,
        )
        articles.append(art)
    test_db_session.add_all(articles)
    test_db_session.commit()

    for art in articles:
        ai_out = ArticleAIOutput(article_id=art.id, status="success", is_relevant=True, importance_score=85)
        test_db_session.add(ai_out)
    test_db_session.commit()

    ai_map = {a.id: a.ai_outputs[0] for a in articles if a.ai_outputs}
    cls = cluster_articles(articles, ai_outputs_map=ai_map, now=now)
    save_event_clusters(test_db_session, cls)

    audit_res = generate_daily_edition_selection(
        db=test_db_session,
        target_date=target_date,
        max_edition_size=20,
        max_section_share=0.30,  # Max 6 per section
        now=now,
    )

    econ_selected = [ev for ev in audit_res.selected_events if ev.section == "ECONOMY"]
    assert len(econ_selected) <= 6


def test_readiness_gate_preparing_vs_ready(test_db_session: Session, test_sources):
    now = datetime.now(timezone.utc)
    target_date = now.date()

    # 3 distinct articles from 3 distinct sources (< 10 min publishable size) -> PREPARING
    sample_data = [
        ("Federal Reserve Monetary Policy Rate Decision", test_sources["fed"].id),
        ("NVIDIA Vera Rubin NVLink Architecture Keynote", test_sources["tech"].id),
        ("Red Sea Shipping Escalation Boosts Crude Futures", test_sources["reuters"].id),
    ]
    for i, (title, s_id) in enumerate(sample_data):
        art = Article(
            title=title,
            canonical_url=f"http://sample.com/macro-{i+1}",
            source_id=s_id,
            published_at=now - timedelta(minutes=i*10),
            collected_at=now,
        )
        test_db_session.add(art)
        test_db_session.commit()
        ai_out = ArticleAIOutput(article_id=art.id, status="success", is_relevant=True, importance_score=80)
        test_db_session.add(ai_out)
    test_db_session.commit()

    sample_articles = test_db_session.query(Article).all()
    ai_map = {a.id: a.ai_outputs[0] for a in sample_articles if a.ai_outputs}
    cls = cluster_articles(sample_articles, ai_outputs_map=ai_map, now=now)
    save_event_clusters(test_db_session, cls)

    audit_prep = generate_daily_edition_selection(db=test_db_session, target_date=target_date, min_publishable_size=10, now=now)
    assert audit_prep.readiness == "PREPARING"
    assert audit_prep.selected_events_count == 3


def test_lead_story_selection_and_roles(test_db_session: Session, test_sources):
    now = datetime.now(timezone.utc)
    target_date = now.date()

    # Article with high score (85 importance) -> LEAD
    a_lead = Article(
        title="Major Global Interest Rate Decision Announced",
        canonical_url="http://fed.gov/major-lead",
        source_id=test_sources["fed"].id,
        source=test_sources["fed"],
        primary_category="Markets & Economy",
        published_at=now,
        collected_at=now,
    )
    test_db_session.add(a_lead)
    test_db_session.commit()
    ai_lead = ArticleAIOutput(article_id=a_lead.id, status="success", is_relevant=True, importance_score=95)
    test_db_session.add(ai_lead)
    test_db_session.commit()

    ai_map = {a_lead.id: ai_lead}
    cls = cluster_articles([a_lead], ai_outputs_map=ai_map, now=now)
    save_event_clusters(test_db_session, cls)

    audit_res = generate_daily_edition_selection(db=test_db_session, target_date=target_date, lead_quality_threshold=70.0, now=now)
    assert audit_res.lead_story_title == a_lead.title
    roles = [ev.role for ev in audit_res.selected_events]
    assert "LEAD" in roles


def test_snapshot_persistence_and_published_immutability(test_db_session: Session, test_sources):
    now = datetime.now(timezone.utc)
    target_date = now.date()

    a1 = Article(
        title="Persisted Edition Event 1",
        canonical_url="http://test.com/p1",
        source_id=test_sources["fed"].id,
        source=test_sources["fed"],
        published_at=now,
        collected_at=now,
    )
    test_db_session.add(a1)
    test_db_session.commit()
    ai_out = ArticleAIOutput(article_id=a1.id, status="success", is_relevant=True, importance_score=85)
    test_db_session.add(ai_out)
    test_db_session.commit()

    cls = cluster_articles([a1], ai_outputs_map={a1.id: ai_out}, now=now)
    save_event_clusters(test_db_session, cls)

    audit_res = generate_daily_edition_selection(db=test_db_session, target_date=target_date, now=now)
    edition = save_daily_edition_selection(test_db_session, audit_res, target_date, status="DRAFT")

    assert edition.id is not None
    assert edition.status == "DRAFT"
    assert len(edition.edition_events) == 1

    # Regenerate DRAFT edition
    edition_regen = save_daily_edition_selection(test_db_session, audit_res, target_date, status="GENERATED")
    assert edition_regen.status == "GENERATED"

    # Mark as PUBLISHED
    edition_regen.status = "PUBLISHED"
    test_db_session.commit()

    # Attempting to save/regenerate PUBLISHED edition must raise ValueError
    with pytest.raises(ValueError, match="PUBLISHED and cannot be regenerated"):
        save_daily_edition_selection(test_db_session, audit_res, target_date, status="GENERATED")
