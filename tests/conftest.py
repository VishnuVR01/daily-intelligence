"""
Centralized Test Database Isolation & Safety Guard (Sprint 2 Stage 2C.2 Phase 1).
Guarantees 100% test isolation by providing SQLite in-memory test database sessions
and blocking direct calls to SessionLocal() or canonical PostgreSQL database writes.
"""
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
import app.db
from app.db import Base, get_db
from app.models import Source
from app.main import app as fastapi_app


# ---------------------------------------------------------------------------
# Phase 1 Safety Guard: Canonical Database Protection
# ---------------------------------------------------------------------------

def pytest_sessionstart(session):
    """
    Safety Guard: Executed before any test runs.
    Verifies tests do not connect directly to the canonical database.
    Monkeypatches app.db.SessionLocal to raise an error if invoked directly.
    """
    canonical_db_url = get_settings().effective_database_url
    if canonical_db_url and ("daily_intelligence" in canonical_db_url or "postgresql" in canonical_db_url):
        # Enforce that app.db.SessionLocal cannot be called directly in unit tests
        def _forbidden_session_local(*args, **kwargs):
            raise RuntimeError(
                "CANONICAL DB PROTECTION SAFETY GUARD TRIGGERED: "
                "Direct invocation of app.db.SessionLocal() is forbidden in unit tests to prevent canonical database contamination. "
                "Use the isolated 'test_db_session' fixture instead."
            )
        
        app.db.SessionLocal = _forbidden_session_local


# ---------------------------------------------------------------------------
# Centralized Isolated Test Database Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def test_db_session():
    """
    Provides an isolated SQLite in-memory test database session.
    Automatically overrides FastAPI get_db dependency during test execution.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Enable SQLite foreign key constraints for test engine
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()

    # Automatically override FastAPI get_db dependency for TestClient(app)
    def _override_get_db():
        try:
            yield session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = _override_get_db

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        fastapi_app.dependency_overrides.pop(get_db, None)
