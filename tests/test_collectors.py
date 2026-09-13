from datetime import datetime, timezone
from unittest.mock import patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Source
from ingestion.collectors import CollectionStatus
from ingestion.collectors.html_collector import collect_html
from ingestion.collectors.rss_collector import collect_rss
from ingestion.pipeline import run_ingestion_pipeline
from ingestion.rss import FeedItem


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_rss_collector_ok_empty_and_failed():
    # Test OK status
    with patch("ingestion.collectors.rss_collector.fetch_feed") as mock_fetch:
        mock_fetch.return_value = [
            FeedItem("Title 1", "https://ex.com/1", datetime.now(timezone.utc), "Summary", "Source 1")
        ]
        res_ok = collect_rss("https://ex.com/rss", "Source 1")
        assert res_ok.status == CollectionStatus.OK
        assert len(res_ok.items) == 1

    # Test EMPTY status
    with patch("ingestion.collectors.rss_collector.fetch_feed") as mock_fetch:
        mock_fetch.return_value = []
        res_empty = collect_rss("https://ex.com/rss", "Source 1")
        assert res_empty.status == CollectionStatus.EMPTY
        assert len(res_empty.items) == 0

    # Test FAILED status
    with patch("ingestion.collectors.rss_collector.fetch_feed") as mock_fetch:
        mock_fetch.side_effect = Exception("HTTP 500 Server Error")
        res_failed = collect_rss("https://ex.com/rss", "Source 1")
        assert res_failed.status == CollectionStatus.FAILED
        assert "HTTP 500" in res_failed.error_message


def test_html_collector_returns_skipped_unsupported():
    res = collect_html("https://blog.google/", "Google Blog")
    assert res.status == CollectionStatus.SKIPPED_UNSUPPORTED
    assert len(res.items) == 0
    assert "HTML collection is not supported" in res.error_message


def test_pipeline_routing_and_status_classifications(db_session):
    # Setup sources with different source_types and active states
    s_rss_ok = Source(name="RSS OK Feed", feed_url="https://ok.com/rss", source_type="rss", active=True)
    s_rss_empty = Source(name="RSS Empty Feed", feed_url="https://empty.com/rss", source_type="rss", active=True)
    s_html_inactive = Source(name="Google Blog HTML", website_url="https://blog.google", source_type="html", active=False)
    s_html_active = Source(name="Active HTML Blog", website_url="https://html.com", source_type="html", active=True)
    s_unknown = Source(name="Custom Source", feed_url="https://custom.com", source_type="custom_type", active=True)

    db_session.add_all([s_rss_ok, s_rss_empty, s_html_inactive, s_html_active, s_unknown])
    db_session.commit()

    def mock_fetch(url, name):
        if "ok.com" in url:
            return [FeedItem("Story 1", "https://ok.com/s1", datetime.now(timezone.utc), "Sum", name)]
        return []

    with patch("ingestion.collectors.rss_collector.fetch_feed", side_effect=mock_fetch):
        summary = run_ingestion_pipeline(db_session)

        assert summary.active_sources_processed == 4
        assert summary.inactive_sources_skipped == 1
        assert summary.healthy_feeds == 1
        assert summary.empty_feeds == 1
        assert summary.unsupported_sources == 2  # s_html_active and s_unknown

        results_by_name = {r.source_name: r.status for r in summary.source_results}
        assert results_by_name["RSS OK Feed"] == "OK"
        assert results_by_name["RSS Empty Feed"] == "EMPTY"
        assert results_by_name["Google Blog HTML"] == "SKIPPED_INACTIVE"
        assert results_by_name["Active HTML Blog"] == "SKIPPED_UNSUPPORTED"
        assert results_by_name["Custom Source"] == "UNKNOWN_TYPE"
