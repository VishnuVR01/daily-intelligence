import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import httpx
from fastapi.testclient import TestClient

from app.main import app
from services.markets.models import MarketSnapshot, create_market_snapshot
from services.markets.provider import (
    INDEX_BASKET,
    MarketDataProvider,
    TwelveDataProvider,
    YahooFinanceProvider,
)
from services.markets.service import MarketService, get_market_service


# ---------------------------------------------------------------------------
# Models & Helper Tests
# ---------------------------------------------------------------------------

def test_create_market_snapshot_positive_change_up():
    snapshot = create_market_snapshot(
        region="United States",
        symbol="SPX",
        display_name="S&P 500",
        latest_close=5550.0,
        previous_close=5500.0,
        market_date="2026-09-15",
        currency="USD",
    )
    assert snapshot.change_value == 50.0
    assert snapshot.change_percent == 0.9091
    assert snapshot.direction == "UP"
    assert snapshot.currency == "USD"
    assert snapshot.is_stale is False


def test_create_market_snapshot_negative_change_down():
    snapshot = create_market_snapshot(
        region="United Kingdom",
        symbol="FTSE",
        display_name="FTSE 100",
        latest_close=8200.0,
        previous_close=8300.0,
        market_date="2026-09-15",
        currency="GBP",
    )
    assert snapshot.change_value == -100.0
    assert snapshot.change_percent == -1.2048
    assert snapshot.direction == "DOWN"
    assert snapshot.currency == "GBP"


def test_create_market_snapshot_flat_threshold():
    # 0.04% change is below 0.05% threshold -> FLAT
    snapshot = create_market_snapshot(
        region="China",
        symbol="399972",
        display_name="CSI 300",
        latest_close=3501.4,
        previous_close=3500.0,
        market_date="2026-09-15",
        currency="CNY",
    )
    assert snapshot.change_percent == 0.04
    assert snapshot.direction == "FLAT"


def test_create_market_snapshot_zero_previous_close_safety():
    snapshot = create_market_snapshot(
        region="Test",
        symbol="TEST",
        display_name="Test Index",
        latest_close=100.0,
        previous_close=0.0,
        market_date="2026-09-15",
    )
    assert snapshot.change_value == 0.0
    assert snapshot.change_percent == 0.0
    assert snapshot.direction == "FLAT"


def test_basket_six_indices_present():
    assert len(INDEX_BASKET) == 6
    regions = [item["region"] for item in INDEX_BASKET]
    assert "United States" in regions
    assert "United Kingdom" in regions
    assert "India" in regions
    assert "Japan" in regions
    assert "Europe" in regions
    assert "China" in regions


# ---------------------------------------------------------------------------
# Provider Tests
# ---------------------------------------------------------------------------

def test_twelve_data_provider_missing_key():
    async def _test():
        provider = TwelveDataProvider(api_key="")
        snapshots = await provider.fetch_snapshots()
        assert snapshots == []

    asyncio.run(_test())


def test_twelve_data_provider_successful_fetch():
    async def _test():
        mock_payload = {
            "SPX": {"symbol": "SPX", "close": "5500.00", "previous_close": "5450.00", "datetime": "2026-09-15", "currency": "USD"},
            "FTSE": {"symbol": "FTSE", "close": "8200.00", "previous_close": "8200.00", "datetime": "2026-09-15", "currency": "GBP"},
            "NSEI": {"symbol": "NSEI", "close": "25000.00", "previous_close": "24800.00", "datetime": "2026-09-15", "currency": "INR"},
            "N225": {"symbol": "N225", "close": "36000.00", "previous_close": "36200.00", "datetime": "2026-09-15", "currency": "JPY"},
            "STOXX": {"symbol": "STOXX", "close": "500.00", "previous_close": "498.00", "datetime": "2026-09-15", "currency": "EUR"},
            "399972": {"symbol": "399972", "close": "3500.00", "previous_close": "3500.00", "datetime": "2026-09-15", "currency": "CNY"},
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_payload

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            provider = TwelveDataProvider(api_key="test_api_key")
            snapshots = await provider.fetch_snapshots()

        assert len(snapshots) == 6
        assert snapshots[0].symbol == "SPX"
        assert snapshots[0].latest_close == 5500.0
        assert snapshots[0].currency == "USD"
        assert snapshots[0].direction == "UP"

    asyncio.run(_test())


def test_twelve_data_provider_http_error():
    async def _test():
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            provider = TwelveDataProvider(api_key="test_api_key")
            snapshots = await provider.fetch_snapshots()

        assert snapshots == []

    asyncio.run(_test())


def test_yahoo_finance_provider_fallback():
    async def _test():
        mock_payload = {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "regularMarketPrice": 5500.0,
                            "chartPreviousClose": 5450.0,
                            "currency": "USD",
                        }
                    }
                ]
            }
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_payload

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            provider = YahooFinanceProvider()
            snapshots = await provider.fetch_snapshots()

        assert len(snapshots) == 6
        assert snapshots[0].source == "Yahoo Finance (Fallback)"

    asyncio.run(_test())


# ---------------------------------------------------------------------------
# Market Service Tests
# ---------------------------------------------------------------------------

class MockSuccessProvider(MarketDataProvider):
    def __init__(self, snapshots: list[MarketSnapshot]):
        self.snapshots = snapshots
        self.call_count = 0

    async def fetch_snapshots(self) -> list[MarketSnapshot]:
        self.call_count += 1
        return self.snapshots

    async def fetch_cross_asset_snapshots(self) -> list[MarketSnapshot]:
        return []


class MockFailingProvider(MarketDataProvider):
    def __init__(self):
        self.call_count = 0

    async def fetch_snapshots(self) -> list[MarketSnapshot]:
        self.call_count += 1
        return []

    async def fetch_cross_asset_snapshots(self) -> list[MarketSnapshot]:
        return []


def test_market_service_cache_hit():
    async def _test():
        sample_snapshot = create_market_snapshot(
            region="United States",
            symbol="SPX",
            display_name="S&P 500",
            latest_close=5500.0,
            previous_close=5450.0,
            market_date="2026-09-15",
        )
        provider = MockSuccessProvider([sample_snapshot])
        service = MarketService(provider=provider, cache_ttl_seconds=900)

        # First call: hits provider
        res1, is_stale1 = await service.get_global_markets()
        assert len(res1) == 1
        assert is_stale1 is False
        assert provider.call_count == 1

        # Second call within TTL: hits cache
        res2, is_stale2 = await service.get_global_markets()
        assert len(res2) == 1
        assert is_stale2 is False
        assert provider.call_count == 1

    asyncio.run(_test())


def test_market_service_cache_expiry():
    async def _test():
        sample_snapshot = create_market_snapshot(
            region="United States",
            symbol="SPX",
            display_name="S&P 500",
            latest_close=5500.0,
            previous_close=5450.0,
            market_date="2026-09-15",
        )
        provider = MockSuccessProvider([sample_snapshot])
        # 1 second TTL
        service = MarketService(provider=provider, cache_ttl_seconds=1)

        await service.get_global_markets()
        assert provider.call_count == 1

        # Wait for TTL to expire
        time.sleep(1.1)

        await service.get_global_markets()
        assert provider.call_count == 2

    asyncio.run(_test())


def test_market_service_stale_cache_fallback():
    async def _test():
        sample_snapshot = create_market_snapshot(
            region="United States",
            symbol="SPX",
            display_name="S&P 500",
            latest_close=5500.0,
            previous_close=5450.0,
            market_date="2026-09-15",
        )
        # Start with success provider to prime cache
        success_provider = MockSuccessProvider([sample_snapshot])
        service = MarketService(provider=success_provider, cache_ttl_seconds=1)

        # Prime cache
        await service.get_global_markets()

        # Switch provider to failing provider and expire TTL
        service.provider = MockFailingProvider()
        time.sleep(1.1)

        stale_res, is_stale = await service.get_global_markets()
        assert len(stale_res) == 1
        assert is_stale is True
        assert stale_res[0].is_stale is True

    asyncio.run(_test())


def test_market_service_empty_cache_provider_failure():
    async def _test():
        service = MarketService(provider=MockFailingProvider(), cache_ttl_seconds=900)
        res, is_stale = await service.get_global_markets()
        assert res == []
        assert is_stale is False

    asyncio.run(_test())


def test_market_service_force_refresh():
    async def _test():
        sample_snapshot = create_market_snapshot(
            region="United States",
            symbol="SPX",
            display_name="S&P 500",
            latest_close=5500.0,
            previous_close=5450.0,
            market_date="2026-09-15",
        )
        provider = MockSuccessProvider([sample_snapshot])
        service = MarketService(provider=provider, cache_ttl_seconds=900)

        await service.get_global_markets()
        assert provider.call_count == 1

        # Force refresh bypasses cache
        await service.get_global_markets(force_refresh=True)
        assert provider.call_count == 2

    asyncio.run(_test())


# ---------------------------------------------------------------------------
# Integration & UI Route Tests
# ---------------------------------------------------------------------------

def test_homepage_route_renders_global_markets(test_db_session):
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
    assert "United States" in response.text
    assert "5,550.00" in response.text
    assert "DEMO" not in response.text


def test_homepage_route_handles_market_failure_gracefully(test_db_session):
    mock_service = AsyncMock()
    mock_service.get_global_markets.return_value = ([], False)

    with patch("app.main.get_market_service", return_value=mock_service):
        client = TestClient(app)
        response = client.get("/")

    assert response.status_code == 200
    assert "Global Markets" in response.text
    assert "Market data temporarily unavailable." in response.text


def test_no_api_key_leakage():
    api_key = "SECRET_KEY_12345"
    provider = TwelveDataProvider(api_key=api_key)
    snapshot = create_market_snapshot(
        region="United States",
        symbol="SPX",
        display_name="S&P 500",
        latest_close=5500.0,
        previous_close=5450.0,
        market_date="2026-09-15",
    )
    assert api_key not in repr(snapshot)
    assert api_key not in str(snapshot)


# ---------------------------------------------------------------------------
# Stage 2C Cross-Asset Tests
# ---------------------------------------------------------------------------

def test_stage_2c_basket_identities():
    """Verify all 9 approved Stage 2C instruments have exact canonical identities and symbols."""
    from services.markets.provider import CROSS_ASSET_BASKET
    assert len(CROSS_ASSET_BASKET) == 9

    brent = next(i for i in CROSS_ASSET_BASKET if i["canonical_id"] == "BRENT_CRUDE_FUTURES")
    assert brent["yahoo_symbol"] == "BZ=F"
    assert brent["asset_class"] == "ENERGY_FUTURES"

    wti = next(i for i in CROSS_ASSET_BASKET if i["canonical_id"] == "WTI_CRUDE_FUTURES")
    assert wti["yahoo_symbol"] == "CL=F"
    assert wti["asset_class"] == "ENERGY_FUTURES"

    gold = next(i for i in CROSS_ASSET_BASKET if i["canonical_id"] == "GOLD_FUTURES")
    assert gold["yahoo_symbol"] == "GC=F"
    assert gold["asset_class"] == "METALS_FUTURES"

    silver = next(i for i in CROSS_ASSET_BASKET if i["canonical_id"] == "SILVER_FUTURES")
    assert silver["yahoo_symbol"] == "SI=F"

    remx = next(i for i in CROSS_ASSET_BASKET if i["canonical_id"] == "REMX_EQUITY_PROXY")
    assert remx["yahoo_symbol"] == "REMX"
    assert remx["asset_class"] == "EQUITY_PROXY"

    gbp_usd = next(i for i in CROSS_ASSET_BASKET if i["canonical_id"] == "GBP_USD")
    assert gbp_usd["yahoo_symbol"] == "GBPUSD=X"
    assert gbp_usd["asset_class"] == "FX"

    eur_usd = next(i for i in CROSS_ASSET_BASKET if i["canonical_id"] == "EUR_USD")
    assert eur_usd["yahoo_symbol"] == "EURUSD=X"

    usd_inr = next(i for i in CROSS_ASSET_BASKET if i["canonical_id"] == "USD_INR")
    assert usd_inr["yahoo_symbol"] == "USDINR=X"

    usd_jpy = next(i for i in CROSS_ASSET_BASKET if i["canonical_id"] == "USD_JPY")
    assert usd_jpy["yahoo_symbol"] == "USDJPY=X"


def test_remx_never_classified_as_commodity():
    """Verify REMX snapshot is strictly constructed with EQUITY_PROXY asset class."""
    snap = create_market_snapshot(
        region="Critical Minerals",
        symbol="REMX",
        display_name="Rare Earth & Strategic Metals",
        latest_close=68.40,
        previous_close=60.95,
        market_date="2026-09-15",
        asset_class="EQUITY_PROXY",
        unit="USD / share",
        semantics_note="EQUITY PROXY — VanEck Rare Earth & Strategic Metals Mining Index ETF",
    )
    assert snap.asset_class == "EQUITY_PROXY"
    assert snap.asset_class != "COMMODITY"


def test_gold_spot_and_futures_identity_not_mixed():
    """Verify Gold Futures canonical snapshot preserves GC=F futures identity."""
    snap = create_market_snapshot(
        region="Precious Metals",
        symbol="GC=F",
        display_name="Gold Futures",
        latest_close=4343.20,
        previous_close=3719.00,
        market_date="2026-09-15",
        asset_class="METALS_FUTURES",
        unit="USD / t oz",
        canonical_id="GOLD_FUTURES",
    )
    assert snap.canonical_id == "GOLD_FUTURES"
    assert snap.symbol == "GC=F"
    assert "Spot" not in snap.display_name


def test_fx_movement_semantics():
    """Verify deterministic FX movement interpretations."""
    from services.markets.intelligence import interpret_fx_movement

    # 1. GBP/USD Rises -> GBP Strengthened
    gbp_up = create_market_snapshot("FX", "GBP/USD", "GBP / USD", 1.3550, 1.3450, "2026-09-15", asset_class="FX")
    res_gbp_up = interpret_fx_movement(gbp_up)
    assert "strengthened" in res_gbp_up["statement"]
    assert "GBP" in res_gbp_up["statement"]

    # 2. GBP/USD Falls -> GBP Weakened
    gbp_down = create_market_snapshot("FX", "GBP/USD", "GBP / USD", 1.3400, 1.3500, "2026-09-15", asset_class="FX")
    res_gbp_down = interpret_fx_movement(gbp_down)
    assert "weakened" in res_gbp_down["statement"]

    # 3. USD/INR Rises -> INR Weakened
    inr_up = create_market_snapshot("FX", "USD/INR", "USD / INR", 96.00, 88.00, "2026-09-15", asset_class="FX")
    res_inr_up = interpret_fx_movement(inr_up)
    assert "weakened" in res_inr_up["statement"]
    assert "Rupee" in res_inr_up["statement"]

    # 4. USD/INR Falls -> INR Strengthened
    inr_down = create_market_snapshot("FX", "USD/INR", "USD / INR", 87.00, 88.00, "2026-09-15", asset_class="FX")
    res_inr_down = interpret_fx_movement(inr_down)
    assert "strengthened" in res_inr_down["statement"]

    # 5. USD/JPY Rises -> JPY Weakened
    jpy_up = create_market_snapshot("FX", "USD/JPY", "USD / JPY", 155.00, 148.00, "2026-09-15", asset_class="FX")
    res_jpy_up = interpret_fx_movement(jpy_up)
    assert "weakened" in res_jpy_up["statement"]
    assert "Yen" in res_jpy_up["statement"]


def test_cross_asset_single_instrument_failure_isolation():
    """Verify failure of cross-asset providers does not break MarketService."""
    async def _test():
        mock_provider = MockFailingProvider()
        service = MarketService(provider=mock_provider)
        snaps, is_stale = await service.get_macro_commodities()
        assert snaps == []
        assert is_stale is False

    asyncio.run(_test())

