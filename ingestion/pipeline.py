from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import Article, Source
from ingestion.collectors import CollectionStatus
from ingestion.collectors.html_collector import collect_html
from ingestion.collectors.rss_collector import collect_rss
from ingestion.dedupe import title_fingerprint
from ingestion.normalize import canonicalize_url, clean_summary_text

logger = logging.getLogger("ingestion.pipeline")


@dataclass
class SourceResult:
    source_name: str
    source_type: str
    fetched: int = 0
    new: int = 0
    duplicates: int = 0
    status: str = "OK"
    error_message: str | None = None


@dataclass
class IngestionSummary:
    active_sources_processed: int = 0
    inactive_sources_skipped: int = 0
    unsupported_sources: int = 0
    healthy_feeds: int = 0
    empty_feeds: int = 0
    failed_feeds: int = 0
    articles_fetched: int = 0
    new_articles: int = 0
    duplicates_skipped: int = 0
    source_results: list[SourceResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_sources_processed": self.active_sources_processed,
            "inactive_sources_skipped": self.inactive_sources_skipped,
            "unsupported_sources": self.unsupported_sources,
            "healthy_feeds": self.healthy_feeds,
            "empty_feeds": self.empty_feeds,
            "failed_feeds": self.failed_feeds,
            "articles_fetched": self.articles_fetched,
            "new_articles": self.new_articles,
            "duplicates_skipped": self.duplicates_skipped,
        }


def run_ingestion_pipeline(session: Session) -> IngestionSummary:
    summary = IngestionSummary()

    # Query all sources ordered by name
    all_sources = session.query(Source).order_by(Source.name.asc()).all()

    logger.info(f"Starting ingestion pipeline for {len(all_sources)} configured source(s)...")

    for source in all_sources:
        if not source.active:
            summary.inactive_sources_skipped += 1
            summary.source_results.append(
                SourceResult(
                    source_name=source.name,
                    source_type=source.source_type or "rss",
                    fetched=0,
                    new=0,
                    duplicates=0,
                    status=CollectionStatus.SKIPPED_INACTIVE.value,
                )
            )
            logger.info(f"Source '{source.name}' is INACTIVE. Skipped.")
            continue

        summary.active_sources_processed += 1
        stype = (source.source_type or "rss").lower()
        is_rss_compatible = stype in (
            "rss", "news_feed", "institutional_research", "central_bank",
            "company_primary", "commodity_research", "energy_organization", "regulator"
        )

        if is_rss_compatible and source.feed_url:
            res = collect_rss(source.feed_url, source.name)

            if res.status == CollectionStatus.OK:
                summary.healthy_feeds += 1
                fetched = len(res.items)
                new_count = 0
                dup_count = 0
                seen_urls_in_batch: set[str] = set()

                try:
                    for item in res.items:
                        if not item.url or not item.title:
                            continue

                        canonical_url = canonicalize_url(item.url)
                        fingerprint = title_fingerprint(item.title)

                        if canonical_url in seen_urls_in_batch:
                            dup_count += 1
                            continue

                        existing = (
                            session.query(Article)
                            .filter(Article.canonical_url == canonical_url)
                            .first()
                        )

                        if existing:
                            dup_count += 1
                        else:
                            seen_urls_in_batch.add(canonical_url)
                            new_article = Article(
                                source_id=source.id,
                                title=item.title,
                                canonical_url=canonical_url,
                                published_at=item.published_at,
                                collected_at=datetime.now(timezone.utc),
                                raw_summary=clean_summary_text(item.summary),
                                title_fingerprint=fingerprint,
                            )
                            session.add(new_article)
                            new_count += 1

                    session.commit()

                    summary.articles_fetched += fetched
                    summary.new_articles += new_count
                    summary.duplicates_skipped += dup_count

                    summary.source_results.append(
                        SourceResult(
                            source_name=source.name,
                            source_type=stype,
                            fetched=fetched,
                            new=new_count,
                            duplicates=dup_count,
                            status=CollectionStatus.OK.value,
                        )
                    )
                    logger.info(
                        f"SUCCESS: '{source.name}' (rss) | Fetched: {fetched} | New: {new_count} | Duplicates: {dup_count}"
                    )

                except Exception as exc:
                    session.rollback()
                    summary.healthy_feeds -= 1
                    summary.failed_feeds += 1
                    summary.source_results.append(
                        SourceResult(
                            source_name=source.name,
                            source_type=stype,
                            fetched=0,
                            new=0,
                            duplicates=0,
                            status=CollectionStatus.FAILED.value,
                            error_message=str(exc),
                        )
                    )
                    logger.error(f"FAILED saving articles for '{source.name}': {exc}")

            elif res.status == CollectionStatus.EMPTY:
                summary.empty_feeds += 1
                summary.source_results.append(
                    SourceResult(
                        source_name=source.name,
                        source_type=stype,
                        fetched=0,
                        new=0,
                        duplicates=0,
                        status=CollectionStatus.EMPTY.value,
                    )
                )
                logger.info(f"EMPTY: '{source.name}' (rss) returned 0 items.")

            else:  # FAILED
                summary.failed_feeds += 1
                summary.source_results.append(
                    SourceResult(
                        source_name=source.name,
                        source_type=stype,
                        fetched=0,
                        new=0,
                        duplicates=0,
                        status=CollectionStatus.FAILED.value,
                        error_message=res.error_message,
                    )
                )
                logger.warning(f"FAILED: '{source.name}' (rss) - {res.error_message}")

        elif stype in ("html", "social_api", "github_releases"):
            summary.unsupported_sources += 1
            error_msg = f"Source type '{stype}' is prepared for future integration and not active in standard RSS collection"
            if stype == "html":
                res = collect_html(source.website_url, source.name)
                error_msg = res.error_message or error_msg

            summary.source_results.append(
                SourceResult(
                    source_name=source.name,
                    source_type=stype,
                    fetched=0,
                    new=0,
                    duplicates=0,
                    status=CollectionStatus.SKIPPED_UNSUPPORTED.value,
                    error_message=error_msg,
                )
            )
            logger.info(f"UNSUPPORTED: '{source.name}' ({stype}) skipped.")

        else:
            summary.unsupported_sources += 1
            summary.source_results.append(
                SourceResult(
                    source_name=source.name,
                    source_type=stype,
                    fetched=0,
                    new=0,
                    duplicates=0,
                    status=CollectionStatus.UNKNOWN_TYPE.value,
                    error_message=f"Unknown source type '{stype}'",
                )
            )
            logger.warning(f"UNKNOWN_TYPE: '{source.name}' has source_type '{stype}'.")

    logger.info("Ingestion pipeline execution complete.")
    return summary
