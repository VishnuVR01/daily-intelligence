import logging
from typing import Any, Dict, Optional
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import get_settings, get_db_host_mode, sanitize_database_url

logger = logging.getLogger("app.db")
settings = get_settings()

db_url = settings.effective_database_url

if db_url:
    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,
    )
else:
    # Fallback in-memory engine when DATABASE_URL is not configured (e.g. production missing DB secret)
    engine = create_engine("sqlite:///:memory:")

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


def check_db_health() -> Dict[str, Any]:
    """
    Sanitized, environment-aware diagnostic check for PostgreSQL database.
    Never exposes passwords, tokens, or raw credentials.
    """
    raw_url = settings.database_url
    effective_url = settings.effective_database_url

    if not effective_url:
        return {
            "configured": False,
            "mode": get_db_host_mode(raw_url),
            "reachable": False,
            "schema_valid": False,
            "migration_revision": None,
            "error": "DATABASE_URL is not configured for production environment",
        }

    host_mode = get_db_host_mode(effective_url)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        reachable = True
    except Exception as exc:
        sanitized = sanitize_database_url(effective_url)
        logger.warning(f"Database connection failed for host mode={host_mode} ({sanitized}): {exc.__class__.__name__}")
        return {
            "configured": True,
            "mode": host_mode,
            "reachable": False,
            "schema_valid": False,
            "migration_revision": None,
            "error": f"Connection failed: {exc.__class__.__name__}",
        }

    # Fetch migration revision safely if alembic_version table exists
    migration_revision: Optional[str] = None
    try:
        with engine.connect() as conn:
            res = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            row = res.fetchone()
            if row:
                migration_revision = str(row[0])
    except Exception:
        pass

    # Check schema validation
    try:
        from app.schema_validation import validate_schema
        validate_schema(engine, Base.metadata)
        schema_valid = True
        error_msg = None
    except Exception as exc:
        schema_valid = False
        error_msg = str(exc)

    return {
        "configured": True,
        "mode": host_mode,
        "reachable": True,
        "schema_valid": schema_valid,
        "migration_revision": migration_revision,
        "error": error_msg,
    }


def get_db():
    if not settings.effective_database_url:
        raise HTTPException(
            status_code=503,
            detail="Database service is unconfigured in production environment.",
        )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

