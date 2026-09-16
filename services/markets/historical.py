from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import List, Optional, Tuple
import httpx

from services.markets.provider import INDEX_BASKET, CROSS_ASSET_BASKET

logger = logging.getLogger(__name__)


@dataclass
class HistoricalPoint:
    date_str: str
    close: float


@dataclass
class HistoricalSeries:
    region: str
    symbol: str
    display_name: str
    daily_points: List[HistoricalPoint]
    high_52w: float
    low_52w: float
    distance_from_52w_high: float
    ytd_change_percent: float


def compute_historical_statistics(
    points: List[HistoricalPoint],
    latest_close: float,
) -> Tuple[float, float, float, float]:
    """
    Computes 52W High, 52W Low, Distance from 52W High %, and YTD Change %
    from a chronological list of HistoricalPoint objects.
    """
    if not points:
        return latest_close, latest_close, 0.0, 0.0

    closes = [p.close for p in points if p.close > 0]
    if not closes:
        return latest_close, latest_close, 0.0, 0.0

    high_52w = round(max(closes), 2)
    low_52w = round(min(closes), 2)

    # Distance from 52W High %
    if high_52w > 0:
        distance_from_high = round(((latest_close - high_52w) / high_52w) * 100.0, 2)
    else:
        distance_from_high = 0.0

    # YTD Change % (First valid close point on or after Jan 1 of current year)
    now_year = str(datetime.now(timezone.utc).year)
    ytd_first_point = None

    for p in points:
        if p.date_str.startswith(now_year) and p.close > 0:
            ytd_first_point = p
            break

    if ytd_first_point and ytd_first_point.close > 0:
        ytd_change = round(((latest_close - ytd_first_point.close) / ytd_first_point.close) * 100.0, 2)
    else:
        # Fallback to first available point in series if YTD point not found
        first_close = points[0].close
        ytd_change = round(((latest_close - first_close) / first_close) * 100.0, 2) if first_close > 0 else 0.0

    return high_52w, low_52w, distance_from_high, ytd_change


async def fetch_historical_series_yahoo(
    identifier: str,
    timeout_seconds: float = 10.0,
) -> Optional[HistoricalSeries]:
    """
    Fetches 1Y daily close historical data from Yahoo Finance chart endpoint for specified region or canonical ID.
    Deduplicates dates, formats chronologically, and calculates 52W High/Low and YTD statistics.
    """
    all_baskets = INDEX_BASKET + CROSS_ASSET_BASKET
    id_lower = identifier.lower()

    target = next((item for item in all_baskets if (
        item.get("region", "").lower() == id_lower or
        item.get("canonical_id", "").lower() == id_lower or
        item.get("twelve_symbol", "").lower() == id_lower or
        item.get("display_name", "").lower() == id_lower or
        item.get("yahoo_symbol", "").lower() == id_lower
    )), None)

    if not target:
        return None

    symbol = target["yahoo_symbol"]
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1y"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        async with httpx.AsyncClient(headers=headers, timeout=timeout_seconds) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.warning(f"Yahoo Finance historical fetch returned HTTP {resp.status_code} for {symbol}")
                return None
            payload = resp.json()
    except Exception as exc:
        logger.error(f"Error fetching historical series for {symbol}: {exc}")
        return None

    result = payload.get("chart", {}).get("result", [])
    if not result:
        return None

    res = result[0]
    timestamps = res.get("timestamp", [])
    quote = res.get("indicators", {}).get("quote", [{}])[0]
    closes = quote.get("close", [])

    if not timestamps or not closes:
        return None

    # Construct chronological points, deduplicating dates
    seen_dates = set()
    raw_points: List[HistoricalPoint] = []
    now_utc = datetime.now(timezone.utc)

    for ts, c in zip(timestamps, closes):
        if ts is None or c is None or c <= 0:
            continue
        dt = datetime.fromtimestamp(ts, timezone.utc)
        if dt > now_utc:
            continue
        date_str = dt.strftime("%Y-%m-%d")
        if date_str not in seen_dates:
            seen_dates.add(date_str)
            raw_points.append(HistoricalPoint(date_str=date_str, close=round(float(c), 2)))

    if not raw_points or len(raw_points) < 2:
        logger.info(f"Insufficient historical data points ({len(raw_points)}) for {symbol}")
        return None

    # Ensure chronological order
    raw_points.sort(key=lambda p: p.date_str)
    latest_close = raw_points[-1].close

    high_52w, low_52w, dist_high, ytd_change = compute_historical_statistics(raw_points, latest_close)

    return HistoricalSeries(
        region=target["region"],
        symbol=target["twelve_symbol"],
        display_name=target["display_name"],
        daily_points=raw_points,
        high_52w=high_52w,
        low_52w=low_52w,
        distance_from_52w_high=dist_high,
        ytd_change_percent=ytd_change,
    )


def generate_svg_mini_chart(
    points: List[HistoricalPoint],
    width: int = 500,
    height: int = 140,
    padding: int = 15,
) -> str:
    """
    Generates a server-rendered SVG line chart displaying trend for daily points.
    Clean vector path with Warm Editorial styling (accent stroke, gradient fill).
    """
    if not points or len(points) < 2:
        return f'<svg viewBox="0 0 {width} {height}" class="mini-chart-svg"><text x="{width//2}" y="{height//2}" text-anchor="middle" fill="#888" font-size="13">Historical series temporarily unavailable.</text></svg>'

    closes = [p.close for p in points]
    min_c = min(closes)
    max_c = max(closes)
    val_range = max_c - min_c if max_c != min_c else 1.0

    usable_w = width - (2 * padding)
    usable_h = height - (2 * padding)

    n_points = len(points)
    step_x = usable_w / (n_points - 1)

    coords = []
    for idx, c in enumerate(closes):
        x = padding + (idx * step_x)
        # Invert y for SVG space (0 at top)
        y = (padding + usable_h) - ((c - min_c) / val_range * usable_h)
        coords.append((round(x, 1), round(y, 1)))

    path_d = f"M {coords[0][0]} {coords[0][1]}"
    for x, y in coords[1:]:
        path_d += f" L {x} {y}"

    # Closed polygon area path for fill
    area_d = f"{path_d} L {coords[-1][0]} {height - padding} L {coords[0][0]} {height - padding} Z"

    start_date = points[0].date_str
    end_date = points[-1].date_str
    first_close = points[0].close
    last_close = points[-1].close

    is_up = last_close >= first_close
    stroke_color = "#2E5942" if is_up else "#C76A4C"  # Green or Warm Editorial Terracotta
    fill_color = "rgba(46, 89, 66, 0.12)" if is_up else "rgba(199, 106, 76, 0.12)"

    svg = f'''<svg viewBox="0 0 {width} {height}" class="mini-chart-svg" preserveAspectRatio="none" role="img" aria-label="1Y Trend Chart from {start_date} to {end_date}">
  <defs>
    <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{stroke_color}" stop-opacity="0.25"/>
      <stop offset="100%" stop-color="{stroke_color}" stop-opacity="0.0"/>
    </linearGradient>
  </defs>
  <path d="{area_d}" fill="url(#chartGrad)"/>
  <path d="{path_d}" fill="none" stroke="{stroke_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>'''
    return svg
