import html
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from bs4 import BeautifulSoup

TRACKING_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
}


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    filtered_query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in TRACKING_KEYS
    ]
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/") or "/",
            urlencode(filtered_query, doseq=True),
            "",
        )
    )


def clean_summary_text(text: str | None) -> str | None:
    if not text:
        return None
    # Remove HTML tags using BeautifulSoup
    soup = BeautifulSoup(text, "html.parser")
    cleaned = soup.get_text(separator=" ")
    # Decode HTML entities (e.g. &nbsp;, &amp;, &quot;)
    cleaned = html.unescape(cleaned)
    # Replace non-breaking spaces and collapse extra whitespace/newlines
    cleaned = cleaned.replace("\xa0", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if cleaned else None
