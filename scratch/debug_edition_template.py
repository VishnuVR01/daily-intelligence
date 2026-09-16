from datetime import date, datetime, timezone
import pytest
from app.models import Source, Article, DailyEdition, EditionEvent, EventCluster, EventEditorialProse, EditionBrief
from services.editorial.publication import publish_daily_edition

def debug_run():
    from app.main import app
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.db import Base, get_db

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()

    app.dependency_overrides[get_db] = lambda: session

    src = Source(name="FT", website_url="https://ft.com")
    session.add(src)
    session.commit()

    art = Article(title="Art Title", canonical_url="https://ft.com/1", source_id=src.id, raw_summary="Raw summary")
    session.add(art)
    session.commit()

    ec = EventCluster(cluster_id="c1", canonical_title="Cluster Title", category="WORLD", primary_article_id=art.id)
    session.add(ec)
    session.commit()

    ed = DailyEdition(edition_date=date(2026, 9, 15), status="PUBLISHED", readiness="READY")
    session.add(ed)
    session.commit()

    ee = EditionEvent(edition_id=ed.id, event_cluster_id="c1", section="WORLD", role="LEAD_STORY", position=1)
    session.add(ee)
    session.commit()

    prose = EventEditorialProse(edition_event_id=ee.id, event_cluster_id="c1", headline="Headline Text", summary="Summary Text")
    brief = EditionBrief(edition_id=ed.id, brief_text="Brief Text", key_themes_json=[])
    session.add_all([prose, brief])
    session.commit()

    client = TestClient(app)
    res = client.get("/edition/2026-09-15")
    print("STATUS CODE:", res.status_code)
    print("TEXT LENGTH:", len(res.text))
    print("TEXT FULL:\n", res.text)

if __name__ == "__main__":
    debug_run()
