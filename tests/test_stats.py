from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Article, Source
from repositories.articles import (
    count_active_sources,
    count_articles_today,
    count_total_articles,
    get_archive_stats,
    get_paginated_articles,
    get_recent_articles,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_stats_and_counts(db_session):
    london_tz = ZoneInfo("Europe/London")
    now_london = datetime.now(london_tz)
    today_start_london = now_london.replace(hour=0, minute=0, second=0, microsecond=0)

    # Active and inactive sources
    s_active1 = Source(name="Active 1", active=True, feed_url="https://a1.com/rss")
    s_active2 = Source(name="Active 2", active=True, feed_url="https://a2.com/rss")
    s_inactive = Source(name="Inactive", active=False, website_url="https://in.com")
    db_session.add_all([s_active1, s_active2, s_inactive])
    db_session.commit()

    # Active source count test
    assert count_active_sources(db_session) == 2

    # Articles setup:
    # 1. Historical article (published in 2024)
    art_historical = Article(
        source_id=s_active1.id,
        title="Historical 2024 Article",
        canonical_url="https://a1.com/2024",
        published_at=datetime(2024, 5, 1, 10, 0, tzinfo=timezone.utc),
    )
    # 2. Article published today in Europe/London (10 seconds after midnight so it is never future-dated)
    published_today_dt = (today_start_london + timedelta(seconds=10)).astimezone(timezone.utc)
    art_today = Article(
        source_id=s_active1.id,
        title="Published Today Article",
        canonical_url="https://a1.com/today",
        published_at=published_today_dt,
    )
    # 3. Article published tomorrow (future dated)
    published_tomorrow_dt = (today_start_london + timedelta(days=1, hours=2)).astimezone(timezone.utc)
    art_tomorrow = Article(
        source_id=s_active2.id,
        title="Published Tomorrow Article",
        canonical_url="https://a2.com/tomorrow",
        published_at=published_tomorrow_dt,
    )
    # 4. Article with null published_at
    art_null = Article(
        source_id=s_active2.id,
        title="Null Published Date Article",
        canonical_url="https://a2.com/null",
        published_at=None,
    )

    db_session.add_all([art_historical, art_today, art_tomorrow, art_null])
    db_session.commit()

    # Total archive count includes ALL 4 stored articles (SELECT COUNT(*) FROM articles)
    assert count_total_articles(db_session) == 4

    # Today's articles count: ONLY art_today should be counted (1)
    assert count_articles_today(db_session, tz_name="Europe/London") == 1

    # Overall stats dictionary test
    stats = get_archive_stats(db_session)
    assert stats["total_archive"] == 4
    assert stats["today_articles"] == 1
    assert stats["active_sources"] == 2


def test_europe_london_timezone_boundary(db_session):
    # Test boundary condition specifically around Europe/London midnight
    london_tz = ZoneInfo("Europe/London")
    now_london = datetime.now(london_tz)
    today_start_london = now_london.replace(hour=0, minute=0, second=0, microsecond=0)

    s1 = Source(name="Source 1", active=True)
    db_session.add(s1)
    db_session.commit()

    # Exactly at today 00:00:00 London
    art_start = Article(
        source_id=s1.id,
        title="Midnight Start Article",
        canonical_url="https://s1.com/start",
        published_at=today_start_london.astimezone(timezone.utc),
    )
    # 1 second before today 00:00:00 London (Yesterday)
    art_prev = Article(
        source_id=s1.id,
        title="Yesterday Article",
        canonical_url="https://s1.com/prev",
        published_at=(today_start_london - timedelta(seconds=1)).astimezone(timezone.utc),
    )

    db_session.add_all([art_start, art_prev])
    db_session.commit()

    # Midnight start is included in today, yesterday 23:59:59 is excluded
    assert count_articles_today(db_session, tz_name="Europe/London") == 1


def test_historical_article_not_counted_as_today(db_session):
    art = Article(
        title="2015 Article",
        canonical_url="https://example.com/2015",
        published_at=datetime(2015, 6, 15, 12, 0, tzinfo=timezone.utc),
    )
    db_session.add(art)
    db_session.commit()

    assert count_articles_today(db_session, tz_name="Europe/London") == 0


def test_article_published_today_is_counted(db_session):
    london_tz = ZoneInfo("Europe/London")
    now_london = datetime.now(london_tz)
    today_start_london = now_london.replace(hour=0, minute=0, second=0, microsecond=0)

    published_today_dt = (today_start_london + timedelta(seconds=10)).astimezone(timezone.utc)
    art = Article(
        title="Today Article",
        canonical_url="https://example.com/today-art",
        published_at=published_today_dt,
    )
    db_session.add(art)
    db_session.commit()

    assert count_articles_today(db_session, tz_name="Europe/London") == 1


def test_article_published_tomorrow_excluded_from_today(db_session):
    london_tz = ZoneInfo("Europe/London")
    now_london = datetime.now(london_tz)
    today_start_london = now_london.replace(hour=0, minute=0, second=0, microsecond=0)

    published_tomorrow_dt = (today_start_london + timedelta(days=1, hours=1)).astimezone(timezone.utc)
    art = Article(
        title="Tomorrow Article",
        canonical_url="https://example.com/tomorrow-art",
        published_at=published_tomorrow_dt,
    )
    db_session.add(art)
    db_session.commit()

    assert count_articles_today(db_session, tz_name="Europe/London") == 0
    assert count_total_articles(db_session) == 1


def test_inactive_source_not_included_in_active_source_count(db_session):
    s_active = Source(name="Active Source", active=True)
    s_inactive = Source(name="Inactive Source", active=False)
    db_session.add_all([s_active, s_inactive])
    db_session.commit()

    assert count_active_sources(db_session) == 1


def test_total_archive_includes_future_dated_stored_rows(db_session):
    now = datetime.now(timezone.utc)
    past_art = Article(title="Past", canonical_url="https://ex.com/p", published_at=now - timedelta(days=10))
    future_art = Article(title="Future", canonical_url="https://ex.com/f", published_at=now + timedelta(days=10))
    db_session.add_all([past_art, future_art])
    db_session.commit()

    # Total archive must count ALL stored articles (SELECT COUNT(*) FROM articles)
    assert count_total_articles(db_session) == 2


def test_visible_article_lists_exclude_future_dated_rows(db_session):
    now = datetime.now(timezone.utc)
    past_art = Article(title="Past Article", canonical_url="https://ex.com/p1", published_at=now - timedelta(days=1))
    future_art = Article(title="Future Article", canonical_url="https://ex.com/f1", published_at=now + timedelta(days=5))
    db_session.add_all([past_art, future_art])
    db_session.commit()

    recent = get_recent_articles(db_session)
    titles = [a.title for a in recent]
    assert "Past Article" in titles
    assert "Future Article" not in titles

    paginated = get_paginated_articles(db_session)
    paginated_titles = [a.title for a in paginated["articles"]]
    assert "Past Article" in paginated_titles
    assert "Future Article" not in paginated_titles


def test_todays_count_excludes_tomorrow_future_rows(db_session):
    london_tz = ZoneInfo("Europe/London")
    now_london = datetime.now(london_tz)
    today_start_london = now_london.replace(hour=0, minute=0, second=0, microsecond=0)

    art_today = Article(
        title="Today Article",
        canonical_url="https://ex.com/t1",
        published_at=(today_start_london + timedelta(seconds=10)).astimezone(timezone.utc),
    )
    art_tomorrow = Article(
        title="Tomorrow Article",
        canonical_url="https://ex.com/t2",
        published_at=(today_start_london + timedelta(days=1, hours=2)).astimezone(timezone.utc),
    )
    art_far_future = Article(
        title="Far Future Article",
        canonical_url="https://ex.com/t3",
        published_at=(today_start_london + timedelta(days=30)).astimezone(timezone.utc),
    )
    db_session.add_all([art_today, art_tomorrow, art_far_future])
    db_session.commit()

    assert count_articles_today(db_session, tz_name="Europe/London") == 1


def test_utc_timezone_storage_and_conversion(db_session):
    # Store article with timezone-aware UTC published_at
    utc_time = datetime(2026, 7, 15, 14, 30, tzinfo=timezone.utc)
    art = Article(
        title="UTC Timestamp Test",
        canonical_url="https://ex.com/utc-test",
        published_at=utc_time,
        collected_at=datetime.now(timezone.utc),
    )
    db_session.add(art)
    db_session.commit()

    fetched = db_session.query(Article).filter(Article.canonical_url == "https://ex.com/utc-test").first()
    assert fetched is not None
    assert fetched.published_at is not None

    # Convert UTC to Europe/London timezone dynamically via ZoneInfo
    london_tz = ZoneInfo("Europe/London")
    # July is in British Summer Time (BST, UTC+1)
    if fetched.published_at.tzinfo is None:
        fetched_dt = fetched.published_at.replace(tzinfo=timezone.utc)
    else:
        fetched_dt = fetched.published_at

    local_dt = fetched_dt.astimezone(london_tz)
    assert local_dt.hour == 15  # 14:30 UTC -> 15:30 BST
    assert local_dt.minute == 30


def test_dst_transition_europe_london_boundary(db_session):
    london_tz = ZoneInfo("Europe/London")
    
    # Summer BST date: 2026-07-01 00:00:00 BST = 2026-06-30 23:00:00 UTC
    bst_start_local = datetime(2026, 7, 1, 0, 0, 0, tzinfo=london_tz)
    bst_start_utc = bst_start_local.astimezone(timezone.utc)
    
    assert bst_start_utc == datetime(2026, 6, 30, 23, 0, 0, tzinfo=timezone.utc)

    # Winter GMT date: 2026-01-01 00:00:00 GMT = 2026-01-01 00:00:00 UTC
    gmt_start_local = datetime(2026, 1, 1, 0, 0, 0, tzinfo=london_tz)
    gmt_start_utc = gmt_start_local.astimezone(timezone.utc)
    
    assert gmt_start_utc == datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)



