from ingestion.collectors import CollectionStatus, CollectorResult


def collect_html(website_url: str | None, source_name: str) -> CollectorResult:
    """HTML collector stub - HTML scraping is not implemented yet."""
    return CollectorResult(
        status=CollectionStatus.SKIPPED_UNSUPPORTED,
        items=[],
        error_message="HTML collection is not supported yet",
    )
