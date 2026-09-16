"""Tests for historical market data calculations, SVG chart generation, caching, and stats."""

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from services.markets.historical import (
    HistoricalPoint,
    HistoricalSeries,
    compute_historical_statistics,
    fetch_historical_series_yahoo,
    generate_svg_mini_chart,
)
from services.markets.service import MarketService


def test_52w_high_low_and_ytd_calculation():
    """Verify 52W High, Low, Distance from High, and YTD statistics computation."""
    current_year = datetime.now(timezone.utc).year
    points = [
        HistoricalPoint(date_str=f"{current_year-1}-09-15", close=4500.0),
        HistoricalPoint(date_str=f"{current_year-1}-11-20", close=4200.0),  # Lowest overall
        HistoricalPoint(date_str=f"{current_year}-01-02", close=5000.0),    # First YTD close
        HistoricalPoint(date_str=f"{current_year}-02-10", close=5500.0),    # Highest 52W
        HistoricalPoint(date_str=f"{current_year}-09-15", close=5250.0),    # Latest
    ]

    high_52w, low_52w, dist_high, ytd_change = compute_historical_statistics(points, latest_close=5250.0)

    assert high_52w == 5500.0
    assert low_52w == 4200.0
    assert dist_high == pytest.approx(-4.55, 0.01)  # (5250 - 5500) / 5500 * 100 = -4.545...
    assert ytd_change == pytest.approx(5.0, 0.01)    # (5250 - 5000) / 5000 * 100 = +5.0


def test_missing_or_empty_history_handling():
    """Verify stats computation handles empty points list gracefully."""
    high_52w, low_52w, dist_high, ytd_change = compute_historical_statistics([], latest_close=5000.0)

    assert high_52w == 5000.0
    assert low_52w == 5000.0
    assert dist_high == 0.0
    assert ytd_change == 0.0


def test_svg_mini_chart_rendering():
    """Verify SVG string generation from historical points."""
    points = [
        HistoricalPoint(date_str="2026-01-01", close=100.0),
        HistoricalPoint(date_str="2026-01-02", close=120.0),
        HistoricalPoint(date_str="2026-01-03", close=110.0),
    ]
    svg = generate_svg_mini_chart(points)

    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    assert 'class="mini-chart-svg"' in svg
    assert "<path" in svg


def test_svg_mini_chart_empty_series():
    """Verify fallback SVG returned when points list is empty."""
    svg = generate_svg_mini_chart([])

    assert "<svg" in svg
    assert "Historical series temporarily unavailable." in svg


def test_fetch_historical_series_yahoo_success():
    """Verify Yahoo Finance historical parser parses timestamps and closes."""
    async def _test():
        mock_yahoo_response = {
            "chart": {
                "result": [
                    {
                        "timestamp": [1700000000, 1700086400],  # Unix timestamps in the past
                        "indicators": {
                            "quote": [
                                {
                                    "close": [5000.25, 5050.75]
                                }
                            ]
                        }
                    }
                ],
                "error": None
            }
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_yahoo_response

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            series = await fetch_historical_series_yahoo("United States")

            assert series is not None
            assert series.region == "United States"
            assert series.symbol == "SPX"
            assert len(series.daily_points) == 2
            assert series.daily_points[0].close == 5000.25
            assert series.daily_points[1].close == 5050.75

    asyncio.run(_test())


def test_fetch_historical_series_yahoo_failure_handling():
    """Verify Yahoo Finance historical parser returns None on network error."""
    async def _test():
        with patch("httpx.AsyncClient.get", side_effect=Exception("Network error")):
            series = await fetch_historical_series_yahoo("United States")
            assert series is None

    asyncio.run(_test())


def test_6hour_historical_cache_hit_and_expiry():
    """Verify MarketService historical series cache behaves with 6-hour TTL."""
    async def _test():
        service = MarketService()

        dummy_series = HistoricalSeries(
            region="United States",
            symbol="SPX",
            display_name="S&P 500",
            daily_points=[HistoricalPoint(date_str="2026-01-01", close=5000.0)],
            high_52w=5000.0,
            low_52w=5000.0,
            distance_from_52w_high=0.0,
            ytd_change_percent=0.0,
        )

        with patch("services.markets.service.fetch_historical_series_yahoo", new_callable=AsyncMock, return_value=dummy_series) as mock_fetch:
            # First fetch (cache miss)
            s1 = await service.get_historical_series("United States")
            assert mock_fetch.call_count == 1
            assert s1 == dummy_series

            # Second fetch within 6 hours (cache hit)
            s2 = await service.get_historical_series("United States")
            assert mock_fetch.call_count == 1
            assert s2 == dummy_series

            # Expire cache manually (store updated timestamp in key)
            service._historical_cache["united states"] = (dummy_series, time.time() - (6 * 3600 + 10))

            # Third fetch after 6 hours (cache miss & refresh)
            s3 = await service.get_historical_series("United States")
            assert mock_fetch.call_count == 2
            assert s3 == dummy_series

    asyncio.run(_test())


def test_news_section_title_market_intelligence(test_db_session):
    """Verify /markets page contains 'Market Intelligence' section heading."""
    client = TestClient(app)
    response = client.get("/markets")
    assert response.status_code == 200
    html = response.text
    assert "MARKET INTELLIGENCE" in html or "Market Intelligence" in html


def test_selected_market_context_rendering(test_db_session):
    """Verify route handles query parameter market selection cleanly."""
    client = TestClient(app)
    response = client.get("/markets?region=UK")
    assert response.status_code == 200
    assert "FTSE 100" in response.text


def test_csi_300_historical_symbol_mapping():
    """Verify China CSI 300 uses correct 000300.SS symbol in INDEX_BASKET."""
    from services.markets.provider import INDEX_BASKET
    china_item = next(item for item in INDEX_BASKET if item["region"] == "China")
    assert china_item["yahoo_symbol"] == "000300.SS"
    assert china_item["twelve_symbol"] == "399972"


def test_csi_300_insufficient_points_returns_none():
    """Verify single-point historical responses (e.g. 000300.SS) return None safely."""
    async def _test():
        mock_yahoo_response = {
            "chart": {
                "result": [
                    {
                        "timestamp": [1700000000],  # Single point only
                        "indicators": {
                            "quote": [
                                {
                                    "close": [4450.04]
                                }
                            ]
                        }
                    }
                ],
                "error": None
            }
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_yahoo_response

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            series = await fetch_historical_series_yahoo("China")
            assert series is None

    asyncio.run(_test())


def test_csi_300_stats_when_history_available():
    """Verify CSI 300 computes statistics correctly if multiple historical points exist."""
    async def _test():
        mock_yahoo_response = {
            "chart": {
                "result": [
                    {
                        "timestamp": [1700000000, 1700086400, 1700172800],
                        "indicators": {
                            "quote": [
                                {
                                    "close": [4000.0, 4200.0, 4100.0]
                                }
                            ]
                        }
                    }
                ],
                "error": None
            }
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_yahoo_response

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            series = await fetch_historical_series_yahoo("China")
            assert series is not None
            assert series.high_52w == 4200.0
            assert series.low_52w == 4000.0
            assert len(series.daily_points) == 3

    asyncio.run(_test())


def test_no_cross_market_historical_contamination():
    """Verify MarketService isolates historical cache entries by region key."""
    async def _test():
        service = MarketService()

        us_series = HistoricalSeries(
            region="United States",
            symbol="SPX",
            display_name="S&P 500",
            daily_points=[HistoricalPoint(date_str="2026-01-01", close=5000.0), HistoricalPoint(date_str="2026-01-02", close=5050.0)],
            high_52w=5050.0,
            low_52w=5000.0,
            distance_from_52w_high=0.0,
            ytd_change_percent=1.0,
        )

        with patch("services.markets.service.fetch_historical_series_yahoo", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = lambda reg: us_series if reg.lower() in ["us", "united states"] else None

            s_us = await service.get_historical_series("United States")
            s_china = await service.get_historical_series("China")

            assert s_us is not None
            assert s_us.region == "United States"
            assert s_china is None

    asyncio.run(_test())

