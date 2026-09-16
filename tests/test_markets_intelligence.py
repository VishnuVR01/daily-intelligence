import asyncio
from datetime import datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Article, ArticleAIOutput, Country, Source
from services.markets.models import MarketSnapshot, create_market_snapshot
from services.markets.sessions import get_market_session_status
from services.markets.intelligence import (
    calculate_article_market_affinity,
    classify_causality_relationship,
    generate_market_takeaways,
    get_market_intelligence,
)


# ---------------------------------------------------------------------------
# Session Engine Tests
# ---------------------------------------------------------------------------

def test_session_status_open_during_trading_hours():
    # US market: Mon 14:00 UTC (09:00 EST -> 10:00 EDT) -> OPEN
    mon_open = datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc)
    status = get_market_session_status("United States", at_time=mon_open)
    assert status.state == "OPEN"
    assert status.dot_class == "open"


def test_session_status_closed_outside_trading_hours():
    # US market: Mon 02:00 UTC -> CLOSED
    mon_night = datetime(2026, 9, 14, 2, 0, tzinfo=timezone.utc)
    status = get_market_session_status("United States", at_time=mon_night)
    assert status.state == "CLOSED"
    assert status.dot_class == "closed"


def test_session_status_weekend():
    # Sat Sep 19, 2026 -> CLOSED for all markets
    sat = datetime(2026, 9, 19, 14, 0, tzinfo=timezone.utc)
    for region in ["United States", "United Kingdom", "India", "Japan", "Europe", "China"]:
        status = get_market_session_status(region, at_time=sat)
        assert status.state == "CLOSED"
        assert status.dot_class == "closed"


def test_session_timezone_correctness():
    # UK market: Mon 10:00 UTC -> OPEN (LSE RTH: 08:00 - 16:30 BST)
    dt = datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc)
    status = get_market_session_status("United Kingdom", at_time=dt)
    assert status.state == "OPEN"
    assert status.exchange_tz == "Europe/London"


# ---------------------------------------------------------------------------
# Market Affinity & Causality Tests
# ---------------------------------------------------------------------------

def test_us_market_affinity(test_db_session):
    art = Article(
        title="Fed Signals Interest Rate Cut Amid Wall Street Rally",
        raw_summary="Federal Reserve Chair comments on inflation and US equities.",
        canonical_url="https://news.org/us-fed-1",
        published_at=datetime.now(timezone.utc),
    )
    test_db_session.add(art)
    test_db_session.commit()

    match = calculate_article_market_affinity(art, "United States")
    assert match is not None
    assert match.affinity_score > 0
    assert any("fed" in r.lower() or "wall street" in r.lower() for r in match.reasons)


def test_uk_market_affinity(test_db_session):
    art = Article(
        title="Bank of England Keeps Rates Unchanged as FTSE Gains",
        raw_summary="UK economy metrics and Sterling movement.",
        canonical_url="https://news.org/uk-boe-1",
        published_at=datetime.now(timezone.utc),
    )
    test_db_session.add(art)
    test_db_session.commit()

    match = calculate_article_market_affinity(art, "United Kingdom")
    assert match is not None
    assert match.affinity_score > 0


def test_india_market_affinity(test_db_session):
    art = Article(
        title="RBI Policy Outlook Boosts NIFTY 50 and Sensex",
        raw_summary="Reserve Bank of India announces economic metrics.",
        canonical_url="https://news.org/in-rbi-1",
        published_at=datetime.now(timezone.utc),
    )
    test_db_session.add(art)
    test_db_session.commit()

    match = calculate_article_market_affinity(art, "India")
    assert match is not None
    assert match.affinity_score > 0


def test_japan_market_affinity(test_db_session):
    art = Article(
        title="BOJ Rate Strategy Shift Impact on Nikkei 225",
        raw_summary="Bank of Japan policy discussions and Yen movement.",
        canonical_url="https://news.org/jp-boj-1",
        published_at=datetime.now(timezone.utc),
    )
    test_db_session.add(art)
    test_db_session.commit()

    match = calculate_article_market_affinity(art, "Japan")
    assert match is not None
    assert match.affinity_score > 0


def test_europe_market_affinity(test_db_session):
    art = Article(
        title="ECB Rate Decisions Drive STOXX Europe 600 Gains",
        raw_summary="Eurozone economic trends and European central bank policy.",
        canonical_url="https://news.org/eu-ecb-1",
        published_at=datetime.now(timezone.utc),
    )
    test_db_session.add(art)
    test_db_session.commit()

    match = calculate_article_market_affinity(art, "Europe")
    assert match is not None
    assert match.affinity_score > 0


def test_china_market_affinity(test_db_session):
    art = Article(
        title="PBOC Stimulus Measures Support CSI 300 Rally",
        raw_summary="People's Bank of China economic policies.",
        canonical_url="https://news.org/cn-pboc-1",
        published_at=datetime.now(timezone.utc),
    )
    test_db_session.add(art)
    test_db_session.commit()

    match = calculate_article_market_affinity(art, "China")
    assert match is not None
    assert match.affinity_score > 0


def test_explicit_market_moving_causality_classification():
    text = "Tech stocks fell after new regulatory guidance was issued by regulators."
    rel, reasons = classify_causality_relationship(text)
    assert rel == "MARKET_MOVING"
    assert len(reasons) > 0


def test_contextual_article_classified_related():
    text = "Overview of Semiconductor Supply Chain Investments in 2026."
    rel, reasons = classify_causality_relationship(text)
    assert rel == "RELATED"


def test_related_never_promoted_without_evidence():
    art = Article(
        title="General Economic Overview of European Manufacturing",
        raw_summary="Contextual background on manufacturing output.",
        canonical_url="https://news.org/eu-mfg-1",
        published_at=datetime.now(timezone.utc),
    )
    match = calculate_article_market_affinity(art, "Europe")
    assert match is not None
    assert match.relationship == "RELATED"


def test_recency_ranking_precedence(test_db_session):
    now = datetime.now(timezone.utc)
    art_recent = Article(
        title="US Stocks Fell After Fed Announcement",
        canonical_url="https://news.org/us-recent",
        published_at=now - timedelta(hours=1),
    )
    art_older = Article(
        title="US Stocks Fell After Trade Speech",
        canonical_url="https://news.org/us-older",
        published_at=now - timedelta(hours=36),
    )
    test_db_session.add_all([art_recent, art_older])
    test_db_session.commit()

    intel = get_market_intelligence(test_db_session, selected_region="United States", hours_window=48)
    assert intel["featured_story"] is not None
    assert intel["featured_story"].article.id == art_recent.id


def test_importance_score_affects_ranking(test_db_session):
    now = datetime.now(timezone.utc)
    art_low_imp = Article(
        title="US Market Briefing",
        canonical_url="https://news.org/low-imp",
        published_at=now,
    )
    art_high_imp = Article(
        title="US Market Crisis Response",
        canonical_url="https://news.org/high-imp",
        published_at=now,
    )
    test_db_session.add_all([art_low_imp, art_high_imp])
    test_db_session.commit()

    ai_low = ArticleAIOutput(article_id=art_low_imp.id, importance_score=3, relevance_score=5, primary_category="Markets")
    ai_high = ArticleAIOutput(article_id=art_high_imp.id, importance_score=9, relevance_score=5, primary_category="Markets")
    test_db_session.add_all([ai_low, ai_high])
    test_db_session.commit()

    intel = get_market_intelligence(test_db_session, selected_region="United States", hours_window=48)
    assert intel["featured_story"] is not None
    assert intel["featured_story"].article.id == art_high_imp.id


def test_featured_story_selection(test_db_session):
    now = datetime.now(timezone.utc)
    art_moving = Article(
        title="US Stocks Surged Following Jobs Report",
        raw_summary="Wall street rallied as employment numbers exceeded forecasts.",
        canonical_url="https://news.org/moving-1",
        published_at=now,
    )
    test_db_session.add(art_moving)
    test_db_session.commit()

    intel = get_market_intelligence(test_db_session, selected_region="United States")
    assert intel["featured_story"] is not None
    assert intel["featured_story"].relationship == "MARKET_MOVING"


def test_no_story_fallback_messaging(test_db_session):
    # Empty DB
    intel = get_market_intelligence(test_db_session, selected_region="United States")
    assert intel["featured_story"] is None
    assert intel["selected_matches_count"] == 0


def test_low_coverage_wording():
    snapshots = [
        create_market_snapshot("United States", "SPX", "S&P 500", 5500.0, 5600.0, "2026-09-15"),
        create_market_snapshot("United Kingdom", "FTSE", "FTSE 100", 8200.0, 8300.0, "2026-09-15"),
        create_market_snapshot("India", "NSEI", "NIFTY 50", 24000.0, 24500.0, "2026-09-15"),
    ]
    takeaways = generate_market_takeaways(snapshots, "United States", matched_count=0)
    assert len(takeaways) == 3
    assert "Among currently processed intelligence" in takeaways[2]["text"]


# ---------------------------------------------------------------------------
# Integration & UI Route Tests
# ---------------------------------------------------------------------------

def test_homepage_session_status_rendering(test_db_session):
    sample_snapshot = create_market_snapshot(
        region="United States",
        symbol="SPX",
        display_name="S&P 500",
        latest_close=5550.0,
        previous_close=5500.0,
        market_date="2026-09-15",
        currency="USD",
    )

    mock_service = AsyncMock()
    mock_service.get_global_markets.return_value = ([sample_snapshot], False)

    with patch("app.main.get_market_service", return_value=mock_service):
        client = TestClient(app)
        response = client.get("/")

    assert response.status_code == 200
    assert "Global Markets" in response.text
    assert 'href="/markets"' in response.text


def test_markets_route_rendering(test_db_session):
    sample_snapshot = create_market_snapshot(
        region="United States",
        symbol="SPX",
        display_name="S&P 500",
        latest_close=5550.0,
        previous_close=5500.0,
        market_date="2026-09-15",
        currency="USD",
    )

    mock_service = AsyncMock()
    mock_service.get_global_markets.return_value = ([sample_snapshot], False)
    mock_service.get_historical_series.return_value = None

    with patch("app.main.get_market_service", return_value=mock_service):
        client = TestClient(app)
        response = client.get("/markets")

    assert response.status_code == 200
    assert "GLOBAL MARKETS INTELLIGENCE" in response.text
    assert "GLOBAL MARKET PULSE" in response.text
    assert "MARKET FOCUS" in response.text
    assert "KEY TAKEAWAYS" in response.text


def test_all_six_markets_selectable(test_db_session):
    mock_service = AsyncMock()
    mock_service.get_global_markets.return_value = ([], False)
    mock_service.get_historical_series.return_value = None

    with patch("app.main.get_market_service", return_value=mock_service):
        client = TestClient(app)
        for m_slug in ["us", "uk", "india", "japan", "europe", "china"]:
            resp = client.get(f"/markets?market={m_slug}")
            assert resp.status_code == 200


def test_invalid_market_parameter_fallback(test_db_session):
    mock_service = AsyncMock()
    mock_service.get_global_markets.return_value = ([], False)
    mock_service.get_historical_series.return_value = None

    with patch("app.main.get_market_service", return_value=mock_service):
        client = TestClient(app)
        resp = client.get("/markets?market=invalid-market-name")
        assert resp.status_code == 200
        assert "United States" in resp.text


def test_market_api_failure_does_not_break_markets_page(test_db_session):
    mock_service = AsyncMock()
    mock_service.get_global_markets.return_value = ([], False)
    mock_service.get_historical_series.return_value = None

    with patch("app.main.get_market_service", return_value=mock_service):
        client = TestClient(app)
        response = client.get("/markets")

    assert response.status_code == 200
    assert "Market Data Temporarily Unavailable" in response.text


def test_six_dropdown_options_rendered(test_db_session):
    """Verify all six tracked markets are present in the dropdown selector."""
    sample_snapshot = create_market_snapshot(
        region="United States",
        symbol="SPX",
        display_name="S&P 500",
        latest_close=5550.0,
        previous_close=5500.0,
        market_date="2026-09-15",
        currency="USD",
    )

    mock_service = AsyncMock()
    mock_service.get_global_markets.return_value = ([sample_snapshot], False)
    mock_service.get_historical_series.return_value = None

    with patch("app.main.get_market_service", return_value=mock_service):
        client = TestClient(app)
        response = client.get("/markets")

    assert response.status_code == 200
    html = response.text

    assert 'id="market-focus-select"' in html
    assert 'value="us"' in html
    assert 'value="uk"' in html
    assert 'value="india"' in html
    assert 'value="japan"' in html
    assert 'value="europe"' in html
    assert 'value="china"' in html


def test_dropdown_accessibility_attributes(test_db_session):
    """Verify select element contains appropriate accessibility labels."""
    sample_snapshot = create_market_snapshot(
        region="United States",
        symbol="SPX",
        display_name="S&P 500",
        latest_close=5550.0,
        previous_close=5500.0,
        market_date="2026-09-15",
        currency="USD",
    )

    mock_service = AsyncMock()
    mock_service.get_global_markets.return_value = ([sample_snapshot], False)
    mock_service.get_historical_series.return_value = None

    with patch("app.main.get_market_service", return_value=mock_service):
        client = TestClient(app)
        response = client.get("/markets")

    assert response.status_code == 200
    assert 'aria-label="Select market focus region"' in response.text


def test_selected_market_metadata_rendered(test_db_session):
    """Verify selecting a market updates snapshot metadata presentation."""
    sample_snapshot = create_market_snapshot(
        region="Japan",
        symbol="N225",
        display_name="Nikkei 225",
        latest_close=36000.0,
        previous_close=35500.0,
        market_date="2026-09-15",
        currency="JPY",
    )

    mock_service = AsyncMock()
    mock_service.get_global_markets.return_value = ([sample_snapshot], False)
    mock_service.get_historical_series.return_value = None

    with patch("app.main.get_market_service", return_value=mock_service):
        client = TestClient(app)
        response = client.get("/markets?market=japan")

    assert response.status_code == 200
    assert "Nikkei 225" in response.text
    assert "36,000.00" in response.text
    assert "JPY" in response.text

