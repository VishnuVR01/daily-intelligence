from dataclasses import dataclass
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Any, Literal, Optional

SessionState = Literal["OPEN", "CLOSED", "PRE_MARKET", "POST_MARKET"]

SESSION_DISCLAIMER = (
    "Session status currently reflects regular trading hours and does not yet include full exchange-holiday calendars."
)

EXCHANGE_CONFIGS: Dict[str, Dict[str, Any]] = {
    "United States": {
        "symbol": "SPX",
        "tz": "America/New_York",
        "weekdays": [0, 1, 2, 3, 4],
        "open_time": time(9, 30),
        "close_time": time(16, 0),
        "pre_open_time": time(8, 30),
        "post_close_time": time(17, 0),
    },
    "United Kingdom": {
        "symbol": "FTSE",
        "tz": "Europe/London",
        "weekdays": [0, 1, 2, 3, 4],
        "open_time": time(8, 0),
        "close_time": time(16, 30),
        "pre_open_time": time(7, 0),
        "post_close_time": time(17, 30),
    },
    "India": {
        "symbol": "NSEI",
        "tz": "Asia/Kolkata",
        "weekdays": [0, 1, 2, 3, 4],
        "open_time": time(9, 15),
        "close_time": time(15, 30),
        "pre_open_time": time(9, 0),
        "post_close_time": time(16, 0),
    },
    "Japan": {
        "symbol": "N225",
        "tz": "Asia/Tokyo",
        "weekdays": [0, 1, 2, 3, 4],
        # Nikkei RTH: 09:00 - 11:30 & 12:30 - 15:30
        "sessions": [
            (time(9, 0), time(11, 30)),
            (time(12, 30), time(15, 30)),
        ],
        "pre_open_time": time(8, 0),
        "post_close_time": time(16, 30),
    },
    "Europe": {
        "symbol": "STOXX",
        "tz": "Europe/Paris",
        "weekdays": [0, 1, 2, 3, 4],
        "open_time": time(9, 0),
        "close_time": time(17, 30),
        "pre_open_time": time(8, 0),
        "post_close_time": time(18, 30),
    },
    "China": {
        "symbol": "399972",
        "tz": "Asia/Shanghai",
        "weekdays": [0, 1, 2, 3, 4],
        # CSI 300 RTH: 09:30 - 11:30 & 13:00 - 15:00
        "sessions": [
            (time(9, 30), time(11, 30)),
            (time(13, 0), time(15, 0)),
        ],
        "pre_open_time": time(9, 0),
        "post_close_time": time(15, 30),
    },
}


@dataclass
class MarketSessionStatus:
    region: str
    symbol: str
    state: SessionState
    display_label: str
    dot_class: str  # "open" (green), "closed" (muted), "prepost" (amber)
    exchange_tz: str
    local_time_str: str
    disclaimer: str = SESSION_DISCLAIMER


def get_market_session_status(
    region_or_symbol: str,
    at_time: Optional[datetime] = None,
) -> MarketSessionStatus:
    """
    Calculates deterministic market trading session status for a given region or symbol.
    Uses exchange local time and regular trading hours.
    """
    if at_time is None:
        at_time = datetime.now(timezone.utc)
    elif at_time.tzinfo is None:
        at_time = at_time.replace(tzinfo=timezone.utc)

    # Find matching config by region or symbol
    matched_region = None
    config = None

    for r_name, c_data in EXCHANGE_CONFIGS.items():
        if r_name.lower() == region_or_symbol.lower() or c_data["symbol"].lower() == region_or_symbol.lower():
            matched_region = r_name
            config = c_data
            break

    if not config or not matched_region:
        # Default fallback
        return MarketSessionStatus(
            region=region_or_symbol,
            symbol="UNKNOWN",
            state="CLOSED",
            display_label="CLOSED",
            dot_class="closed",
            exchange_tz="UTC",
            local_time_str=at_time.strftime("%H:%M %Z"),
        )

    tz_name = config["tz"]
    try:
        ex_tz = ZoneInfo(tz_name)
    except Exception:
        ex_tz = timezone.utc

    local_dt = at_time.astimezone(ex_tz)
    local_time = local_dt.time()
    weekday = local_dt.weekday()

    # Weekend check
    if weekday not in config["weekdays"]:
        return MarketSessionStatus(
            region=matched_region,
            symbol=config["symbol"],
            state="CLOSED",
            display_label="CLOSED",
            dot_class="closed",
            exchange_tz=tz_name,
            local_time_str=local_dt.strftime("%H:%M %Z"),
        )

    # Multi-session markets (Japan, China)
    if "sessions" in config:
        is_open = any(start <= local_time <= end for start, end in config["sessions"])
        if is_open:
            return MarketSessionStatus(
                region=matched_region,
                symbol=config["symbol"],
                state="OPEN",
                display_label="OPEN",
                dot_class="open",
                exchange_tz=tz_name,
                local_time_str=local_dt.strftime("%H:%M %Z"),
            )
    else:
        open_t = config["open_time"]
        close_t = config["close_time"]
        if open_t <= local_time <= close_t:
            return MarketSessionStatus(
                region=matched_region,
                symbol=config["symbol"],
                state="OPEN",
                display_label="OPEN",
                dot_class="open",
                exchange_tz=tz_name,
                local_time_str=local_dt.strftime("%H:%M %Z"),
            )

    # Pre-market / After-hours check
    pre_t = config.get("pre_open_time")
    post_t = config.get("post_close_time")
    open_t = config.get("open_time") or (config["sessions"][0][0] if "sessions" in config else None)
    close_t = config.get("close_time") or (config["sessions"][-1][1] if "sessions" in config else None)

    if pre_t and open_t and pre_t <= local_time < open_t:
        return MarketSessionStatus(
            region=matched_region,
            symbol=config["symbol"],
            state="PRE_MARKET",
            display_label="PRE-MARKET",
            dot_class="prepost",
            exchange_tz=tz_name,
            local_time_str=local_dt.strftime("%H:%M %Z"),
        )

    if post_t and close_t and close_t < local_time <= post_t:
        return MarketSessionStatus(
            region=matched_region,
            symbol=config["symbol"],
            state="POST_MARKET",
            display_label="AFTER-HOURS",
            dot_class="prepost",
            exchange_tz=tz_name,
            local_time_str=local_dt.strftime("%H:%M %Z"),
        )

    # Otherwise CLOSED
    return MarketSessionStatus(
        region=matched_region,
        symbol=config["symbol"],
        state="CLOSED",
        display_label="CLOSED",
        dot_class="closed",
        exchange_tz=tz_name,
        local_time_str=local_dt.strftime("%H:%M %Z"),
    )
