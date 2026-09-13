from datetime import datetime, timezone
from unittest.mock import patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Article, Source
from ingestion.pipeline import run_ingestion_pipeline
from ingestion.rss import FeedItem


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create test active sources
    source1 = Source(
        name="Source Alpha",
        feed_url="https://alpha.com/rss",
        source_type="rss",
        active=True,
    )
    source2 = Source(
        name="Source Beta",
        feed_url="https://beta.com/rss",
        source_type="rss",
        active=True,
    )
    session.add_all([source1, source2])
    session.commit()

    yield session
    session.close()


def mock_fetch_feed(feed_url: str, source_name: str) -> list[FeedItem]:
    if "alpha" in feed_url:
        return [
            FeedItem(
                title="Alpha Story 1",
                url="https://alpha.com/story1?utm_source=rss",
                published_at=datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc),
                summary="Summary 1",
                source_name=source_name,
            ),
            FeedItem(
                title="Alpha Story 2",
                url="https://alpha.com/story2",
                published_at=datetime(2026, 9, 12, 13, 0, tzinfo=timezone.utc),
                summary="Summary 2",
                source_name=source_name,
            ),
        ]
    elif "beta" in feed_url:
        return [
            FeedItem(
                title="Beta Story 1",
                url="https://beta.com/story1",
                published_at=datetime(2026, 9, 12, 14, 0, tzinfo=timezone.utc),
                summary="Summary 3",
                source_name=source_name,
            )
        ]
    return []


@patch("ingestion.collectors.rss_collector.fetch_feed", side_effect=mock_fetch_feed)
def test_pipeline_ingestion_and_deduplication(mock_fetch, db_session):
    # First run: should insert 3 new articles
    summary = run_ingestion_pipeline(db_session)

    assert summary.active_sources_processed == 2
    assert summary.healthy_feeds == 2
    assert summary.articles_fetched == 3
    assert summary.new_articles == 3
    assert summary.duplicates_skipped == 0
    assert summary.failed_feeds == 0

    articles = db_session.query(Article).all()
    assert len(articles) == 3

    # Check canonical URL and title fingerprint stored correctly
    art1 = db_session.query(Article).filter_by(title="Alpha Story 1").first()
    assert art1 is not None
    assert art1.canonical_url == "https://alpha.com/story1"
    assert art1.title_fingerprint is not None

    # Second run: re-ingest identical feed, all 3 should be skipped as duplicates
    summary2 = run_ingestion_pipeline(db_session)
    assert summary2.active_sources_processed == 2
    assert summary2.healthy_feeds == 2
    assert summary2.articles_fetched == 3
    assert summary2.new_articles == 0
    assert summary2.duplicates_skipped == 3
    assert summary2.failed_feeds == 0


def test_pipeline_fault_tolerance(db_session):
    def mock_fetch_with_error(feed_url: str, source_name: str) -> list[FeedItem]:
        if "alpha" in feed_url:
            raise Exception("Connection timeout fetching Alpha feed")
        return [
            FeedItem(
                title="Beta Story 1",
                url="https://beta.com/story1",
                published_at=datetime(2026, 9, 12, 14, 0, tzinfo=timezone.utc),
                summary="Summary 3",
                source_name=source_name,
            )
        ]

    with patch("ingestion.collectors.rss_collector.fetch_feed", side_effect=mock_fetch_with_error):
        summary = run_ingestion_pipeline(db_session)

        # Source Alpha fails, but Source Beta succeeds
        assert summary.active_sources_processed == 2
        assert summary.healthy_feeds == 1
        assert summary.failed_feeds == 1
        assert summary.articles_fetched == 1
        assert summary.new_articles == 1

        # Ensure Beta article was still committed to DB
        articles = db_session.query(Article).all()
        assert len(articles) == 1
        assert articles[0].title == "Beta Story 1"
