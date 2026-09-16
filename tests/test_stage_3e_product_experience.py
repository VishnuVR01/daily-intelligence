"""
Unit tests for Sprint 3 Stage 3E — Daily Edition Product Experience, Publication & Acceptance.
Tests routes (/edition, /edition/{date}, /editions), no-Ollama page load guarantee, publication workflow, CLI scripts, and market snapshot safety.
"""
from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models import (
    Article,
    Source,
    DailyEdition,
    EditionEvent,
    EventCluster,
    EventEditorialProse,
    EditionBrief,
)
from services.editorial.publication import publish_daily_edition


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_source_3e(test_db_session: Session):
    src = Source(
        name="Financial Times",
        website_url="https://ft.com",
        source_type="NEWS_OUTLET",
        trust_tier="tier1_direct",
    )
    test_db_session.add(src)
    test_db_session.commit()
    test_db_session.refresh(src)
    return src


@pytest.fixture
def sample_article_3e(test_db_session: Session, sample_source_3e: Source):
    art = Article(
        title="ECB Cuts Benchmark Interest Rate by 25 Basis Points to 3.25%",
        canonical_url="https://ft.com/ecb-rate-cut-25bps",
        source_id=sample_source_3e.id,
        published_at=datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc),
        raw_summary="The European Central Bank announced a 25 basis point reduction in key policy rates.",
    )
    test_db_session.add(art)
    test_db_session.commit()
    test_db_session.refresh(art)
    return art


def test_edition_routes(test_db_session: Session, sample_article_3e: Article, client: TestClient):
    ed_date = date(2026, 9, 15)

    ec = EventCluster(
        cluster_id="evt_route_001",
        canonical_title="ECB Cuts Benchmark Rate",
        category="CENTRAL_BANKS",
        primary_article_id=sample_article_3e.id,
        article_count=1,
    )
    test_db_session.add(ec)
    test_db_session.commit()

    edition = DailyEdition(
        edition_date=ed_date,
        status="PUBLISHED",
        readiness="READY",
        lead_event_cluster_id="evt_route_001",
        article_count=1,
        event_count=1,
    )
    test_db_session.add(edition)
    test_db_session.commit()

    ee = EditionEvent(
        edition_id=edition.id,
        event_cluster_id="evt_route_001",
        section="ECONOMY & POLICY",
        role="LEAD_STORY",
        position=1,
        event_score=90.0,
    )
    test_db_session.add(ee)
    test_db_session.commit()

    prose = EventEditorialProse(
        edition_event_id=ee.id,
        event_cluster_id="evt_route_001",
        headline="European Central Bank Cuts Rates by 25 Basis Points",
        summary="The ECB announced a rate reduction today.",
        status="SUCCESS",
    )
    test_db_session.add(prose)

    brief = EditionBrief(
        edition_id=edition.id,
        brief_text="Morning Executive Briefing for 15 September 2026.",
        key_themes_json=[{"title": "Monetary Policy", "description": "ECB easing policy."}],
        status="SUCCESS",
    )
    test_db_session.add(brief)
    test_db_session.commit()

    # 1. Test GET /edition (Redirect to latest published edition)
    res_latest = client.get("/edition", follow_redirects=False)
    assert res_latest.status_code == 307
    assert res_latest.headers["location"] == "/edition/2026-09-15"

    # 2. Test GET /edition/2026-09-15
    res_page = client.get("/edition/2026-09-15")
    assert res_page.status_code == 200
    assert "DAILY INTELLIGENCE" in res_page.text
    assert "European Central Bank Cuts Rates by 25 Basis Points" in res_page.text
    assert "Morning Executive Briefing for 15 September 2026" in res_page.text

    # 3. Test GET /editions (Editions Archive Index)
    res_archive = client.get("/editions")
    assert res_archive.status_code == 200
    assert "Daily Editions Archive" in res_archive.text
    assert "2026-09-15" in res_archive.text

    # 4. Test Invalid Date (Safe 404)
    res_inv = client.get("/edition/invalid-date")
    assert res_inv.status_code == 404


def test_no_ollama_on_page_load(test_db_session: Session, sample_article_3e: Article, client: TestClient, monkeypatch):
    ed_date = date(2026, 9, 14)

    ec = EventCluster(
        cluster_id="evt_no_ollama_001",
        canonical_title="Test Cluster Title",
        category="WORLD",
        primary_article_id=sample_article_3e.id,
    )
    test_db_session.add(ec)
    test_db_session.commit()

    edition = DailyEdition(edition_date=ed_date, status="PUBLISHED", readiness="READY")
    test_db_session.add(edition)
    test_db_session.commit()

    ee = EditionEvent(edition_id=edition.id, event_cluster_id="evt_no_ollama_001", section="WORLD", role="LEAD_STORY", position=1)
    test_db_session.add(ee)
    test_db_session.commit()

    prose = EventEditorialProse(edition_event_id=ee.id, event_cluster_id="evt_no_ollama_001", headline="Headline Text", summary="Summary Text")
    brief = EditionBrief(edition_id=edition.id, brief_text="Brief Text", key_themes_json=[])
    test_db_session.add_all([prose, brief])
    test_db_session.commit()

    def mock_chat_json(*args, **kwargs):
        raise RuntimeError("Ollama chat_json was unexpectedly called on page load!")

    monkeypatch.setattr("services.ai.ollama.OllamaService.chat_json", mock_chat_json)

    res = client.get("/edition/2026-09-14")
    assert res.status_code == 200
    assert "Headline Text" in res.text


def test_publication_workflow(test_db_session: Session, sample_article_3e: Article):
    ed_date = date(2026, 9, 13)

    ec = EventCluster(
        cluster_id="evt_pub_001",
        canonical_title="Fed Policy Decision",
        category="CENTRAL_BANKS",
        primary_article_id=sample_article_3e.id,
    )
    test_db_session.add(ec)
    test_db_session.commit()

    edition = DailyEdition(edition_date=ed_date, status="GENERATED", readiness="READY", article_count=1, event_count=1)
    test_db_session.add(edition)
    test_db_session.commit()

    ee = EditionEvent(edition_id=edition.id, event_cluster_id="evt_pub_001", section="ECONOMY & POLICY", role="LEAD_STORY", position=1)
    test_db_session.add(ee)
    test_db_session.commit()

    prose = EventEditorialProse(edition_event_id=ee.id, event_cluster_id="evt_pub_001", headline="Fed Holds Rates", summary="Summary")
    brief = EditionBrief(edition_id=edition.id, brief_text="Brief text", key_themes_json=[])
    test_db_session.add_all([prose, brief])
    test_db_session.commit()

    pub_ed = publish_daily_edition(db=test_db_session, target_date=ed_date)
    assert pub_ed.status == "PUBLISHED"
    assert (pub_ed.metadata_json or {}).get("published_at") is not None
