"""
Local-first Execution Lock & Overlap Protection Guard (Sprint 1 Stage 1C Phase 3).
Prevents concurrent pipeline cycles or duplicate scheduled jobs from running simultaneously.
Uses PostgreSQL Advisory Locks (pg_try_advisory_lock) with a safe DB lock table fallback on SQLite.
"""
import contextlib
import logging
import zlib
from datetime import datetime, timedelta, timezone
from typing import Generator
from sqlalchemy import Boolean, Column, DateTime, String, text
from sqlalchemy.orm import Session

from app.db import Base

logger = logging.getLogger("services.lock")


class PipelineLockModel(Base):
    __tablename__ = "pipeline_locks"

    lock_name = Column(String(50), primary_key=True)
    is_locked = Column(Boolean, nullable=False, default=False)
    locked_at = Column(DateTime(timezone.utc), nullable=True)


def _get_advisory_lock_id(lock_name: str) -> int:
    """Generates a stable 64-bit signed integer for PostgreSQL advisory locking."""
    # zlib.crc32 returns uint32; fit into 32-bit signed int for PG compatibility
    return zlib.crc32(lock_name.encode("utf-8")) & 0x7FFFFFFF


@contextlib.contextmanager
def pipeline_lock(
    session: Session,
    lock_name: str = "pipeline_cycle",
    stale_seconds: int = 600,
) -> Generator[bool, None, None]:
    """
    Context manager that attempts to acquire an execution lock for lock_name.
    Yields True if lock was successfully acquired.
    Yields False if another process is actively holding the lock (SKIPPED_ALREADY_RUNNING).
    """
    now = datetime.now(timezone.utc)
    is_postgres = False
    lock_id = _get_advisory_lock_id(lock_name)

    try:
        bind = session.get_bind()
        if bind and bind.dialect.name == "postgresql":
            is_postgres = True
    except Exception:
        pass

    acquired = False

    if is_postgres:
        try:
            res = session.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": lock_id}).scalar()
            acquired = bool(res)
        except Exception as exc:
            logger.warning(f"PostgreSQL advisory lock error: {exc}; falling back to DB table lock.")
            is_postgres = False

    if not is_postgres:
        # DB Table Lock Fallback (SQLite & generic SQL)
        try:
            Base.metadata.create_all(bind, tables=[PipelineLockModel.__table__])
        except Exception:
            pass

        try:
            lock_row = session.query(PipelineLockModel).filter(PipelineLockModel.lock_name == lock_name).first()
            if not lock_row:
                lock_row = PipelineLockModel(lock_name=lock_name, is_locked=True, locked_at=now)
                session.add(lock_row)
                session.commit()
                acquired = True
            else:
                # Check if currently locked and not stale
                locked_at = lock_row.locked_at
                if locked_at and locked_at.tzinfo is None:
                    locked_at = locked_at.replace(tzinfo=timezone.utc)

                is_stale = locked_at and (now - locked_at).total_seconds() > stale_seconds

                if lock_row.is_locked and not is_stale:
                    acquired = False
                else:
                    lock_row.is_locked = True
                    lock_row.locked_at = now
                    session.commit()
                    acquired = True
        except Exception as exc:
            session.rollback()
            logger.error(f"Error acquiring table lock for '{lock_name}': {exc}")
            acquired = False

    try:
        yield acquired
    finally:
        if acquired:
            if is_postgres:
                try:
                    session.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": lock_id})
                    session.commit()
                except Exception as exc:
                    logger.warning(f"Error releasing PostgreSQL advisory lock {lock_id}: {exc}")
            else:
                try:
                    session.rollback()
                    lock_row = session.query(PipelineLockModel).filter(PipelineLockModel.lock_name == lock_name).first()
                    if lock_row:
                        lock_row.is_locked = False
                        session.commit()
                except Exception as exc:
                    session.rollback()
                    logger.warning(f"Error releasing table lock for '{lock_name}': {exc}")
