import pytest
from sqlalchemy import Column, Integer, String, Table, create_engine
from sqlalchemy.orm import DeclarativeBase

from app.schema_validation import validate_schema


class BaseTest(DeclarativeBase):
    pass


class DummyModel(BaseTest):
    __tablename__ = "dummy_table"
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    missing_col = Column(String(50))


def test_schema_validation_detects_missing_column():
    engine = create_engine("sqlite:///:memory:")
    # Manually create table without missing_col
    with engine.connect() as conn:
        conn.exec_driver_sql("CREATE TABLE dummy_table (id INTEGER PRIMARY KEY, name VARCHAR(50));")
        conn.commit()

    with pytest.raises(RuntimeError) as exc_info:
        validate_schema(engine, BaseTest.metadata)

    assert "dummy_table.missing_col" in str(exc_info.value)
    assert "python -m alembic upgrade head" in str(exc_info.value)


def test_schema_validation_passes_when_all_columns_exist():
    engine = create_engine("sqlite:///:memory:")
    BaseTest.metadata.create_all(engine)

    # Should not raise any exception
    validate_schema(engine, BaseTest.metadata)
