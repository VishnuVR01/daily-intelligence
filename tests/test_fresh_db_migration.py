"""
Automated Regression Test for Fresh Database Migration Replay.
Verifies that an empty PostgreSQL database can migrate cleanly from base -> e1f2a3b4c5d6,
validating foreign keys and model schema synchronization without manual table creation.
"""

import os
import psycopg
import pytest
from sqlalchemy import create_engine, text, inspect
from alembic.config import Config
from alembic import command

from app.config import get_settings
from app.models import Base
from app.schema_validation import validate_schema

TEST_SCHEMA = "test_fresh_migration_schema"


def test_fresh_database_migration_replay(monkeypatch):
    """
    Tests that a completely empty PostgreSQL database / schema can be migrated from
    base -> head (e1f2a3b4c5d6) without errors, missing tables, or FK failures.
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

        # 3. Verify alembic current is e1f2a3b4c5d6
        engine = create_engine(sqla_schema_url)
        with engine.connect() as conn:
            res = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            row = res.fetchone()
            current_head = row[0] if row else None
        assert current_head == "e1f2a3b4c5d6"

        # 4. Schema Inventory
        inspector = inspect(engine)
        tables = set(inspector.get_table_names(schema=TEST_SCHEMA))
        expected_tables = {
            "sources", "articles", "countries", "article_countries",
            "saved_articles", "article_ai_outputs",
            "daily_editions", "daily_edition_articles", "edition_events",
            "event_editorial_prose", "daily_edition_briefs", "event_clusters",
            "event_cluster_articles", "entities", "entity_aliases",
            "entity_mentions", "event_entities", "signals", "signal_evidence",
            "pipeline_locks"
        }
        assert expected_tables.issubset(tables)

        # 5. FK Validation
        fk_event_entities = inspector.get_foreign_keys("event_entities", schema=TEST_SCHEMA)
        fks_ee = {fk["constrained_columns"][0]: fk["referred_table"] for fk in fk_event_entities}
        assert fks_ee.get("event_cluster_id") == "event_clusters"
        assert fks_ee.get("entity_id") == "entities"

        # 6. Schema validation tool check (passed with engine)
        validate_schema(engine, Base.metadata)

    finally:
        if engine:
            engine.dispose()
        with psycopg.connect(raw_base, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE")
