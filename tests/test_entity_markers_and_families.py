import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Article, Source
from app.entity_metadata import (
    EntityMetadata,
    format_country_badges,
    get_country_info,
    get_source_family_info,
)
from repositories.articles import get_sources_summary


@pytest.fixture
def test_db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(test_db_session):
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_entity_metadata_model():
    entity = EntityMetadata(
        name="McKinsey & Company",
        entity_type="consulting_firm",
        country_code="US",
    )
    data = entity.to_dict()
    assert data["name"] == "McKinsey & Company"
    assert data["entity_type"] == "consulting_firm"
    assert data["country_code"] == "US"
    assert data["country_name"] == "United States"
    assert data["country_flag"] == "🇺🇸"
    assert data["fallback_icon"] == "💼"


def test_format_country_badges_overflow():
    countries = ["US", "GB", "CN", "BR", "FR"]
    result = format_country_badges(countries, max_visible=3)

    assert result["total_count"] == 5
    assert len(result["visible"]) == 3
    assert [c["code"] for c in result["visible"]] == ["US", "GB", "CN"]
    assert result["overflow_count"] == 2
    assert "Brazil" in result["overflow_names"]
    assert "France" in result["overflow_names"]


def test_source_family_info_lookup():
    news_info = get_source_family_info("news")
    assert news_info["label"] == "News & Media"
    assert news_info["class"] == "family-news"

    consulting_info = get_source_family_info("consulting")
    assert consulting_info["label"] == "Consulting"
    assert consulting_info["class"] == "family-consulting"

    gov_info = get_source_family_info("government")
    assert gov_info["label"] == "Government & Multilateral"
    assert gov_info["class"] == "family-gov"

    os_info = get_source_family_info("open_source")
    assert os_info["label"] == "Open Source"
    assert os_info["class"] == "family-open-source"


def test_get_sources_summary_family_filtering(test_db_session):
    s1 = Source(name="Consulting One", feed_url="https://c1.com/rss", source_family="consulting", active=True)
    s2 = Source(name="University One", feed_url="https://u1.com/rss", source_family="university", active=True)
    s3 = Source(name="Gov One", feed_url="https://g1.com/rss", source_family="government", active=True)
    test_db_session.add_all([s1, s2, s3])
    test_db_session.commit()

    all_summary = get_sources_summary(test_db_session)
    assert len(all_summary) >= 3

    consulting_summary = get_sources_summary(test_db_session, family="consulting")
    assert any(s["name"] == "Consulting One" for s in consulting_summary)
    assert not any(s["name"] == "University One" for s in consulting_summary)

    univ_summary = get_sources_summary(test_db_session, family="university")
    assert any(s["name"] == "University One" for s in univ_summary)
    assert not any(s["name"] == "Consulting One" for s in univ_summary)


def test_web_sources_family_filter_endpoint(client, test_db_session):
    s = Source(name="McKinsey Test", feed_url="https://mcktest.com/rss", source_family="consulting", active=True)
    test_db_session.add(s)
    test_db_session.commit()

    response = client.get("/sources?family=consulting")
    assert response.status_code == 200
    assert "McKinsey Test" in response.text
    assert "Consulting" in response.text


def test_api_articles_includes_source_family(client, test_db_session):
    s = Source(name="McKinsey API", feed_url="https://mckapi.com/rss", source_family="consulting", active=True)
    test_db_session.add(s)
    test_db_session.commit()

    art = Article(source_id=s.id, title="Consulting Insights", canonical_url="https://mckapi.com/art1")
    test_db_session.add(art)
    test_db_session.commit()

    res = client.get("/api/articles")
    assert res.status_code == 200
    data = res.json()
    matched = next((item for item in data if item["title"] == "Consulting Insights"), None)
    assert matched is not None
    assert matched["source"]["source_family"] == "consulting"
