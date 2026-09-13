import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from app.config import get_settings

BASE_DIR = Path(__file__).resolve().parent.parent
QUOTES_FILE = BASE_DIR / "data" / "quotes.json"

_cached_quotes: list[Dict[str, Any]] = []


def load_quotes() -> list[Dict[str, Any]]:
    """Loads curated verified quotes from local quotes.json."""
    global _cached_quotes
    if _cached_quotes:
        return _cached_quotes

    if not QUOTES_FILE.exists():
        return [
            {
                "quote": "An investment in knowledge pays the best interest.",
                "author": "Benjamin Franklin",
                "theme": "intelligence",
                "verified": True,
                "reference": "Poor Richard's Almanack",
            }
        ]

    try:
        with open(QUOTES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            _cached_quotes = [q for q in data if q.get("verified", False)]
            return _cached_quotes
    except Exception:
        return [
            {
                "quote": "An investment in knowledge pays the best interest.",
                "author": "Benjamin Franklin",
                "theme": "intelligence",
                "verified": True,
                "reference": "Poor Richard's Almanack",
            }
        ]


def get_daily_quote(target_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Returns a single verified quote deterministically selected for target_date.
    Guarantees the exact same quote is returned for any given calendar date across refreshes.
    """
    quotes = load_quotes()
    if not quotes:
        return {
            "quote": "An investment in knowledge pays the best interest.",
            "author": "Benjamin Franklin",
            "theme": "intelligence",
            "verified": True,
            "reference": "Poor Richard's Almanack",
        }

    if target_date is None:
        try:
            tz = ZoneInfo(get_settings().app_timezone)
            target_date = datetime.now(tz).date()
        except Exception:
            target_date = date.today()

    date_str = target_date.isoformat()
    # Compute deterministic index using SHA-256 hash of date string
    hash_int = int(hashlib.sha256(date_str.encode("utf-8")).hexdigest(), 16)
    quote_index = hash_int % len(quotes)
    return quotes[quote_index]
