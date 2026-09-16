import time
import logging
from typing import Optional, Dict, Tuple
from app.config import get_settings
from services.markets.models import (
    MarketSnapshot,
    SovereignYieldSnapshot,
    MonetaryPolicySnapshot,
)
from services.markets.provider import (
    MarketDataProvider,
    TwelveDataProvider,
    YahooFinanceProvider,
    SovereignYieldProvider,
    MonetaryPolicyProvider,
)
from services.markets.historical import HistoricalSeries, fetch_historical_series_yahoo

logger = logging.getLogger(__name__)

HISTORICAL_CACHE_TTL_SECONDS = 21600   # 6 hours TTL for 1Y daily close series
YIELD_CACHE_TTL_SECONDS = 1800          # 30 minutes TTL for sovereign yields
POLICY_CACHE_TTL_SECONDS = 21600        # 6 hours TTL for central bank policy rates


class MarketService:
    """
    Market data service providing in-memory TTL caching, fallback handling,
    historical series caching, cross-asset macro tracking, sovereign yield tracking,
    monetary policy tracking, and stale-cache failure isolation.
    """

    def __init__(
        self,
        provider: Optional[MarketDataProvider] = None,
        sovereign_provider: Optional[SovereignYieldProvider] = None,
        monetary_provider: Optional[MonetaryPolicyProvider] = None,
        cache_ttl_seconds: Optional[int] = None,
    ):
        settings = get_settings()
        self.cache_ttl_seconds = cache_ttl_seconds if cache_ttl_seconds is not None else settings.market_cache_ttl_seconds
        
        if provider is not None:
            self.provider = provider
        else:
            self.provider = TwelveDataProvider(api_key=settings.market_data_api_key)

        self.sovereign_provider = sovereign_provider or SovereignYieldProvider()
        self.monetary_provider = monetary_provider or MonetaryPolicyProvider()

        self._cached_snapshots: list[MarketSnapshot] = []
        self._last_fetch_time: float = 0.0

        self._cached_cross_assets: list[MarketSnapshot] = []
        self._last_cross_asset_fetch_time: float = 0.0

        self._cached_sovereign_yields: list[SovereignYieldSnapshot] = []
        self._last_sovereign_yield_fetch_time: float = 0.0

        self._cached_monetary_policy: list[MonetaryPolicySnapshot] = []
        self._last_monetary_policy_fetch_time: float = 0.0

        self._historical_cache: Dict[str, Tuple[HistoricalSeries, float]] = {}

    async def get_global_markets(self, force_refresh: bool = False) -> tuple[list[MarketSnapshot], bool]:
        """
        Retrieves global equity market snapshots.
        Returns a tuple of (snapshots, is_stale).
        """
        now = time.time()

        if not force_refresh and self._cached_snapshots and (now - self._last_fetch_time < self.cache_ttl_seconds):
            return self._cached_snapshots, False

        try:
            new_snapshots = await self.provider.fetch_snapshots()
            if not new_snapshots and isinstance(self.provider, TwelveDataProvider):
                logger.info("Twelve Data index queries unavailable; invoking YahooFinanceProvider fallback.")
                fallback_provider = YahooFinanceProvider()
                new_snapshots = await fallback_provider.fetch_snapshots()
        except Exception as exc:
            logger.error(f"Error invoking market data provider: {exc}")
            new_snapshots = []

        if new_snapshots:
            self._cached_snapshots = new_snapshots
            self._last_fetch_time = now
            return self._cached_snapshots, False

        if self._cached_snapshots:
            logger.warning("Market data provider returned empty snapshots. Falling back to stale cache.")
            stale_snapshots = [
                MarketSnapshot(
                    region=s.region,
                    symbol=s.symbol,
                    display_name=s.display_name,
                    latest_close=s.latest_close,
                    previous_close=s.previous_close,
                    change_value=s.change_value,
                    change_percent=s.change_percent,
                    direction=s.direction,
                    market_date=s.market_date,
                    fetched_at=s.fetched_at,
                    source=s.source,
                    currency=s.currency,
                    is_stale=True,
                    asset_class=s.asset_class,
                    unit=s.unit,
                    semantics_note=s.semantics_note,
                    canonical_id=s.canonical_id,
                )
                for s in self._cached_snapshots
            ]
            return stale_snapshots, True

        return [], False

    async def get_macro_commodities(self, force_refresh: bool = False) -> tuple[list[MarketSnapshot], bool]:
        """
        Retrieves macro, commodity, critical minerals, and FX cross-asset snapshots.
        Returns a tuple of (snapshots, is_stale).
        """
        now = time.time()

        if not force_refresh and self._cached_cross_assets and (now - self._last_cross_asset_fetch_time < self.cache_ttl_seconds):
            return self._cached_cross_assets, False

        try:
            new_snapshots = await self.provider.fetch_cross_asset_snapshots()
            if not new_snapshots and isinstance(self.provider, TwelveDataProvider):
                logger.info("Twelve Data cross-assets unavailable; invoking YahooFinanceProvider fallback.")
                fallback = YahooFinanceProvider()
                new_snapshots = await fallback.fetch_cross_asset_snapshots()
        except Exception as exc:
            logger.error(f"Error fetching macro/commodity cross-assets: {exc}")
            new_snapshots = []

        if new_snapshots:
            self._cached_cross_assets = new_snapshots
            self._last_cross_asset_fetch_time = now
            return self._cached_cross_assets, False

        if self._cached_cross_assets:
            logger.warning("Cross-asset fetch empty/failed. Returning stale cache.")
            stale = [
                MarketSnapshot(
                    region=s.region,
                    symbol=s.symbol,
                    display_name=s.display_name,
                    latest_close=s.latest_close,
                    previous_close=s.previous_close,
                    change_value=s.change_value,
                    change_percent=s.change_percent,
                    direction=s.direction,
                    market_date=s.market_date,
                    fetched_at=s.fetched_at,
                    source=s.source,
                    currency=s.currency,
                    is_stale=True,
                    asset_class=s.asset_class,
                    unit=s.unit,
                    semantics_note=s.semantics_note,
                    canonical_id=s.canonical_id,
                )
                for s in self._cached_cross_assets
            ]
            return stale, True

        return [], False

    async def get_sovereign_yields(self, force_refresh: bool = False) -> tuple[list[SovereignYieldSnapshot], bool]:
        """
        Retrieves 10-Year Benchmark Sovereign Bond Yields.
        Returns a tuple of (snapshots, is_stale).
        30-minute in-memory TTL caching with failure isolation.
        """
        now = time.time()

        if not force_refresh and self._cached_sovereign_yields and (now - self._last_sovereign_yield_fetch_time < YIELD_CACHE_TTL_SECONDS):
            return self._cached_sovereign_yields, False

        try:
            new_yields = await self.sovereign_provider.fetch_sovereign_yields()
        except Exception as exc:
            logger.error(f"Error fetching sovereign yields: {exc}")
            new_yields = []

        if new_yields:
            self._cached_sovereign_yields = new_yields
            self._last_sovereign_yield_fetch_time = now
            return self._cached_sovereign_yields, False

        if self._cached_sovereign_yields:
            logger.warning("Sovereign yield fetch empty/failed. Returning stale cache.")
            stale_yields = [
                SovereignYieldSnapshot(
                    instrument_id=s.instrument_id,
                    country=s.country,
                    display_name=s.display_name,
                    maturity=s.maturity,
                    yield_percent=s.yield_percent,
                    previous_yield_percent=s.previous_yield_percent,
                    change_basis_points=s.change_basis_points,
                    direction=s.direction,
                    market_date=s.market_date,
                    fetched_at=s.fetched_at,
                    source=s.source,
                    is_stale=True,
                    unit=s.unit,
                )
                for s in self._cached_sovereign_yields
            ]
            return stale_yields, True

        return [], False

    async def get_monetary_policy_rates(self, force_refresh: bool = False) -> tuple[list[MonetaryPolicySnapshot], bool]:
        """
        Retrieves Central Bank Monetary Policy Decisions and Policy Rates.
        Returns a tuple of (snapshots, is_stale).
        6-hour in-memory TTL caching with failure isolation.
        """
        now = time.time()

        if not force_refresh and self._cached_monetary_policy and (now - self._last_monetary_policy_fetch_time < POLICY_CACHE_TTL_SECONDS):
            return self._cached_monetary_policy, False

        try:
            new_policy = await self.monetary_provider.fetch_monetary_policy_rates()
        except Exception as exc:
            logger.error(f"Error fetching monetary policy rates: {exc}")
            new_policy = []

        if new_policy:
            self._cached_monetary_policy = new_policy
            self._last_monetary_policy_fetch_time = now
            return self._cached_monetary_policy, False

        if self._cached_monetary_policy:
            logger.warning("Monetary policy fetch empty/failed. Returning stale cache.")
            stale_policy = [
                MonetaryPolicySnapshot(
                    central_bank=s.central_bank,
                    jurisdiction=s.jurisdiction,
                    policy_rate_name=s.policy_rate_name,
                    rate=s.rate,
                    lower_bound=s.lower_bound,
                    upper_bound=s.upper_bound,
                    effective_date=s.effective_date,
                    decision_date=s.decision_date,
                    change_basis_points=s.change_basis_points,
                    action=s.action,
                    source=s.source,
                    fetched_at=s.fetched_at,
                    is_stale=True,
                    secondary_rates=s.secondary_rates,
                )
                for s in self._cached_monetary_policy
            ]
            return stale_policy, True

        return [], False

    async def get_historical_series(
        self,
        identifier: str = "United States",
        force_refresh: bool = False,
    ) -> Optional[HistoricalSeries]:
        """
        Retrieves 1Y historical series for specified region or canonical ID with 6-hour TTL caching.
        """
        now = time.time()
        reg_key = identifier.lower()

        if not force_refresh and reg_key in self._historical_cache:
            series, fetch_time = self._historical_cache[reg_key]
            if now - fetch_time < HISTORICAL_CACHE_TTL_SECONDS:
                return series

        try:
            series = await fetch_historical_series_yahoo(identifier)
            if series:
                self._historical_cache[reg_key] = (series, now)
                return series
        except Exception as exc:
            logger.error(f"Failed to fetch historical series for {identifier}: {exc}")

        if reg_key in self._historical_cache:
            return self._historical_cache[reg_key][0]

        return None


_market_service_instance: Optional[MarketService] = None


def get_market_service() -> MarketService:
    """Returns global singleton MarketService instance."""
    global _market_service_instance
    if _market_service_instance is None:
        _market_service_instance = MarketService()
    return _market_service_instance
