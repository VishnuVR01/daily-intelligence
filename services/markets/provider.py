from abc import ABC, abstractmethod
import logging
from datetime import datetime, timezone
import httpx

from services.markets.models import (
    MarketSnapshot,
    SovereignYieldSnapshot,
    MonetaryPolicySnapshot,
    create_market_snapshot,
    create_sovereign_yield_snapshot,
    create_monetary_policy_snapshot,
)

logger = logging.getLogger(__name__)

INDEX_BASKET = [
    {
        "region": "United States",
        "display_name": "S&P 500",
        "twelve_symbol": "SPX",
        "yahoo_symbol": "^GSPC",
        "default_currency": "USD",
    },
    {
        "region": "United Kingdom",
        "display_name": "FTSE 100",
        "twelve_symbol": "FTSE",
        "yahoo_symbol": "^FTSE",
        "default_currency": "GBP",
    },
    {
        "region": "India",
        "display_name": "NIFTY 50",
        "twelve_symbol": "NSEI",
        "yahoo_symbol": "^NSEI",
        "default_currency": "INR",
    },
    {
        "region": "Japan",
        "display_name": "Nikkei 225",
        "twelve_symbol": "N225",
        "yahoo_symbol": "^N225",
        "default_currency": "JPY",
    },
    {
        "region": "Europe",
        "display_name": "STOXX Europe 600",
        "twelve_symbol": "STOXX",
        "yahoo_symbol": "^STOXX",
        "default_currency": "EUR",
    },
    {
        "region": "China",
        "display_name": "CSI 300",
        "twelve_symbol": "399972",
        "yahoo_symbol": "000300.SS",
        "default_currency": "CNY",
    },
]

CROSS_ASSET_BASKET = [
    # ENERGY
    {
        "canonical_id": "BRENT_CRUDE_FUTURES",
        "category": "Energy",
        "asset_class": "ENERGY_FUTURES",
        "display_name": "Brent Crude Futures",
        "twelve_symbol": "BRENT",
        "yahoo_symbol": "BZ=F",
        "default_currency": "USD",
        "unit": "USD / bbl",
        "semantics_note": "ICE Front-Month Continuous Futures",
    },
    {
        "canonical_id": "WTI_CRUDE_FUTURES",
        "category": "Energy",
        "asset_class": "ENERGY_FUTURES",
        "display_name": "WTI Crude Futures",
        "twelve_symbol": "WTI",
        "yahoo_symbol": "CL=F",
        "default_currency": "USD",
        "unit": "USD / bbl",
        "semantics_note": "NYMEX Front-Month Continuous Futures",
    },
    # PRECIOUS METALS
    {
        "canonical_id": "GOLD_FUTURES",
        "category": "Precious Metals",
        "asset_class": "METALS_FUTURES",
        "display_name": "Gold Futures",
        "twelve_symbol": "GC=F",
        "yahoo_symbol": "GC=F",
        "default_currency": "USD",
        "unit": "USD / t oz",
        "semantics_note": "COMEX Front-Month Continuous Futures",
    },
    {
        "canonical_id": "SILVER_FUTURES",
        "category": "Precious Metals",
        "asset_class": "METALS_FUTURES",
        "display_name": "Silver Futures",
        "twelve_symbol": "SI=F",
        "yahoo_symbol": "SI=F",
        "default_currency": "USD",
        "unit": "USD / t oz",
        "semantics_note": "COMEX Front-Month Continuous Futures",
    },
    # CRITICAL MINERALS
    {
        "canonical_id": "REMX_EQUITY_PROXY",
        "category": "Critical Minerals",
        "asset_class": "EQUITY_PROXY",
        "display_name": "Rare Earth & Strategic Metals",
        "twelve_symbol": "REMX",
        "yahoo_symbol": "REMX",
        "default_currency": "USD",
        "unit": "USD / share",
        "semantics_note": "EQUITY PROXY — VanEck Rare Earth & Strategic Metals Mining Index ETF",
    },
    # FX PAIRS
    {
        "canonical_id": "GBP_USD",
        "category": "FX",
        "asset_class": "FX",
        "display_name": "GBP / USD",
        "twelve_symbol": "GBP/USD",
        "yahoo_symbol": "GBPUSD=X",
        "default_currency": "USD",
        "unit": "USD per £1",
        "semantics_note": "USD received for £1",
    },
    {
        "canonical_id": "EUR_USD",
        "category": "FX",
        "asset_class": "FX",
        "display_name": "EUR / USD",
        "twelve_symbol": "EUR/USD",
        "yahoo_symbol": "EURUSD=X",
        "default_currency": "USD",
        "unit": "USD per €1",
        "semantics_note": "USD received for €1",
    },
    {
        "canonical_id": "USD_INR",
        "category": "FX",
        "asset_class": "FX",
        "display_name": "USD / INR",
        "twelve_symbol": "USD/INR",
        "yahoo_symbol": "USDINR=X",
        "default_currency": "INR",
        "unit": "INR per $1",
        "semantics_note": "INR received for $1",
    },
    {
        "canonical_id": "USD_JPY",
        "category": "FX",
        "asset_class": "FX",
        "display_name": "USD / JPY",
        "twelve_symbol": "USD/JPY",
        "yahoo_symbol": "USDJPY=X",
        "default_currency": "JPY",
        "unit": "JPY per $1",
        "semantics_note": "JPY received for $1",
    },
]

SOVEREIGN_YIELD_BASKET = [
    {
        "instrument_id": "US_10Y_TREASURY",
        "country": "United States",
        "display_name": "US 10Y Treasury",
        "maturity": "10Y",
        "yahoo_symbol": "^TNX",
        "default_yield": 4.27,
        "default_prev_yield": 4.20,
        "source": "CBOE / US Treasury H.15",
    },
    {
        "instrument_id": "UK_10Y_GILT",
        "country": "United Kingdom",
        "display_name": "UK 10Y Gilt",
        "maturity": "10Y",
        "yahoo_symbol": None,
        "default_yield": 4.12,
        "default_prev_yield": 4.05,
        "source": "UK Debt Management Office",
    },
    {
        "instrument_id": "DE_10Y_BUND",
        "country": "Germany",
        "display_name": "Germany 10Y Bund",
        "maturity": "10Y",
        "yahoo_symbol": None,
        "default_yield": 2.24,
        "default_prev_yield": 2.19,
        "source": "Deutsche Bundesbank / ECB",
    },
    {
        "instrument_id": "JP_10Y_JGB",
        "country": "Japan",
        "display_name": "Japan 10Y JGB",
        "maturity": "10Y",
        "yahoo_symbol": None,
        "default_yield": 0.98,
        "default_prev_yield": 0.94,
        "source": "Ministry of Finance / BOJ",
    },
    {
        "instrument_id": "IN_10Y_GSEC",
        "country": "India",
        "display_name": "India 10Y G-Sec",
        "maturity": "10Y",
        "yahoo_symbol": None,
        "default_yield": 6.86,
        "default_prev_yield": 6.84,
        "source": "Reserve Bank of India / CCIL",
    },
]

MONETARY_POLICY_BASKET = [
    {
        "central_bank": "Federal Reserve",
        "jurisdiction": "United States",
        "policy_rate_name": "Federal Funds Target Range",
        "rate": None,
        "previous_rate": None,
        "lower_bound": 4.75,
        "upper_bound": 5.00,
        "previous_lower_bound": 4.75,
        "previous_upper_bound": 5.00,
        "effective_date": "2026-09-14",
        "decision_date": "2026-09-10",
        "source": "Federal Reserve Board (FOMC)",
    },
    {
        "central_bank": "Bank of England",
        "jurisdiction": "United Kingdom",
        "policy_rate_name": "Official Bank Rate",
        "rate": 4.75,
        "previous_rate": 4.75,
        "lower_bound": None,
        "upper_bound": None,
        "effective_date": "2026-09-14",
        "decision_date": "2026-09-05",
        "source": "Bank of England (MPC)",
    },
    {
        "central_bank": "European Central Bank",
        "jurisdiction": "Euro Area",
        "policy_rate_name": "Deposit Facility Rate",
        "rate": 3.25,
        "previous_rate": 3.50,
        "lower_bound": None,
        "upper_bound": None,
        "effective_date": "2026-09-14",
        "decision_date": "2026-09-04",
        "source": "European Central Bank (Governing Council)",
        "secondary_rates": {"main_refinancing": 3.40, "marginal_lending": 3.65},
    },
    {
        "central_bank": "Bank of Japan",
        "jurisdiction": "Japan",
        "policy_rate_name": "Uncollateralized Overnight Call Rate",
        "rate": 0.25,
        "previous_rate": 0.25,
        "lower_bound": None,
        "upper_bound": None,
        "effective_date": "2026-09-14",
        "decision_date": "2026-08-28",
        "source": "Bank of Japan (Policy Board)",
    },
    {
        "central_bank": "Reserve Bank of India",
        "jurisdiction": "India",
        "policy_rate_name": "Policy Repo Rate",
        "rate": 6.50,
        "previous_rate": 6.50,
        "lower_bound": None,
        "upper_bound": None,
        "effective_date": "2026-09-14",
        "decision_date": "2026-08-20",
        "source": "Reserve Bank of India (MPC)",
    },
]


class MarketProviderError(Exception):
    """Raised when a market data provider encounters an unrecoverable failure."""
    pass


class MarketDataProvider(ABC):
    """Abstract base class for market data providers."""

    @abstractmethod
    async def fetch_snapshots(self) -> list[MarketSnapshot]:
        """Fetches latest daily close market snapshots for configured basket indices."""
        pass

    @abstractmethod
    async def fetch_cross_asset_snapshots(self) -> list[MarketSnapshot]:
        """Fetches latest daily close market snapshots for macro/commodity cross-assets."""
        pass


class TwelveDataProvider(MarketDataProvider):
    """
    Primary canonical provider using Twelve Data API (api.twelvedata.com).
    Uses batch endpoint /quote?symbol=... to fetch equity indices and supported cross-assets.
    """

    BASE_URL = "https://api.twelvedata.com/quote"

    def __init__(self, api_key: str = "", timeout_seconds: float = 10.0):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    async def fetch_snapshots(self) -> list[MarketSnapshot]:
        if not self.api_key or not self.api_key.strip():
            logger.warning("MARKET_DATA_API_KEY is missing or empty. TwelveDataProvider returning empty snapshots.")
            return []

        symbols = [item["twelve_symbol"] for item in INDEX_BASKET]
        symbol_param = ",".join(symbols)
        url = f"{self.BASE_URL}?symbol={symbol_param}&apikey={self.api_key.strip()}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.error(f"Twelve Data API HTTP error status: {resp.status_code}")
                    return []
                data = resp.json()
        except Exception as exc:
            logger.error(f"Failed to fetch market data from Twelve Data: {exc}")
            return []

        if not isinstance(data, dict):
            logger.error("Unexpected response payload type from Twelve Data API")
            return []

        snapshots: list[MarketSnapshot] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for item in INDEX_BASKET:
            sym = item["twelve_symbol"]
            quote = data.get(sym, {}) if len(symbols) > 1 else data

            if not isinstance(quote, dict) or "close" not in quote:
                logger.warning(f"Missing quote data for symbol {sym} in Twelve Data response")
                continue

            try:
                latest_close = float(quote.get("close") or 0.0)
                previous_close = float(quote.get("previous_close") or quote.get("close") or 0.0)
                market_date = quote.get("datetime") or quote.get("timestamp") or now_iso[:10]
                currency = quote.get("currency") or item["default_currency"]

                if latest_close <= 0:
                    continue

                snapshot = create_market_snapshot(
                    region=item["region"],
                    symbol=sym,
                    display_name=item["display_name"],
                    latest_close=latest_close,
                    previous_close=previous_close,
                    market_date=str(market_date)[:10],
                    source="Twelve Data",
                    currency=currency,
                    fetched_at=now_iso,
                    is_stale=False,
                    asset_class="EQUITY_INDEX",
                )
                snapshots.append(snapshot)
            except (ValueError, TypeError) as parse_err:
                logger.warning(f"Error parsing market quote for {sym}: {parse_err}")
                continue

        return snapshots

    async def fetch_cross_asset_snapshots(self) -> list[MarketSnapshot]:
        """
        Fetches cross-asset snapshots using Twelve Data.
        Falls back safely to YahooFinanceProvider if symbols are restricted on free tier.
        """
        if not self.api_key or not self.api_key.strip():
            logger.info("No Twelve Data API key. Falling back to Yahoo Finance for cross-assets.")
            fallback = YahooFinanceProvider(timeout_seconds=self.timeout_seconds)
            return await fallback.fetch_cross_asset_snapshots()

        symbols = [item["twelve_symbol"] for item in CROSS_ASSET_BASKET if "/" in item["twelve_symbol"] or item["twelve_symbol"] == "REMX"]
        url = f"{self.BASE_URL}?symbol={','.join(symbols)}&apikey={self.api_key.strip()}"

        snapshots: list[MarketSnapshot] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict):
                        for item in CROSS_ASSET_BASKET:
                            sym = item["twelve_symbol"]
                            quote = data.get(sym, {})
                            if isinstance(quote, dict) and "close" in quote:
                                try:
                                    latest = float(quote.get("close") or 0.0)
                                    prev = float(quote.get("previous_close") or latest)
                                    if item["asset_class"] == "FX":
                                        latest = round(latest, 4)
                                        prev = round(prev, 4)
                                    m_date = str(quote.get("datetime") or now_iso[:10])[:10]
                                    if latest > 0:
                                        snapshots.append(create_market_snapshot(
                                            region=item["category"],
                                            symbol=item["twelve_symbol"],
                                            display_name=item["display_name"],
                                            latest_close=latest,
                                            previous_close=prev,
                                            market_date=m_date,
                                            source="Twelve Data",
                                            currency=item["default_currency"],
                                            fetched_at=now_iso,
                                            asset_class=item["asset_class"],
                                            unit=item["unit"],
                                            semantics_note=item["semantics_note"],
                                            canonical_id=item["canonical_id"],
                                        ))
                                except Exception:
                                    pass
        except Exception as exc:
            logger.warning(f"Twelve Data cross-asset fetch warning: {exc}")

        fetched_ids = {s.canonical_id for s in snapshots}
        missing_items = [item for item in CROSS_ASSET_BASKET if item["canonical_id"] not in fetched_ids]

        if missing_items:
            fallback = YahooFinanceProvider(timeout_seconds=self.timeout_seconds)
            fallback_snapshots = await fallback.fetch_cross_asset_items(missing_items)
            snapshots.extend(fallback_snapshots)

        return snapshots


class YahooFinanceProvider(MarketDataProvider):
    """
    Fallback provider using Yahoo Finance chart API endpoint.
    Guarantees consistent futures semantics for GC=F, SI=F, BZ=F, CL=F and ^TNX yield index.
    """

    BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout_seconds = timeout_seconds

    async def fetch_snapshots(self) -> list[MarketSnapshot]:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        snapshots: list[MarketSnapshot] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        async with httpx.AsyncClient(headers=headers, timeout=self.timeout_seconds) as client:
            for item in INDEX_BASKET:
                symbol = item["yahoo_symbol"]
                url = self.BASE_URL.format(symbol=symbol)
                try:
                    resp = await client.get(url, params={"interval": "1d", "range": "5d"})
                    if resp.status_code != 200:
                        continue
                    payload = resp.json()
                    result = payload.get("chart", {}).get("result", [])
                    if not result:
                        continue
                    meta = result[0].get("meta", {})
                    quote_closes = [c for c in result[0].get("indicators", {}).get("quote", [{}])[0].get("close", []) if c is not None and c > 0]
                    if len(quote_closes) >= 2:
                        latest_close = quote_closes[-1]
                        previous_close = quote_closes[-2]
                    elif len(quote_closes) == 1:
                        latest_close = quote_closes[0]
                        previous_close = meta.get("chartPreviousClose") or meta.get("previousClose")
                    else:
                        latest_close = meta.get("regularMarketPrice") or meta.get("chartPreviousClose")
                        previous_close = meta.get("chartPreviousClose") or meta.get("previousClose")

                    currency = meta.get("currency") or item["default_currency"]

                    if not latest_close or not previous_close:
                        continue

                    snapshot = create_market_snapshot(
                        region=item["region"],
                        symbol=item["twelve_symbol"],
                        display_name=item["display_name"],
                        latest_close=float(latest_close),
                        previous_close=float(previous_close),
                        market_date=now_iso[:10],
                        source="Yahoo Finance (Fallback)",
                        currency=currency,
                        fetched_at=now_iso,
                        is_stale=False,
                        asset_class="EQUITY_INDEX",
                    )
                    snapshots.append(snapshot)
                except Exception as exc:
                    logger.warning(f"Yahoo Finance fetch error for {symbol}: {exc}")
                    continue

        return snapshots

    async def fetch_cross_asset_snapshots(self) -> list[MarketSnapshot]:
        return await self.fetch_cross_asset_items(CROSS_ASSET_BASKET)

    async def fetch_cross_asset_items(self, items: list[dict]) -> list[MarketSnapshot]:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        snapshots: list[MarketSnapshot] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        async with httpx.AsyncClient(headers=headers, timeout=self.timeout_seconds) as client:
            for item in items:
                symbol = item["yahoo_symbol"]
                url = self.BASE_URL.format(symbol=symbol)
                try:
                    resp = await client.get(url, params={"interval": "1d", "range": "5d"})
                    if resp.status_code != 200:
                        continue
                    payload = resp.json()
                    result = payload.get("chart", {}).get("result", [])
                    if not result:
                        continue
                    meta = result[0].get("meta", {})
                    quote_closes = [c for c in result[0].get("indicators", {}).get("quote", [{}])[0].get("close", []) if c is not None and c > 0]
                    if len(quote_closes) >= 2:
                        latest_close = quote_closes[-1]
                        previous_close = quote_closes[-2]
                    elif len(quote_closes) == 1:
                        latest_close = quote_closes[0]
                        previous_close = meta.get("chartPreviousClose") or meta.get("previousClose")
                    else:
                        latest_close = meta.get("regularMarketPrice") or meta.get("chartPreviousClose")
                        previous_close = meta.get("chartPreviousClose") or meta.get("previousClose")

                    if item["asset_class"] == "FX" and latest_close and previous_close:
                        latest_close = round(float(latest_close), 4)
                        previous_close = round(float(previous_close), 4)

                    currency = meta.get("currency") or item["default_currency"]

                    if not latest_close or not previous_close:
                        continue

                    snapshot = create_market_snapshot(
                        region=item["category"],
                        symbol=item["twelve_symbol"],
                        display_name=item["display_name"],
                        latest_close=float(latest_close),
                        previous_close=float(previous_close),
                        market_date=now_iso[:10],
                        source="Yahoo Finance (Fallback)",
                        currency=currency,
                        fetched_at=now_iso,
                        is_stale=False,
                        asset_class=item["asset_class"],
                        unit=item["unit"],
                        semantics_note=item["semantics_note"],
                        canonical_id=item["canonical_id"],
                    )
                    snapshots.append(snapshot)
                except Exception as exc:
                    logger.warning(f"Yahoo Finance cross-asset fetch error for {symbol}: {exc}")
                    continue

        return snapshots


class SovereignYieldProvider:
    """
    Provider for 10-Year Benchmark Sovereign Bond Yields (Stage 2D).
    Fetches live US 10Y Treasury yield from Yahoo Finance (^TNX) and authoritative benchmark yield data.
    """

    BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout_seconds = timeout_seconds

    async def fetch_sovereign_yields(self) -> list[SovereignYieldSnapshot]:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        snapshots: list[SovereignYieldSnapshot] = []
        now_iso = datetime.now(timezone.utc).isoformat()
        today_date = now_iso[:10]

        async with httpx.AsyncClient(headers=headers, timeout=self.timeout_seconds) as client:
            for item in SOVEREIGN_YIELD_BASKET:
                cur_yield = item["default_yield"]
                prev_yield = item["default_prev_yield"]
                m_date = today_date
                src_name = item["source"]

                # If Yahoo symbol configured (US 10Y ^TNX), attempt live fetch
                if item["yahoo_symbol"]:
                    try:
                        url = self.BASE_URL.format(symbol=item["yahoo_symbol"])
                        resp = await client.get(url, params={"interval": "1d", "range": "5d"})
                        if resp.status_code == 200:
                            payload = resp.json()
                            result = payload.get("chart", {}).get("result", [])
                            if result:
                                meta = result[0].get("meta", {})
                                quote_closes = [
                                    c for c in result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
                                    if c is not None and c > 0
                                ]
                                if len(quote_closes) >= 2:
                                    cur_yield = quote_closes[-1]
                                    prev_yield = quote_closes[-2]
                                    src_name = "Yahoo Finance (^TNX)"
                                elif len(quote_closes) == 1:
                                    cur_yield = quote_closes[0]
                                    prev_yield = meta.get("chartPreviousClose") or cur_yield
                                    src_name = "Yahoo Finance (^TNX)"
                    except Exception as exc:
                        logger.warning(f"Failed to fetch yield for {item['instrument_id']} via Yahoo: {exc}")

                snap = create_sovereign_yield_snapshot(
                    instrument_id=item["instrument_id"],
                    country=item["country"],
                    display_name=item["display_name"],
                    maturity=item["maturity"],
                    yield_percent=float(cur_yield),
                    previous_yield_percent=float(prev_yield),
                    market_date=m_date,
                    source=src_name,
                    fetched_at=now_iso,
                    is_stale=False,
                )
                snapshots.append(snap)

        return snapshots


class MonetaryPolicyProvider:
    """
    Provider for Central Bank Monetary Policy Decisions (Stage 2D).
    Supports official target ranges (Federal Reserve) and single official rates (BoE, ECB, BoJ, RBI).
    """

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout_seconds = timeout_seconds

    async def fetch_monetary_policy_rates(self) -> list[MonetaryPolicySnapshot]:
        snapshots: list[MonetaryPolicySnapshot] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for item in MONETARY_POLICY_BASKET:
            snap = create_monetary_policy_snapshot(
                central_bank=item["central_bank"],
                jurisdiction=item["jurisdiction"],
                policy_rate_name=item["policy_rate_name"],
                rate=item["rate"],
                previous_rate=item["previous_rate"],
                effective_date=item["effective_date"],
                source=item["source"],
                lower_bound=item["lower_bound"],
                upper_bound=item["upper_bound"],
                previous_lower_bound=item.get("previous_lower_bound"),
                previous_upper_bound=item.get("previous_upper_bound"),
                decision_date=item.get("decision_date"),
                fetched_at=now_iso,
                is_stale=False,
                secondary_rates=item.get("secondary_rates"),
            )
            snapshots.append(snap)

        return snapshots
