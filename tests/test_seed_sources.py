import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Source
from scripts.seed_sources import seed_sources


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_seed_sources_inserts_new_sources(db_session, tmp_path):
    sources_data = [
        {
            "name": "Test Source 1",
            "feed_url": "https://example.com/feed1.xml",
            "website_url": "https://example.com",
            "category": "Tech",
            "trust_tier": "Primary",
            "active": True,
        },
        {
            "name": "Test Source 2",
            "feed_url": "https://example.com/feed2.xml",
            "website_url": "https://example.com/2",
            "category": "Science",
            "trust_tier": "Secondary",
            "active": True,
        },
    ]

    json_file = tmp_path / "sources.json"
    json_file.write_text(json.dumps(sources_data), encoding="utf-8")

    summary = seed_sources(db_session, json_path=json_file)

    assert summary["total"] == 2
    assert summary["inserted"] == 2
    assert summary["updated"] == 0
    assert summary["unchanged"] == 0

    sources = db_session.query(Source).all()
    assert len(sources) == 2
    names = {s.name for s in sources}
    assert names == {"Test Source 1", "Test Source 2"}


def test_seed_sources_prevents_duplicates_and_updates_changed(db_session, tmp_path):
    initial_data = [
        {
            "name": "Test Source 1",
            "feed_url": "https://example.com/feed1.xml",
            "website_url": "https://example.com",
            "category": "Tech",
            "trust_tier": "Primary",
            "active": True,
        }
    ]

    json_file = tmp_path / "sources.json"
    json_file.write_text(json.dumps(initial_data), encoding="utf-8")
    seed_sources(db_session, json_path=json_file)

    # Re-running with exact same data
    summary2 = seed_sources(db_session, json_path=json_file)
    assert summary2["inserted"] == 0
    assert summary2["updated"] == 0
    assert summary2["unchanged"] == 1

    # Re-running with changed category and source_type
    updated_data = [
        {
            "name": "Test Source 1",
            "feed_url": "https://example.com/feed1.xml",
            "website_url": "https://example.com",
            "source_type": "html",
            "category": "AI & Robotics",
            "trust_tier": "Primary",
            "active": True,
        }
    ]
    json_file.write_text(json.dumps(updated_data), encoding="utf-8")
    summary3 = seed_sources(db_session, json_path=json_file)
    assert summary3["inserted"] == 0
    assert summary3["updated"] == 1
    assert summary3["unchanged"] == 0

    source = db_session.query(Source).filter_by(name="Test Source 1").first()
    assert source is not None
    assert source.category == "AI & Robotics"
    assert source.source_type == "html"
