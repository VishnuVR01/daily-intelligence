from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import feedparser

import ssl
import urllib.request

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class FeedItem:
    title: str
    url: str
    published_at: datetime | None
    summary: str | None
    source_name: str


def fetch_feed(feed_url: str, source_name: str) -> list[FeedItem]:
    feed = None
    try:
        req = urllib.request.Request(feed_url, headers={"User-Agent": DEFAULT_USER_AGENT})
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=12) as response:
            feed = feedparser.parse(response.read())
    except Exception:
        feed = feedparser.parse(
            feed_url,
            request_headers={"User-Agent": DEFAULT_USER_AGENT},
        )

    items: list[FeedItem] = []

    for entry in feed.entries:
        title = (getattr(entry, "title", "") or "").strip()
        if not title:
            continue

        # Rule Part 2: URL extraction order
        # 1. entry.link when valid
        # 2. entry.guid / entry.id when it is a permalink (http:// or https://)
        # 3. otherwise reject safely
        link = (getattr(entry, "link", "") or "").strip()
        guid = (getattr(entry, "guid", "") or getattr(entry, "id", "") or "").strip()

        url: str | None = None
        if link and (link.startswith("http://") or link.startswith("https://")):
            url = link
        elif guid and (guid.startswith("http://") or guid.startswith("https://")):
            url = guid

        if not url:
            continue

        published_at = None
        published_struct = getattr(entry, "published_parsed", None) or getattr(
            entry, "updated_parsed", None
        )
        if published_struct:
            try:
                published_at = datetime(*published_struct[:6], tzinfo=timezone.utc)
            except Exception:
                published_at = None

        items.append(
            FeedItem(
                title=title,
                url=url,
                published_at=published_at,
                summary=getattr(entry, "summary", None),
                source_name=source_name,
            )
        )

    return items
