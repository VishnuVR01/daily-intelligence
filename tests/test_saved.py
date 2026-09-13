from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Article, SavedArticle, Source
from repositories.saved import (
    get_saved_article_ids,
    is_saved,
    list_saved_articles,
    mark_read,
    mark_unread,
    save_article,
    unsave_article,
)


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

    s1 = Source(name="Tech Insider", feed_url="https://tech.org/rss", category="AI & Technology", active=True)
    s2 = Source(name="Global Trade", feed_url="https://trade.org/rss", category="Supply Chain & Trade", active=True)
    session.add_all([s1, s2])
    session.commit()

    now = datetime.now(timezone.utc)
    a1 = Article(
        source_id=s1.id,
        title="Breakthrough in Quantum Computing",
        canonical_url="https://tech.org/quantum-1",
        published_at=now - timedelta(hours=2),
        raw_summary="Quantum summary",
    )
    a2 = Article(
        source_id=s2.id,
        title="Global Shipping Routes Disrupted",
        canonical_url="https://trade.org/shipping-1",
        published_at=now - timedelta(hours=1),
        raw_summary="Shipping summary",
    )
    session.add_all([a1, a2])
    session.commit()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_repository_save_and_unsave(db_session):
    articles = db_session.query(Article).all()
    a1 = articles[0]

    assert is_saved(db_session, a1.id) is False
    assert get_saved_article_ids(db_session) == set()

    # Save article
    saved1 = save_article(db_session, a1.id)
    assert saved1 is not None
    assert saved1.article_id == a1.id
    assert saved1.is_read is False

    # Duplicate save is idempotent
    saved_dup = save_article(db_session, a1.id)
    assert saved_dup.id == saved1.id

    assert is_saved(db_session, a1.id) is True
    assert get_saved_article_ids(db_session) == {a1.id}

    # Unsave
    res = unsave_article(db_session, a1.id)
    assert res is True
    assert is_saved(db_session, a1.id) is False
    assert get_saved_article_ids(db_session) == set()

    # Unsave non-saved article returns False
    res_again = unsave_article(db_session, a1.id)
    assert res_again is False


def test_repository_read_unread_status(db_session):
    articles = db_session.query(Article).all()
    a1 = articles[0]

    save_article(db_session, a1.id)
    
    # Mark read
    saved_read = mark_read(db_session, a1.id)
    assert saved_read.is_read is True
    assert saved_read.read_at is not None

    # Mark unread
    saved_unread = mark_unread(db_session, a1.id)
    assert saved_unread.is_read is False
    assert saved_unread.read_at is None


def test_repository_list_saved_articles_filter(db_session):
    articles = db_session.query(Article).order_by(Article.id).all()
    a1, a2 = articles[0], articles[1]

    save_article(db_session, a1.id)
    save_article(db_session, a2.id)
    mark_read(db_session, a1.id)

    # All
    all_res = list_saved_articles(db_session, status_filter="all")
    assert len(all_res["saved_articles"]) == 2

    # Unread
    unread_res = list_saved_articles(db_session, status_filter="unread")
    assert len(unread_res["saved_articles"]) == 1
    assert unread_res["saved_articles"][0].article_id == a2.id

    # Read
    read_res = list_saved_articles(db_session, status_filter="read")
    assert len(read_res["saved_articles"]) == 1
    assert read_res["saved_articles"][0].article_id == a1.id

    # Filter by category
    cat_res = list_saved_articles(db_session, status_filter="all", category="AI & Technology")
    assert len(cat_res["saved_articles"]) == 1
    assert cat_res["saved_articles"][0].article_id == a1.id


def test_api_save_endpoints(client, db_session):
    articles = db_session.query(Article).order_by(Article.id).all()
    a1 = articles[0]

    # Save via POST
    response = client.post(f"/api/articles/{a1.id}/save")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "saved"
    assert data["article_id"] == a1.id

    # Get API list
    response = client.get("/api/saved")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["counts"]["all"] == 1
    assert data["counts"]["unread"] == 1

    # Mark read via API
    response = client.post(f"/api/articles/{a1.id}/read")
    assert response.status_code == 200
    assert response.json()["is_read"] is True

    # Mark unread via API
    response = client.post(f"/api/articles/{a1.id}/unread")
    assert response.status_code == 200
    assert response.json()["is_read"] is False

    # Remove via DELETE
    response = client.delete(f"/api/articles/{a1.id}/save")
    assert response.status_code == 200
    assert response.json()["status"] == "unsaved"

    # Non-existent article return 404
    response = client.post("/api/articles/999999/save")
    assert response.status_code == 404


def test_saved_web_page_rendering(client, db_session):
    articles = db_session.query(Article).all()
    a1 = articles[0]
    save_article(db_session, a1.id)

    response = client.get("/saved")
    assert response.status_code == 200
    assert "Saved Articles" in response.text
    assert a1.title in response.text
