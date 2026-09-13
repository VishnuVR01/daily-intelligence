from datetime import date, timedelta
from services.quotes import get_daily_quote, load_quotes


def test_quotes_file_valid_structure():
    quotes = load_quotes()
    assert len(quotes) >= 10
    for q in quotes:
        assert "quote" in q and isinstance(q["quote"], str) and len(q["quote"]) > 0
        assert "author" in q and isinstance(q["author"], str) and len(q["author"]) > 0
        assert "theme" in q and isinstance(q["theme"], str)
        assert q.get("verified") is True


def test_daily_quote_determinism():
    today = date.today()
    quote1 = get_daily_quote(today)
    quote2 = get_daily_quote(today)
    assert quote1["quote"] == quote2["quote"]
    assert quote1["author"] == quote2["author"]

    # Different dates should produce deterministic quotes
    tomorrow = today + timedelta(days=1)
    quote_tomorrow1 = get_daily_quote(tomorrow)
    quote_tomorrow2 = get_daily_quote(tomorrow)
    assert quote_tomorrow1["quote"] == quote_tomorrow2["quote"]
