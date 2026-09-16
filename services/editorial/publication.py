"""
Publication Service for Daily Edition (Sprint 3 Stage 3E).
Implements explicit, transactional publication workflow.
Verifies readiness, selection presence, synthesis availability, and locks automatic regeneration.
"""
from datetime import datetime, date, timezone
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models import DailyEdition, EditionEvent, EventEditorialProse, EditionBrief

logger = logging.getLogger("editorial_publication")


def publish_daily_edition(db: Session, target_date: date) -> DailyEdition:
    """
    Explicitly publishes a DailyEdition for target_date.
    Validates readiness gate, selection presence, and synthesis completion before publishing.
    """
    edition = db.query(DailyEdition).filter(DailyEdition.edition_date == target_date).first()
    if not edition:
        raise ValueError(f"No Daily Edition found for date {target_date}.")

    if edition.status == "PUBLISHED":
        logger.info(f"Daily Edition for {target_date} is already PUBLISHED.")
        return edition

    # 1. Readiness Gate Verification
    if edition.readiness != "READY":
        raise ValueError(f"Daily Edition for {target_date} readiness is '{edition.readiness}', expected 'READY'.")

    if not edition.edition_events or len(edition.edition_events) == 0:
        raise ValueError(f"Daily Edition for {target_date} contains no selected events.")

    # 2. Synthesis Availability Verification
    brief = db.query(EditionBrief).filter(EditionBrief.edition_id == edition.id).first()
    if not brief:
        raise ValueError(f"Daily Edition for {target_date} lacks a synthesized Morning Brief.")

    ee_ids = [ee.id for ee in edition.edition_events]
    prose_records = db.query(EventEditorialProse).filter(EventEditorialProse.edition_event_id.in_(ee_ids)).all()
    prose_map = {p.edition_event_id: p for p in prose_records}

    for ee in edition.edition_events:
        if ee.id not in prose_map:
            raise ValueError(f"Event cluster '{ee.event_cluster_id}' in edition {target_date} lacks synthesized editorial prose.")

    # 3. Transactional Status Update
    meta = dict(edition.metadata_json or {})
    meta["published_at"] = datetime.now(timezone.utc).isoformat()
    edition.metadata_json = meta
    edition.status = "PUBLISHED"

    db.commit()
    db.refresh(edition)
    logger.info(f"Successfully published Daily Edition for {target_date} (ID: {edition.id}).")
    return edition
