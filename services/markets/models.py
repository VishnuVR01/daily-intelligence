from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Literal, Optional

Direction = Literal["UP", "DOWN", "FLAT"]
AssetClass = Literal["EQUITY_INDEX", "ENERGY_FUTURES", "METALS_FUTURES", "EQUITY_PROXY", "FX", "SOVEREIGN_YIELD"]
PolicyAction = Literal["HIKE", "CUT", "HOLD", "OTHER", "UNKNOWN"]


@dataclass
class MarketSnapshot:
    region: str
    symbol: str
    display_name: str
    latest_close: float
    previous_close: float
    change_value: float
    change_percent: float
    direction: Direction
    market_date: str
    fetched_at: str
    source: str
    currency: Optional[str] = None
    is_stale: bool = False
    asset_class: AssetClass = "EQUITY_INDEX"
    unit: Optional[str] = None
    semantics_note: Optional[str] = None
    canonical_id: Optional[str] = None

    @staticmethod
    def calculate_direction(change_percent: float, threshold: float = 0.05) -> Direction:
        if change_percent > threshold:
            return "UP"
        elif change_percent < -threshold:
            return "DOWN"
        return "FLAT"


def create_market_snapshot(
    region: str,
    symbol: str,
    display_name: str,
    latest_close: float,
    previous_close: float,
    market_date: str,
    source: str = "Twelve Data",
    currency: Optional[str] = None,
    fetched_at: Optional[str] = None,
    is_stale: bool = False,
    flat_threshold_percent: float = 0.05,
    asset_class: AssetClass = "EQUITY_INDEX",
    unit: Optional[str] = None,
    semantics_note: Optional[str] = None,
    canonical_id: Optional[str] = None,
) -> MarketSnapshot:
    """
    Constructs a MarketSnapshot with safe change % calculation and direction determination.
    Handles zero previous_close safely.
    """
    if fetched_at is None:
        fetched_at = datetime.now(timezone.utc).isoformat()

    latest_close = round(float(latest_close), 4)
    previous_close = round(float(previous_close), 4)

    if previous_close <= 0 or latest_close <= 0:
        change_val = 0.0
        change_pct = 0.0
    else:
        change_val = latest_close - previous_close
        change_pct = ((latest_close - previous_close) / previous_close) * 100.0

    change_val = round(change_val, 4)
    change_pct = round(change_pct, 4)
    direction = MarketSnapshot.calculate_direction(change_pct, threshold=flat_threshold_percent)

    close_precision = 4 if latest_close < 20.0 else 2

    return MarketSnapshot(
        region=region,
        symbol=symbol,
        display_name=display_name,
        latest_close=round(latest_close, close_precision),
        previous_close=round(previous_close, close_precision),
        change_value=change_val,
        change_percent=change_pct,
        direction=direction,
        market_date=market_date,
        fetched_at=fetched_at,
        source=source,
        currency=currency,
        is_stale=is_stale,
        asset_class=asset_class,
        unit=unit,
        semantics_note=semantics_note,
        canonical_id=canonical_id,
    )


@dataclass
class SovereignYieldSnapshot:
    """
    Market-priced benchmark sovereign bond yield (Stage 2D).
    Yield changes are calculated in Basis Points (bp): 1.00 percentage point = 100 bp.
    """
    instrument_id: str
    country: str
    display_name: str
    maturity: str
    yield_percent: float
    previous_yield_percent: float
    change_basis_points: float
    direction: Direction
    market_date: str
    fetched_at: str
    source: str
    is_stale: bool = False
    unit: str = "% p.a."


def create_sovereign_yield_snapshot(
    instrument_id: str,
    country: str,
    display_name: str,
    maturity: str,
    yield_percent: float,
    previous_yield_percent: float,
    market_date: str,
    source: str = "Market Yield Data",
    fetched_at: Optional[str] = None,
    is_stale: bool = False,
    flat_threshold_bp: float = 0.5,
) -> SovereignYieldSnapshot:
    """
    Constructs a SovereignYieldSnapshot calculating change in basis points (bp).
    Example: 4.27% - 4.20% = +0.07 percentage points = +7 bp.
    """
    if fetched_at is None:
        fetched_at = datetime.now(timezone.utc).isoformat()

    cur_y = round(float(yield_percent), 3)
    prev_y = round(float(previous_yield_percent), 3)
    change_bp = round((cur_y - prev_y) * 100.0, 1)

    if change_bp > flat_threshold_bp:
        direction: Direction = "UP"
    elif change_bp < -flat_threshold_bp:
        direction: Direction = "DOWN"
    else:
        direction: Direction = "FLAT"

    return SovereignYieldSnapshot(
        instrument_id=instrument_id,
        country=country,
        display_name=display_name,
        maturity=maturity,
        yield_percent=cur_y,
        previous_yield_percent=prev_y,
        change_basis_points=change_bp,
        direction=direction,
        market_date=market_date,
        fetched_at=fetched_at,
        source=source,
        is_stale=is_stale,
        unit="% p.a.",
    )


@dataclass
class MonetaryPolicySnapshot:
    """
    Institutional monetary policy rate decision snapshot (Stage 2D).
    Supports single official rates (e.g. Bank Rate, Repo Rate) as well as target ranges (Fed Funds).
    """
    central_bank: str
    jurisdiction: str
    policy_rate_name: str
    rate: Optional[float]
    lower_bound: Optional[float]
    upper_bound: Optional[float]
    effective_date: str
    decision_date: Optional[str]
    change_basis_points: float
    action: PolicyAction
    source: str
    fetched_at: str
    is_stale: bool = False
    secondary_rates: Optional[Dict[str, float]] = None


def create_monetary_policy_snapshot(
    central_bank: str,
    jurisdiction: str,
    policy_rate_name: str,
    rate: Optional[float],
    previous_rate: Optional[float],
    effective_date: str,
    source: str,
    lower_bound: Optional[float] = None,
    upper_bound: Optional[float] = None,
    previous_lower_bound: Optional[float] = None,
    previous_upper_bound: Optional[float] = None,
    decision_date: Optional[str] = None,
    fetched_at: Optional[str] = None,
    is_stale: bool = False,
    secondary_rates: Optional[Dict[str, float]] = None,
) -> MonetaryPolicySnapshot:
    """
    Constructs a MonetaryPolicySnapshot cleanly handling both single rates and target ranges.
    Calculates rate change in basis points and assigns action (HIKE, CUT, HOLD).
    """
    if fetched_at is None:
        fetched_at = datetime.now(timezone.utc).isoformat()

    # Determine change in basis points
    if lower_bound is not None and upper_bound is not None:
        if previous_lower_bound is not None:
            change_bp = round((lower_bound - previous_lower_bound) * 100.0, 1)
        else:
            change_bp = 0.0
    elif rate is not None and previous_rate is not None:
        change_bp = round((rate - previous_rate) * 100.0, 1)
    else:
        change_bp = 0.0

    if change_bp > 0.5:
        action: PolicyAction = "HIKE"
    elif change_bp < -0.5:
        action: PolicyAction = "CUT"
    else:
        action: PolicyAction = "HOLD"

    return MonetaryPolicySnapshot(
        central_bank=central_bank,
        jurisdiction=jurisdiction,
        policy_rate_name=policy_rate_name,
        rate=round(float(rate), 2) if rate is not None else None,
        lower_bound=round(float(lower_bound), 2) if lower_bound is not None else None,
        upper_bound=round(float(upper_bound), 2) if upper_bound is not None else None,
        effective_date=effective_date,
        decision_date=decision_date,
        change_basis_points=change_bp,
        action=action,
        source=source,
        fetched_at=fetched_at,
        is_stale=is_stale,
        secondary_rates=secondary_rates,
    )
