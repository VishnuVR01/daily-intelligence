"""
Source Health Service for Daily Intelligence.

Calculates observable source health status from existing database models
(Source, Article) and live feed collection checks without database migrations.
"""

from datetime import datetime, timezone, timedelta
from typing import Any
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Source, Article
from ingestion.collectors import CollectionStatus
from ingestion.collectors.rss_collector import collect_rss

logger = logging.getLogger("services.source_health")

DEFAULT_STALE_THRESHOLD_DAYS = 7


def calculate_source_status(
    active: bool,
    is_rss_compatible: bool,
    feed_url: str | None,
    collection_status: CollectionStatus | str | None,
    items_count: int,
    newest_article_at: datetime | None,
    stale_days: int = DEFAULT_STALE_THRESHOLD_DAYS,
    now: datetime | None = None,
) -> str:
    """
    Deterministic rules for source status:
    - DISABLED: source not active
    - FAILED: HTTP/Parser/URL error or explicitly failed collection
    - EMPTY: reachable but 0 items in feed
    - STALE: reachable with items, but newest article is older than stale_days
    - HEALTHY: reachable with items within stale_days
    """
    if not active:
        return "DISABLED"

    if not is_rss_compatible or not feed_url:
        return "FAILED"

    status_str = collection_status.value if isinstance(collection_status, CollectionStatus) else str(collection_status or "")

    if status_str in ("FAILED", "UNKNOWN_TYPE"):
        return "FAILED"

    if status_str == "EMPTY" or items_count == 0:
        return "EMPTY"

    # Evaluate freshness if newest article timestamp exists
    if newest_article_at:
        now_utc = now or datetime.now(timezone.utc)
        if newest_article_at.tzinfo is None:
            newest_article_at = newest_article_at.replace(tzinfo=timezone.utc)
        
        age = now_utc - newest_article_at
        if age > timedelta(days=stale_days):
            return "STALE"

    return "HEALTHY"


def get_source_health(db: Session, stale_days: int = DEFAULT_STALE_THRESHOLD_DAYS, live_check: bool = False) -> dict[str, Any]:
    """
    Returns observable health status for all configured sources.
    If live_check=True, fetches active RSS feeds live to determine current status.
    Otherwise uses existing database metadata and article timestamps.
    """
    sources = db.query(Source).order_by(Source.name.asc()).all()
    now_utc = datetime.now(timezone.utc)

    results = []
    summary_counts = {
        "total_configured": len(sources),
        "active": 0,
        "healthy": 0,
        "stale": 0,
        "empty": 0,
        "failed": 0,
        "disabled": 0,
    }

    for src in sources:
        # Get newest article from DB for this source
        newest_article = (
            db.query(Article)
            .filter(Article.source_id == src.id)
            .order_by(func.coalesce(Article.published_at, Article.collected_at).desc())
            .first()
        )
        newest_article_at = (
            (newest_article.published_at or newest_article.collected_at)
            if newest_article
            else None
        )
        last_collection_at = (
            newest_article.collected_at if newest_article else None
        )

        stype = (src.source_type or "rss").lower()
        is_rss = stype in (
            "rss", "news_feed", "institutional_research", "central_bank",
            "company_primary", "commodity_research", "energy_organization", "regulator"
        )

        if not src.active:
            status = "DISABLED"
            reachable = False
            items_discovered = 0
            error_msg = "Source is inactive"
        elif live_check and is_rss and src.feed_url:
            res = collect_rss(src.feed_url, src.name)
            items_discovered = len(res.items)
            reachable = (res.status != CollectionStatus.FAILED)
            error_msg = res.error_message
            status = calculate_source_status(
                active=True,
                is_rss_compatible=is_rss,
                feed_url=src.feed_url,
                collection_status=res.status,
                items_count=items_discovered,
                newest_article_at=newest_article_at,
                stale_days=stale_days,
                now=now_utc,
            )
        else:
            # DB-based health computation
            reachable = is_rss and bool(src.feed_url)
            article_count = (
                db.query(func.count(Article.id))
                .filter(Article.source_id == src.id)
                .scalar()
                or 0
            )
            items_discovered = article_count
            error_msg = None if reachable else f"Unsupported source type '{stype}' or missing feed URL"
            
            if not is_rss or not src.feed_url:
                status = "FAILED"
            elif article_count == 0:
                status = "EMPTY"
            else:
                status = calculate_source_status(
                    active=True,
                    is_rss_compatible=is_rss,
                    feed_url=src.feed_url,
                    collection_status=CollectionStatus.OK,
                    items_count=article_count,
                    newest_article_at=newest_article_at,
                    stale_days=stale_days,
                    now=now_utc,
                )

        if src.active:
            summary_counts["active"] += 1

        if status == "HEALTHY":
            summary_counts["healthy"] += 1
        elif status == "STALE":
            summary_counts["stale"] += 1
        elif status == "EMPTY":
            summary_counts["empty"] += 1
        elif status == "FAILED":
            summary_counts["failed"] += 1
        elif status == "DISABLED":
            summary_counts["disabled"] += 1

        results.append({
            "source_id": src.id,
            "name": src.name,
            "status": status,
            "reachable": reachable,
            "items_discovered": items_discovered,
            "newest_article": newest_article_at.isoformat() if newest_article_at else None,
            "last_collection": last_collection_at.isoformat() if last_collection_at else None,
            "error": error_msg,
        })

    return {
        "generated_at": now_utc.isoformat(),
        "summary": summary_counts,
        "sources": results,
    }
