import logging
from ingestion.collectors import CollectionStatus, CollectorResult
from ingestion.rss import fetch_feed

logger = logging.getLogger(__name__)


def collect_rss(feed_url: str | None, source_name: str) -> CollectorResult:
    if not feed_url:
        return CollectorResult(
            status=CollectionStatus.FAILED,
            error_message="Missing feed URL for RSS source",
        )
    try:
        items = fetch_feed(feed_url, source_name)
        if len(items) == 0:
            return CollectorResult(status=CollectionStatus.EMPTY, items=[])
        return CollectorResult(status=CollectionStatus.OK, items=items)
    except Exception as exc:
        logger.warning(f"Error fetching RSS feed for '{source_name}': {exc}")
        return CollectorResult(
            status=CollectionStatus.FAILED,
            error_message=str(exc),
        )
