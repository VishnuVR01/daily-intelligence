import logging
from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.sql.schema import MetaData

import app.models  # noqa: F401 (Ensure models are registered on Base.metadata)

logger = logging.getLogger("app.schema_validation")


def validate_schema(engine: Engine, metadata: MetaData) -> None:
    """
    Validates that all tables and columns defined in SQLAlchemy models exist in the target database.
    Does NOT alter production data. Raises a RuntimeError if missing columns or tables are detected.
    """
    if not metadata.tables:
        raise RuntimeError("No SQLAlchemy model tables registered in MetaData for validation.")

    inspector = inspect(engine)
    db_tables = set(inspector.get_table_names())

    missing_tables = []
    missing_columns = []

    for table_name, table in metadata.tables.items():
        if table_name not in db_tables:
            missing_tables.append(table_name)
            continue

        existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
        for col in table.columns:
            if col.name not in existing_cols:
                missing_columns.append(f"{table_name}.{col.name}")

    if missing_tables or missing_columns:
        error_msg = (
            "\n" + "=" * 60 + "\n"
            "DATABASE SCHEMA VALIDATION ERROR:\n"
            "The database schema is out of sync with application models.\n"
        )
        if missing_tables:
            error_msg += f"  - Missing Tables: {', '.join(missing_tables)}\n"
        if missing_columns:
            error_msg += f"  - Missing Columns: {', '.join(missing_columns)}\n"
        error_msg += (
            "\nPlease run Alembic migrations to apply pending schema changes:\n"
            "    python -m alembic upgrade head\n"
            + "=" * 60 + "\n"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    logger.info("Schema validation successful: All model tables and columns exist in database.")
