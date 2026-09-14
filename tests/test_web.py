from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Article, Source


@pytest.fixture
def test_db_session():
    # Use StaticPool and check_same_thread=False so SQLite in-memory DB is shared across TestClient worker threads
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()

    # Seed sources
    s_ai = Source(name="AI Insider", feed_url="https://ai.org/rss", category="AI", active=True)
    s_mk = Source(name="Market Watcher", feed_url="https://mk.org/rss", category="Markets", active=True)
    session.add_all([s_ai, s_mk])
    session.commit()

    now = datetime.now(timezone.utc)

    # Past articles
    past_art1 = Article(
        source_id=s_ai.id,
        title="Breakthrough in LLM Architecture",
        canonical_url="https://ai.org/article-1",
        published_at=now - timedelta(minutes=1),
        raw_summary="Summary of AI breakthrough.",
    )

    past_art2 = Article(
        source_id=s_mk.id,
        title="Stock Markets Hit Record High",
        canonical_url="https://mk.org/article-1",
        published_at=now - timedelta(hours=1),
        raw_summary="Summary of stock market rise.",
    )

    # Future-dated article (Must be excluded by rule 6)
    future_art = Article(
        source_id=s_ai.id,
        title="Future Unreleased AI Discovery",
        canonical_url="https://ai.org/future-article",
        published_at=now + timedelta(days=5),
        raw_summary="This article is dated in the future.",
    )

    session.add_all([past_art1, past_art2, future_art])

    # Add 30 articles for pagination testing
    for i in range(30):
        session.add(
            Article(
                source_id=s_ai.id,
                title=f"Paginated AI Article {i+1}",
                canonical_url=f"https://ai.org/page-art-{i+1}",
                published_at=now - timedelta(minutes=i + 10),
                raw_summary=f"Summary for pagination item {i+1}",
            )
        )

    session.commit()

    yield session
    session.close()


@pytest.fixture
def client(test_db_session):
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_homepage_returns_200_and_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Daily" in response.text
    assert "Intelligence" in response.text
    assert "Breakthrough in LLM Architecture" in response.text


def test_out_of_scope_articles_excluded_from_homepage(client, test_db_session):
    from app.models import ArticleAIOutput
    s_ai = test_db_session.query(Source).filter(Source.name == "AI Insider").first()
    now = datetime.now(timezone.utc)

    # Add sports article
    sports_art = Article(
        source_id=s_ai.id,
        title="Real Madrid Beats Barcelona in El Clasico Match",
        canonical_url="https://ai.org/sports-match-101",
        published_at=now - timedelta(minutes=2),
        raw_summary="Sports match report.",
    )
    test_db_session.add(sports_art)
    test_db_session.commit()

    ai_out = ArticleAIOutput(
        article_id=sports_art.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        is_relevant=False,
        rejection_reason="routine sports coverage",
        status="out_of_scope",
    )
    test_db_session.add(ai_out)
    test_db_session.commit()

    # Verify out-of-scope article is excluded from homepage curated feed
    home_res = client.get("/")
    assert home_res.status_code == 200
    assert "Real Madrid Beats Barcelona" not in home_res.text

    # Verify out-of-scope article remains available in archive
    archive_res = client.get("/archive")
    assert archive_res.status_code == 200
    assert "Real Madrid Beats Barcelona" in archive_res.text


def test_category_filtering(client):
    response = client.get("/?category=Markets")
    assert response.status_code == 200
    assert "Stock Markets Hit Record High" in response.text


def test_future_dated_articles_excluded(client):
    response = client.get("/api/articles?limit=100")
    assert response.status_code == 200
    data = response.json()
    titles = [item["title"] for item in data]
    assert "Future Unreleased AI Discovery" not in titles


def test_archive_pagination(client):
    response_p1 = client.get("/archive?page=1")
    assert response_p1.status_code == 200
    assert "Page <strong>1</strong> of" in response_p1.text

    response_p2 = client.get("/archive?page=2")
    assert response_p2.status_code == 200
    assert "Page <strong>2</strong> of" in response_p2.text


def test_api_articles_endpoint(client):
    response = client.get("/api/articles?category=AI&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 5
    for item in data:
        assert item["source"]["category"] == "AI"
        assert "title" in item
        assert "canonical_url" in item


def test_pwa_manifest_endpoint(client):
    response = client.get("/static/manifest.json")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Daily Intelligence"
    assert data["display"] == "standalone"
    assert data["start_url"] == "/"
    assert len(data["icons"]) >= 2


def test_service_worker_endpoint(client):
    response = client.get("/static/js/service-worker.js")
    assert response.status_code == 200
    assert "daily-intel-v" in response.text
    assert "caches.open" in response.text
    assert "api/" in response.text  # Verifies API bypass logic is present


def test_pwa_and_viewport_meta_in_templates(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'name="viewport"' in response.text
    assert 'viewport-fit=cover' in response.text
    assert 'rel="manifest"' in response.text
    assert 'href="/static/manifest.json"' in response.text
    assert 'id="pwa-install-btn"' in response.text


def test_latest_route(client):
    response = client.get("/latest")
    assert response.status_code == 200
    assert "Latest Updates Digest" in response.text
    assert "Breakthrough in LLM Architecture" in response.text


def test_categories_overview_and_detail(client):
    response_overview = client.get("/categories")
    assert response_overview.status_code == 200
    assert "Intelligence Sectors" in response_overview.text
    assert "AI" in response_overview.text
    assert "Markets" in response_overview.text

    response_detail = client.get("/category/AI")
    assert response_detail.status_code == 200
    assert "AI Intelligence" in response_detail.text
    assert "Breakthrough in LLM Architecture" in response_detail.text


def test_sources_directory_and_detail(client, test_db_session):
    response_sources = client.get("/sources")
    assert response_sources.status_code == 200
    assert "Sources Directory & Registry Status" in response_sources.text
    assert "AI Insider" in response_sources.text
    assert "Market Watcher" in response_sources.text
    assert "Active" in response_sources.text

    s_ai = test_db_session.query(Source).filter(Source.name == "AI Insider").first()
    response_detail = client.get(f"/source/{s_ai.id}")
    assert response_detail.status_code == 200
    assert "AI Insider" in response_detail.text
    assert "Breakthrough in LLM Architecture" in response_detail.text


def test_search_endpoint(client):
    response_search = client.get("/search?q=LLM")
    assert response_search.status_code == 200
    assert "Breakthrough in LLM Architecture" in response_search.text
    assert "Stock Markets Hit Record High" not in response_search.text

    response_empty = client.get("/search?q=NonExistentKeywordXYZ")
    assert response_empty.status_code == 200
    assert "No intelligence records matched" in response_empty.text


def test_archive_date_filtering(client, test_db_session):
    from zoneinfo import ZoneInfo
    now_london = datetime.now(ZoneInfo("Europe/London"))
    today_str = now_london.strftime("%Y-%m-%d")

    response_today = client.get(f"/archive?date={today_str}")
    assert response_today.status_code == 200
    assert "Breakthrough in LLM Architecture" in response_today.text

    response_past = client.get("/archive?date=2020-01-01")
    assert response_past.status_code == 200
    assert "Breakthrough in LLM Architecture" not in response_past.text


def test_world_map_page_renders(client, test_db_session):
    # Seed countries and article-country associations for testing
    from app.models import Country, ArticleCountry
    us = Country(code="US", name="United States", region="Americas", lat=37.0902, lng=-95.7129, is_g7=True)
    cn = Country(code="CN", name="China", region="Asia", lat=35.8617, lng=104.1954, is_brics=True)
    ch = Country(code="CH", name="Switzerland", region="Europe", lat=46.8182, lng=8.2275, is_g7=False)
    test_db_session.add_all([us, cn, ch])
    test_db_session.commit()

    art = test_db_session.query(Article).first()
    art.primary_category = "AI"
    art.groups = "BRICS,G7"
    ac = ArticleCountry(article_id=art.id, country_code="CN")
    test_db_session.add(ac)
    test_db_session.commit()

    # 1. /world returns 200 and renders D3 container & controls
    response = client.get("/world")
    assert response.status_code == 200
    assert "All World" in response.text
    assert "INTELLIGENCE LENS" in response.text
    assert "world-map-svg" in response.text

    # 2. Selecting a country filters correctly
    response_cn = client.get("/world?country=CN")
    assert response_cn.status_code == 200
    assert "China Geographic Feed" in response_cn.text
    assert "Today in China" in response_cn.text

    # 3. World restores all daily stories
    response_world = client.get("/world")
    assert response_world.status_code == 200
    assert "Today's Global Intelligence Feed" in response_world.text

    # 4. BRICS filter works
    response_brics = client.get("/world?brics=1")
    assert response_brics.status_code == 200
    assert "Today's BRICS Intelligence" in response_brics.text

    # 5. Country with no stories returns empty state
    response_empty = client.get("/world?country=CH")
    assert response_empty.status_code == 200
    assert "No stories reported today" in response_empty.text

    # 6. Combined category + country filtering works
    response_combined = client.get("/world?country=CN&category=AI")
    assert response_combined.status_code == 200
    assert "China" in response_combined.text


def test_latest_view_mode_toggle(client):
    response_balanced = client.get("/latest?mode=balanced")
    assert response_balanced.status_code == 200
    assert "Editorial Balanced" in response_balanced.text

    response_chrono = client.get("/latest?mode=chronological")
    assert response_chrono.status_code == 200
    assert "Pure Chronological" in response_chrono.text


def test_sectors_directory_and_alias(client):
    response_cat = client.get("/categories")
    assert response_cat.status_code == 200
    assert "Intelligence Sectors" in response_cat.text
    assert "Explore the intelligence archive" in response_cat.text

    response_sec = client.get("/sectors")
    assert response_sec.status_code == 200
    assert "Intelligence Sectors" in response_sec.text


def test_key_themes_and_global_focus_widgets(client, test_db_session):
    from app.models import ArticleAIOutput
    art = test_db_session.query(Article).first()
    ai_out = ArticleAIOutput(
        article_id=art.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        is_relevant=True,
        output_json={
            "primary_category": "AI & Technology",
            "importance_score": 85,
            "relevance_score": 90,
            "topics": ["Artificial Intelligence", "Semiconductors"],
            "countries": ["US", "CN"],
            "entities": ["NVIDIA"]
        },
        status="processed"
    )
    test_db_session.add(ai_out)
    test_db_session.commit()

    response = client.get("/")
    assert response.status_code == 200
    assert "Key Themes Today" in response.text
    assert '<span class="key-theme-name">Artificial Intelligence</span>' in response.text
    assert "Global Focus" in response.text




def test_save_button_rendering(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "save-toggle-btn" in response.text
    assert "🔖 Save" in response.text


def test_vercel_entrypoint():
    """Verify that api/index.py imports the ASGI application cleanly for Vercel."""
    from api.index import app as vercel_app
    from fastapi.testclient import TestClient

    test_client = TestClient(vercel_app)
    resp = test_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["app"] == "Daily Intelligence Newspaper"

