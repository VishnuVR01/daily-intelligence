import json
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Source, Article
from ingestion.pipeline import run_ingestion_pipeline
from ingestion.collectors import CollectionStatus, CollectorResult
from ingestion.rss import FeedItem


def test_sources_json_config_validation():
    json_path = Path(__file__).resolve().parent.parent / "config" / "sources.json"
    assert json_path.exists(), "config/sources.json must exist"

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 50, f"Expected 50 total sources in sources.json, got {len(data)}"

    names = set()
    feed_urls = set()

    for item in data:
        name = item.get("name")
        feed_url = item.get("feed_url")
        category = item.get("category")
        source_type = item.get("source_type")

        assert name, "Every source must have a name"
        assert name not in names, f"Duplicate source name detected: {name}"
        names.add(name)

        if feed_url:
            assert feed_url not in feed_urls, f"Duplicate feed_url detected: {feed_url}"
            feed_urls.add(feed_url)

        assert category in [
            "World", "AI & Technology", "Markets & Economy", "Industry & Operations",
            "Supply Chain & Trade", "Research", "Geopolitics", "Energy",
            "Sustainability", "Business", "Commodities"
        ], f"Invalid category '{category}' for source {name}"

        assert source_type in [
            "rss", "NEWS_FEED", "INSTITUTIONAL_RESEARCH", "CENTRAL_BANK",
            "COMPANY_PRIMARY", "COMMODITY_RESEARCH", "STRUCTURED_DATA",
            "ENERGY_ORGANIZATION", "REGULATOR", "html"
        ], f"Invalid source_type '{source_type}' for source {name}"


def test_batch2_activated_sources_present():
    json_path = Path(__file__).resolve().parent.parent / "config" / "sources.json"
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    batch2_names = [
        "Reserve Bank of India (RBI)",
        "NY Fed Liberty Street Economics",
        "Wall Street Journal US Business",
        "Financial Times Markets",
        "CNBC Business News",
        "Google DeepMind",
        "NVIDIA Newsroom",
        "AWS Machine Learning Blog",
        "Microsoft Research Blog",
        "OilPrice.com",
        "Rigzone Energy",
        "AgFunderNews",
        "World Grain",
    ]

    configured_names = {item["name"] for item in data}
    for req_name in batch2_names:
        assert req_name in configured_names, f"Required Batch 2 source '{req_name}' missing from config/sources.json"

    # Verify licensing & usage metadata present for Batch 2 sources
    for item in data:
        if item["name"] in batch2_names:
            assert "commercial_reuse_status" in item, f"Missing commercial_reuse_status in {item['name']}"
            assert item["commercial_reuse_status"] in [
                "UNKNOWN", "PERSONAL_RESEARCH_OK", "ATTRIBUTION_REQUIRED",
                "RESTRICTED", "REVIEW_BEFORE_COMMERCIAL_USE"
            ]
            assert "usage_notes" in item, f"Missing usage_notes in {item['name']}"
            assert "terms_url" in item, f"Missing terms_url in {item['name']}"


def test_ingestion_failure_isolation():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()

    s_good = Source(
        name="Good Source",
        feed_url="https://good.org/rss.xml",
        source_type="NEWS_FEED",
        category="Business",
        active=True,
    )
    s_bad = Source(
        name="Broken Source",
        feed_url="https://broken.org/rss.xml",
        source_type="NEWS_FEED",
        category="Business",
        active=True,
    )
    session.add_all([s_good, s_bad])
    session.commit()

    def mock_collect(url, name):
        if "broken" in url:
            return CollectorResult(
                status=CollectionStatus.FAILED,
                error_message="HTTP 404 Not Found",
            )
        return CollectorResult(
            status=CollectionStatus.OK,
            items=[
                FeedItem(
                    title="Good News Item",
                    url="https://good.org/news-1",
                    published_at=None,
                    summary="Good summary text.",
                    source_name="Good Source",
                )
            ],
        )

    with patch("ingestion.pipeline.collect_rss", side_effect=mock_collect):
        summary = run_ingestion_pipeline(session)

    assert summary.active_sources_processed == 2
    assert summary.healthy_feeds == 1
    assert summary.failed_feeds == 1
    assert summary.new_articles == 1

    # Verify database saved the healthy source article despite broken source failure
    art = session.query(Article).filter(Article.title == "Good News Item").first()
    assert art is not None
    assert art.canonical_url == "https://good.org/news-1"

    session.close()
