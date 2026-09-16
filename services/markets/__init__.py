"""
Market data package for Daily Intelligence.
Provides decoupled market data models, provider implementations, caching service,
trading session engine, market intelligence matching, and historical series.
"""

from services.markets.models import MarketSnapshot, Direction
from services.markets.service import MarketService, get_market_service
from services.markets.sessions import get_market_session_status, MarketSessionStatus
from services.markets.intelligence import (
    get_market_intelligence,
    generate_market_takeaways,
    MarketIntelligenceMatch,
    classify_causality_relationship,
)
from services.markets.historical import (
    HistoricalPoint,
    HistoricalSeries,
    fetch_historical_series_yahoo,
    generate_svg_mini_chart,
    compute_historical_statistics,
)

__all__ = [
    "MarketSnapshot",
    "Direction",
    "MarketService",
    "get_market_service",
    "get_market_session_status",
    "MarketSessionStatus",
    "get_market_intelligence",
    "generate_market_takeaways",
    "MarketIntelligenceMatch",
    "classify_causality_relationship",
    "HistoricalPoint",
    "HistoricalSeries",
    "fetch_historical_series_yahoo",
    "generate_svg_mini_chart",
    "compute_historical_statistics",
]
