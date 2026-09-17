from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Article, ArticleAIOutput, Source
from repositories.articles import get_recent_articles
from app.config import get_ai_provider_info, get_settings


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    yield session
    session.close()


def test_empty_database_behaviour(db_session):
    assert get_recent_articles(db_session, mode="balanced") == []
    assert get_recent_articles(db_session, mode="chronological") == []
    assert get_recent_articles(db_session, mode="ai_curated") == []


def test_balanced_works_with_zero_ai_outputs(db_session):
    s1 = Source(name="Reuters AI", feed_url="https://reuters.com/ai", category="AI", active=True)
    db_session.add(s1)
    db_session.commit()

    now = datetime.now(timezone.utc)
    a1 = Article(title="Raw AI Ingested 1", canonical_url="https://reuters.com/1", source_id=s1.id, published_at=now - timedelta(minutes=10), collected_at=now)
    a2 = Article(title="Raw AI Ingested 2", canonical_url="https://reuters.com/2", source_id=s1.id, published_at=now - timedelta(minutes=5), collected_at=now)
    db_session.add_all([a1, a2])
    db_session.commit()

    articles = get_recent_articles(db_session, mode="balanced")
    assert len(articles) == 2
    assert {a.title for a in articles} == {"Raw AI Ingested 1", "Raw AI Ingested 2"}


def test_balanced_enforces_source_diversity(db_session):
    s1 = Source(name="Monopolist Source", feed_url="https://mono.com/rss", category="Markets", active=True)
    s2 = Source(name="Independent Source", feed_url="https://indie.com/rss", category="Markets", active=True)
    db_session.add_all([s1, s2])
    db_session.commit()

    now = datetime.now(timezone.utc)
    arts_s1 = [
        Article(title=f"Mono {i}", canonical_url=f"https://mono.com/{i}", source_id=s1.id, published_at=now - timedelta(minutes=i))
        for i in range(1, 6)
    ]
    art_s2 = Article(title="Indie 1", canonical_url="https://indie.com/1", source_id=s2.id, published_at=now - timedelta(minutes=3))
    db_session.add_all(arts_s1 + [art_s2])
    db_session.commit()

    results = get_recent_articles(db_session, mode="balanced", limit=50)
    s1_count = sum(1 for a in results if a.source_id == s1.id)
    s2_count = sum(1 for a in results if a.source_id == s2.id)

    assert len(results) == 6
    assert s2_count == 1


def test_chronological_works_with_zero_ai_outputs(db_session):
    s1 = Source(name="Chron Feed", feed_url="https://chron.com/rss", category="Geopolitics", active=True)
    db_session.add(s1)
    db_session.commit()

    now = datetime.now(timezone.utc)
    a1 = Article(title="Older Article", canonical_url="https://chron.com/old", source_id=s1.id, published_at=now - timedelta(hours=2))
    a2 = Article(title="Newer Article", canonical_url="https://chron.com/new", source_id=s1.id, published_at=now - timedelta(hours=1))
    db_session.add_all([a1, a2])
    db_session.commit()

    articles = get_recent_articles(db_session, mode="chronological")
    assert len(articles) == 2
    assert articles[0].title == "Newer Article"
    assert articles[1].title == "Older Article"


def test_ai_curated_excludes_unprocessed_articles(db_session):
    s1 = Source(name="Tech Feed", feed_url="https://tech.com/rss", category="AI", active=True)
    db_session.add(s1)
    db_session.commit()

    a1 = Article(title="Unprocessed Article", canonical_url="https://tech.com/unproc", source_id=s1.id, published_at=datetime.now(timezone.utc))
    db_session.add(a1)
    db_session.commit()

    articles = get_recent_articles(db_session, mode="ai_curated")
    assert len(articles) == 0


def test_ai_curated_includes_successful_relevant_articles(db_session):
    s1 = Source(name="Tech Feed", feed_url="https://tech.com/rss", category="AI", active=True)
    db_session.add(s1)
    db_session.commit()

    a1 = Article(title="Curated Relevant Article", canonical_url="https://tech.com/curated", source_id=s1.id, published_at=datetime.now(timezone.utc))
    db_session.add(a1)
    db_session.commit()

    ai_out = ArticleAIOutput(
        article_id=a1.id,
        status="success",
        is_relevant=True,
        primary_category="AI & Technology",
        summary="A major AI breakthrough occurred.",
    )
    db_session.add(ai_out)
    db_session.commit()

    articles = get_recent_articles(db_session, mode="ai_curated")
    assert len(articles) == 1
    assert articles[0].title == "Curated Relevant Article"


def test_ai_curated_excludes_irrelevant_and_failed_articles(db_session):
    s1 = Source(name="News Feed", feed_url="https://news.com/rss", category="World", active=True)
    db_session.add(s1)
    db_session.commit()

    now = datetime.now(timezone.utc)
    a1 = Article(title="Out of Scope Article", canonical_url="https://news.com/oos", source_id=s1.id, published_at=now - timedelta(minutes=30))
    a2 = Article(title="Failed Processing Article", canonical_url="https://news.com/fail", source_id=s1.id, published_at=now - timedelta(minutes=20))
    a3 = Article(title="Explicitly Irrelevant Article", canonical_url="https://news.com/irrel", source_id=s1.id, published_at=now - timedelta(minutes=10))
    db_session.add_all([a1, a2, a3])
    db_session.commit()

    ai_out1 = ArticleAIOutput(article_id=a1.id, status="out_of_scope", is_relevant=False)
    ai_out2 = ArticleAIOutput(article_id=a2.id, status="failed", is_relevant=None)
    ai_out3 = ArticleAIOutput(article_id=a3.id, status="success", is_relevant=False)
    db_session.add_all([ai_out1, ai_out2, ai_out3])
    db_session.commit()

    articles = get_recent_articles(db_session, mode="ai_curated")
    assert len(articles) == 0

    balanced = get_recent_articles(db_session, mode="balanced")
    assert "Out of Scope Article" not in {a.title for a in balanced}
    assert "Explicitly Irrelevant Article" not in {a.title for a in balanced}


def test_category_filtering_still_works(db_session):
    s_ai = Source(name="AI Source", feed_url="https://ai.com/rss", category="AI", active=True)
    s_mkt = Source(name="Market Source", feed_url="https://mkt.com/rss", category="Markets", active=True)
    db_session.add_all([s_ai, s_mkt])
    db_session.commit()

    now = datetime.now(timezone.utc)
    a_ai = Article(title="AI Breakthrough", canonical_url="https://ai.com/1", source_id=s_ai.id, published_at=now)
    a_mkt = Article(title="Stock Rally", canonical_url="https://mkt.com/1", source_id=s_mkt.id, published_at=now)
    db_session.add_all([a_ai, a_mkt])
    db_session.commit()

    ai_out = ArticleAIOutput(article_id=a_ai.id, status="success", is_relevant=True)
    db_session.add(ai_out)
    db_session.commit()

    for mode in ["balanced", "chronological", "ai_curated"]:
        ai_arts = get_recent_articles(db_session, category="AI", mode=mode)
        assert len(ai_arts) == 1
        assert ai_arts[0].title == "AI Breakthrough"

        mkt_arts = get_recent_articles(db_session, category="Markets", mode=mode)
        assert len(mkt_arts) == (0 if mode == "ai_curated" else 1)
        if mode != "ai_curated":
            assert mkt_arts[0].title == "Stock Rally"


def test_get_ai_provider_info_fallback(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "ollama_enabled", False)
    monkeypatch.setattr(settings, "openrouter_api_key", "")

    info = get_ai_provider_info(ttl_seconds=0)
    assert info["available"] is False
    assert info["label"] == "Deterministic Feed"
    assert "Independent" in info["footer_label"]
