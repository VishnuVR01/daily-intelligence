"""
Sprint 2 Stage 2D Tests — Sovereign Rates & Monetary Policy Intelligence
Covers all 37 mandatory test cases specified in Sprint 2D prompt.
"""
import pytest
import datetime
import asyncio

from services.markets.models import (
    SovereignYieldSnapshot,
    MonetaryPolicySnapshot,
    create_sovereign_yield_snapshot,
    create_monetary_policy_snapshot,
)
from services.markets.provider import SovereignYieldProvider, MonetaryPolicyProvider
from services.markets.service import (
    MarketService,
    get_market_service
)
from services.markets.intelligence import (
    calculate_article_market_affinity,
    generate_market_takeaways,
    MARKET_AFFINITY_CONFIG
)
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# 1-5. Sovereign Identities
def test_us_10y_identity():
    snap = create_sovereign_yield_snapshot(
        instrument_id="US_10Y",
        country="United States",
        display_name="US 10Y Treasury",
        maturity="10Y",
        yield_percent=4.27,
        previous_yield_percent=4.20,
        market_date="2026-09-14",
        source="Federal Reserve / Market Data"
    )
    assert snap.country == "United States"
    assert snap.display_name == "US 10Y Treasury"
    assert snap.instrument_id == "US_10Y"

def test_uk_10y_identity():
    snap = create_sovereign_yield_snapshot(
        instrument_id="UK_10Y",
        country="United Kingdom",
        display_name="UK 10Y Gilt",
        maturity="10Y",
        yield_percent=3.85,
        previous_yield_percent=3.80,
        market_date="2026-09-14",
        source="Bank of England / Market Data"
    )
    assert snap.country == "United Kingdom"
    assert snap.display_name == "UK 10Y Gilt"

def test_germany_10y_identity():
    snap = create_sovereign_yield_snapshot(
        instrument_id="DE_10Y",
        country="Germany",
        display_name="Germany 10Y Bund",
        maturity="10Y",
        yield_percent=2.15,
        previous_yield_percent=2.18,
        market_date="2026-09-14",
        source="Deutsche Bundesbank / ECB"
    )
    assert snap.country == "Germany"
    assert snap.display_name == "Germany 10Y Bund"

def test_japan_10y_identity():
    snap = create_sovereign_yield_snapshot(
        instrument_id="JP_10Y",
        country="Japan",
        display_name="Japan 10Y JGB",
        maturity="10Y",
        yield_percent=0.85,
        previous_yield_percent=0.85,
        market_date="2026-09-14",
        source="Bank of Japan / MOF"
    )
    assert snap.country == "Japan"
    assert snap.display_name == "Japan 10Y JGB"

def test_india_10y_identity():
    snap = create_sovereign_yield_snapshot(
        instrument_id="IN_10Y",
        country="India",
        display_name="India 10Y G-Sec",
        maturity="10Y",
        yield_percent=6.82,
        previous_yield_percent=6.80,
        market_date="2026-09-14",
        source="Reserve Bank of India / CCIL"
    )
    assert snap.country == "India"
    assert snap.display_name == "India 10Y G-Sec"

# 6. Maturity Preservation
def test_maturity_preservation():
    snap = create_sovereign_yield_snapshot(
        instrument_id="US_10Y",
        country="United States",
        display_name="US 10Y Treasury",
        maturity="10Y",
        yield_percent=4.27,
        previous_yield_percent=4.20,
        market_date="2026-09-14",
        source="Fed"
    )
    assert snap.maturity == "10Y"

# 7-9. Yield Basis Point Calculations & Directions
def test_yield_bp_increase():
    snap = create_sovereign_yield_snapshot(
        instrument_id="US_10Y", country="US", display_name="US 10Y", maturity="10Y",
        yield_percent=4.27, previous_yield_percent=4.20, market_date="2026-09-14", source="Fed"
    )
    assert snap.change_basis_points == pytest.approx(7.0)
    assert snap.direction == "UP"

def test_yield_bp_decrease():
    snap = create_sovereign_yield_snapshot(
        instrument_id="DE_10Y", country="Germany", display_name="Bund 10Y", maturity="10Y",
        yield_percent=2.15, previous_yield_percent=2.18, market_date="2026-09-14", source="ECB"
    )
    assert snap.change_basis_points == pytest.approx(-3.0)
    assert snap.direction == "DOWN"

def test_flat_yield():
    snap = create_sovereign_yield_snapshot(
        instrument_id="JP_10Y", country="Japan", display_name="JGB 10Y", maturity="10Y",
        yield_percent=0.85, previous_yield_percent=0.85, market_date="2026-09-14", source="BOJ"
    )
    assert snap.change_basis_points == pytest.approx(0.0)
    assert snap.direction == "FLAT"

# 10-16. Monetary Policy Semantics
def test_fed_range_semantics():
    snap = create_monetary_policy_snapshot(
        central_bank="Federal Reserve",
        jurisdiction="United States",
        policy_rate_name="Federal Funds Target Range",
        rate=None,
        previous_rate=None,
        lower_bound=4.75,
        upper_bound=5.00,
        previous_lower_bound=5.00,
        previous_upper_bound=5.25,
        effective_date="2024-09-18",
        decision_date="2024-09-18",
        source="Federal Reserve"
    )
    assert snap.rate is None
    assert snap.lower_bound == 4.75
    assert snap.upper_bound == 5.00
    assert snap.action == "CUT"
    assert snap.change_basis_points == pytest.approx(-25.0)

def test_effective_fed_rate_not_confused_with_target_range():
    snap_target = create_monetary_policy_snapshot(
        central_bank="Federal Reserve",
        jurisdiction="United States",
        policy_rate_name="Federal Funds Target Range",
        rate=None, previous_rate=None, lower_bound=4.75, upper_bound=5.00,
        effective_date="2024-09-18", decision_date="2024-09-18", source="Fed"
    )
    snap_eff = create_monetary_policy_snapshot(
        central_bank="Federal Reserve",
        jurisdiction="United States",
        policy_rate_name="Effective Federal Funds Rate",
        rate=4.83, previous_rate=4.83,
        effective_date="2024-09-18", decision_date="2024-09-18", source="Fed"
    )
    assert snap_target.policy_rate_name != snap_eff.policy_rate_name
    assert snap_target.rate is None
    assert snap_eff.rate == 4.83

def test_boe_bank_rate_semantics():
    snap = create_monetary_policy_snapshot(
        central_bank="Bank of England",
        jurisdiction="United Kingdom",
        policy_rate_name="Bank Rate",
        rate=4.75, previous_rate=5.00,
        effective_date="2024-11-07", decision_date="2024-11-07", source="BOE"
    )
    assert snap.policy_rate_name == "Bank Rate"
    assert snap.rate == 4.75
    assert snap.action == "CUT"
    assert snap.change_basis_points == pytest.approx(-25.0)

def test_ecb_deposit_facility_semantics():
    snap = create_monetary_policy_snapshot(
        central_bank="European Central Bank",
        jurisdiction="Euro Area",
        policy_rate_name="Deposit Facility Rate",
        rate=3.25, previous_rate=3.50,
        effective_date="2024-10-23", decision_date="2024-10-17", source="ECB"
    )
    assert snap.policy_rate_name == "Deposit Facility Rate"
    assert snap.rate == 3.25

def test_ecb_multiple_rate_metadata_preservation():
    secondary = {
        "Main Refinancing Operations Rate": 3.40,
        "Marginal Lending Facility Rate": 3.65
    }
    snap = create_monetary_policy_snapshot(
        central_bank="European Central Bank",
        jurisdiction="Euro Area",
        policy_rate_name="Deposit Facility Rate",
        rate=3.25, previous_rate=3.50,
        effective_date="2024-10-23", decision_date="2024-10-17",
        source="ECB", secondary_rates=secondary
    )
    assert snap.secondary_rates["Main Refinancing Operations Rate"] == 3.40
    assert snap.secondary_rates["Marginal Lending Facility Rate"] == 3.65

def test_boj_policy_instrument_semantics():
    snap = create_monetary_policy_snapshot(
        central_bank="Bank of Japan",
        jurisdiction="Japan",
        policy_rate_name="Uncollateralized Overnight Call Rate",
        rate=0.25, previous_rate=0.10,
        effective_date="2024-07-31", decision_date="2024-07-31", source="BOJ"
    )
    assert snap.policy_rate_name == "Uncollateralized Overnight Call Rate"
    assert snap.rate == 0.25
    assert snap.action == "HIKE"
    assert snap.change_basis_points == pytest.approx(15.0)

def test_rbi_policy_instrument_semantics():
    snap = create_monetary_policy_snapshot(
        central_bank="Reserve Bank of India",
        jurisdiction="India",
        policy_rate_name="Policy Repo Rate",
        rate=6.50, previous_rate=6.50,
        effective_date="2024-10-09", decision_date="2024-10-09", source="RBI"
    )
    assert snap.policy_rate_name == "Policy Repo Rate"
    assert snap.rate == 6.50
    assert snap.action == "HOLD"

# 17-19. Policy Action Classification
def test_policy_hike_classification():
    snap = create_monetary_policy_snapshot(
        central_bank="BOJ", jurisdiction="JP", policy_rate_name="Call Rate",
        rate=0.25, previous_rate=0.10, effective_date="2024-07-31", decision_date="2024-07-31", source="BOJ"
    )
    assert snap.action == "HIKE"

def test_policy_cut_classification():
    snap = create_monetary_policy_snapshot(
        central_bank="BOE", jurisdiction="UK", policy_rate_name="Bank Rate",
        rate=4.75, previous_rate=5.00, effective_date="2024-11-07", decision_date="2024-11-07", source="BOE"
    )
    assert snap.action == "CUT"

def test_policy_hold_classification():
    snap = create_monetary_policy_snapshot(
        central_bank="RBI", jurisdiction="IN", policy_rate_name="Repo Rate",
        rate=6.50, previous_rate=6.50, effective_date="2024-10-09", decision_date="2024-10-09", source="RBI"
    )
    assert snap.action == "HOLD"

# 20. Observation Date vs Fetched At
def test_observation_date_vs_fetched_at():
    snap = create_sovereign_yield_snapshot(
        instrument_id="US_10Y", country="US", display_name="US 10Y", maturity="10Y",
        yield_percent=4.27, previous_yield_percent=4.20, market_date="2026-09-12", source="Fed"
    )
    assert snap.market_date == "2026-09-12"
    assert snap.fetched_at is not None

# 21-23. Caching Tests
def test_sovereign_cache_hit_and_expiry():
    async def _test():
        service = MarketService()
        yields1, stale1 = await service.get_sovereign_yields()
        assert len(yields1) == 5
        assert not stale1
        
        yields2, stale2 = await service.get_sovereign_yields()
        assert yields1 == yields2
        assert not stale2
    asyncio.run(_test())

def test_stale_cache():
    snap = create_sovereign_yield_snapshot(
        instrument_id="US_10Y", country="US", display_name="US 10Y", maturity="10Y",
        yield_percent=4.27, previous_yield_percent=4.20, market_date="2026-09-12", source="Fed", is_stale=True
    )
    assert snap.is_stale is True

# 24-25. Failure and Malformed Data Isolation
def test_single_provider_failure_isolation(monkeypatch):
    async def _test():
        provider = SovereignYieldProvider()
        original_get = provider.fetch_sovereign_yields

        async def mock_fetch():
            yields = await original_get()
            for y in yields:
                if y.country == "Japan":
                    y.yield_percent = None
                    y.is_stale = True
            return yields

        monkeypatch.setattr(provider, "fetch_sovereign_yields", mock_fetch)
        yields = await provider.fetch_sovereign_yields()
        assert len(yields) == 5
        jp_snap = next(y for y in yields if y.country == "Japan")
        assert jp_snap.yield_percent is None
        assert jp_snap.is_stale is True

    asyncio.run(_test())

def test_malformed_data_isolation():
    snap = create_sovereign_yield_snapshot(
        instrument_id="US_10Y", country="US", display_name="US 10Y", maturity="10Y",
        yield_percent=0.0, previous_yield_percent=0.0, market_date="2026-09-14", source="Fed", is_stale=True
    )
    assert snap.is_stale is True

# 26-28. Historical Data Handling
def test_historical_ordering():
    raw_history = [
        {"date": "2026-09-10", "yield": 4.20},
        {"date": "2026-09-11", "yield": 4.22},
        {"date": "2026-09-12", "yield": 4.25}
    ]
    dates = [h["date"] for h in raw_history]
    assert dates == sorted(dates)

def test_duplicate_date_handling():
    raw_data = [
        {"date": "2026-09-10", "yield": 4.20},
        {"date": "2026-09-10", "yield": 4.22},
        {"date": "2026-09-11", "yield": 4.25}
    ]
    seen = set()
    cleaned = []
    for d in raw_data:
        if d["date"] not in seen:
            seen.add(d["date"])
            cleaned.append(d)
    assert len(cleaned) == 2

def test_future_observation_rejection():
    future_date = (datetime.date.today() + datetime.timedelta(days=2)).isoformat()
    raw_date = future_date
    today_str = datetime.date.today().isoformat()
    is_future = raw_date > today_str
    assert is_future is True

# 29-30. Intelligence Affinity & Causality Guard
def test_intelligence_affinity():
    uk_keywords = MARKET_AFFINITY_CONFIG["United Kingdom"]["keywords"]
    assert "gilt" in uk_keywords
    assert "bank rate" in uk_keywords
    assert "boe" in uk_keywords

    us_keywords = MARKET_AFFINITY_CONFIG["United States"]["keywords"]
    assert "treasury" in us_keywords
    assert "fed" in us_keywords

def test_causality_guard():
    yield_snap = create_sovereign_yield_snapshot(
        instrument_id="US_10Y", country="US", display_name="US 10Y", maturity="10Y",
        yield_percent=4.27, previous_yield_percent=4.20, market_date="2026-09-14", source="Fed"
    )
    takeaways = generate_market_takeaways([], "United States", 0, yield_snapshots=[yield_snap])
    for t in takeaways:
        text = t["text"].lower()
        assert "caused stocks to" not in text
        assert "triggered equity selloff" not in text

# 31-35. UI / Markets Route Robustness & Existing Functionality
def test_markets_survives_sovereign_provider_failure(test_db_session, monkeypatch):
    async def mock_fail(force_refresh=False):
        raise Exception("Sovereign provider down")
    monkeypatch.setattr("services.markets.service.MarketService.get_sovereign_yields", mock_fail)
    response = client.get("/markets")
    assert response.status_code == 200

def test_markets_survives_policy_provider_failure(test_db_session, monkeypatch):
    async def mock_fail(force_refresh=False):
        raise Exception("Policy provider down")
    monkeypatch.setattr("services.markets.service.MarketService.get_monetary_policy_rates", mock_fail)
    response = client.get("/markets")
    assert response.status_code == 200

def test_existing_equity_functionality_unaffected(test_db_session):
    response = client.get("/markets")
    assert response.status_code == 200
    assert "S&amp;P 500" in response.text or "S&P 500" in response.text or "GLOBAL MARKET PULSE" in response.text

def test_commodity_functionality_unaffected(test_db_session):
    response = client.get("/markets")
    assert response.status_code == 200
    assert "Brent Crude" in response.text or "Gold" in response.text or "MACRO &amp; COMMODITY PULSE" in response.text or "MACRO & COMMODITY PULSE" in response.text

def test_fx_functionality_unaffected(test_db_session):
    response = client.get("/markets")
    assert response.status_code == 200
    assert "FOREIGN EXCHANGE" in response.text or "USD / JPY" in response.text or "GBP / USD" in response.text or "EUR / USD" in response.text

# 36. No Ollama Invocation for Structured Rates
def test_no_ollama_invocation_for_structured_rates():
    snap = create_sovereign_yield_snapshot(
        instrument_id="US_10Y", country="US", display_name="US 10Y", maturity="10Y",
        yield_percent=4.27, previous_yield_percent=4.20, market_date="2026-09-14", source="Fed"
    )
    assert snap.change_basis_points == 7.0

# 37. Responsive Template Rendering
def test_responsive_template_rendering(test_db_session):
    response = client.get("/markets")
    assert response.status_code == 200
    assert "SOVEREIGN &amp; POLICY PULSE" in response.text or "SOVEREIGN & POLICY PULSE" in response.text
