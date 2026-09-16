"""
Automated Regression Test for Fresh Database Reference Data & Sources Bootstrap.
Verifies that:
1. Empty PostgreSQL database schema after `alembic upgrade head` is populated cleanly by `seed_sources`.
2. All country reference data (including QA, US, GB, DE, etc.) is seeded before sources.
3. Foreign keys from `sources.country_code` -> `countries.code` are 100% valid.
4. Subsequent calls to `seed_sources` are idempotent (0 duplicate rows created).
"""

import os
import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command

from app.config import get_settings
from app.models import Source, Country
from scripts.seed_sources import seed_sources

TEST_SCHEMA = "test_fresh_bootstrap_schema"


def test_fresh_db_reference_data_and_sources_bootstrap(monkeypatch):
    """
    Tests fresh database bootstrap flow:
    empty DB -> alembic upgrade head -> seed_sources -> SUCCESS -> repeat seed_sources (idempotent).
    """
    settings = get_settings()
    base_url = settings.effective_database_url
    if not base_url or "localhost" not in base_url:
        pytest.skip("Test requires local PostgreSQL database connection.")

    if base_url.startswith("postgresql://"):
        raw_base = base_url
        sqla_base = "postgresql+psycopg://" + base_url[len("postgresql://"):]
    elif base_url.startswith("postgresql+psycopg://"):
        sqla_base = base_url
        raw_base = "postgresql://" + base_url[len("postgresql+psycopg://"):]
    else:
        sqla_base = base_url
        raw_base = base_url

    sep = "&" if "?" in sqla_base else "?"
    sqla_schema_url = f"{sqla_base}{sep}options=-csearch_path%3D{TEST_SCHEMA}"
    raw_schema_url = f"{raw_base}{sep}options=-csearch_path%3D{TEST_SCHEMA}"

    # 1. Create clean isolated schema
    with psycopg.connect(raw_base, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE")
            cur.execute(f"CREATE SCHEMA {TEST_SCHEMA}")

    engine = None
    try:
        # 2. Run Alembic upgrade head against empty schema
        monkeypatch.setenv("DATABASE_URL", raw_schema_url)
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", sqla_schema_url.replace("%", "%%"))

        command.upgrade(alembic_cfg, "head")

        engine = create_engine(sqla_schema_url)
        TestSession = sessionmaker(bind=engine)
        session = TestSession()

        # 3. Verify tables are initially empty
        assert session.query(Country).count() == 0
        assert session.query(Source).count() == 0

        # 4. First run of seed_sources on fresh DB
        summary1 = seed_sources(session)
        assert summary1["inserted"] == 50
        assert summary1["countries"]["inserted"] > 0
        assert session.query(Source).count() == 50

        # 5. Verify Al Jazeera English (QA) & Foreign Key Validity
        al_jazeera = session.query(Source).filter(Source.name == "Al Jazeera English").first()
        assert al_jazeera is not None
        assert al_jazeera.country_code == "QA"

        qatar = session.query(Country).filter(Country.code == "QA").first()
        assert qatar is not None
        assert qatar.name == "Qatar"

        # Verify all source country codes exist in countries table
        db_sources = session.query(Source).all()
        for s in db_sources:
            if s.country_code:
                country_exists = session.query(Country).filter(Country.code == s.country_code).first()
                assert country_exists is not None, f"Source '{s.name}' has invalid country_code '{s.country_code}'"

        # 6. Second run of seed_sources (Idempotency Test)
        summary2 = seed_sources(session)
        assert summary2["inserted"] == 0
        assert summary2["updated"] == 0
        assert summary2["countries"]["inserted"] == 0
        assert summary2["countries"]["updated"] == 0
        assert session.query(Source).count() == 50
        assert session.query(Country).count() == summary1["countries"]["total"]

        session.close()

    finally:
        if engine:
            engine.dispose()
        with psycopg.connect(raw_base, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE")
