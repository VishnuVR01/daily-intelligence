import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Source
from scripts.seed_countries import seed_countries

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def seed_sources(
    session: Session, json_path: Path | str | None = None
) -> dict[str, Any]:
    # Ensure prerequisite country reference data exists before inserting sources
    country_summary = seed_countries(session)

    if json_path is None:
        json_path = Path(__file__).resolve().parent.parent / "config" / "sources.json"
    else:
        json_path = Path(json_path)

    if not json_path.exists():
        raise FileNotFoundError(f"Sources config file not found at: {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        sources_data: list[dict[str, Any]] = json.load(f)

    inserted = 0
    updated = 0
    unchanged = 0

    for data in sources_data:
        feed_url = data.get("feed_url")
        name = data.get("name")

        # Find existing record by feed_url first, or fallback to name
        existing: Source | None = None
        if feed_url:
            existing = (
                session.query(Source).filter(Source.feed_url == feed_url).first()
            )
        if not existing and name:
            existing = session.query(Source).filter(Source.name == name).first()

        if existing:
            changed = False
            for field in [
                "name",
                "website_url",
                "feed_url",
                "source_type",
                "category",
                "trust_tier",
                "active",
                "country_code",
                "source_family",
                "provenance",
                "replacement_candidate",
            ]:
                if field in data and getattr(existing, field) != data[field]:
                    setattr(existing, field, data[field])
                    changed = True

            if changed:
                updated += 1
            else:
                unchanged += 1
        else:
            new_source = Source(
                name=data.get("name"),
                feed_url=data.get("feed_url"),
                website_url=data.get("website_url"),
                source_type=data.get("source_type", "rss"),
                category=data.get("category"),
                trust_tier=data.get("trust_tier", "useful"),
                active=data.get("active", True),
                country_code=data.get("country_code"),
                source_family=data.get("source_family", "news"),
                provenance=data.get("provenance", "independent"),
                replacement_candidate=data.get("replacement_candidate", False),
            )
            session.add(new_source)
            inserted += 1


    # Retire any database sources not present in sources.json
    configured_names = {d["name"] for d in sources_data if "name" in d}
    configured_urls = {d["feed_url"] for d in sources_data if d.get("feed_url")}
    db_sources = session.query(Source).all()

    for s in db_sources:
        if s.name not in configured_names and (not s.feed_url or s.feed_url not in configured_urls):
            if len(s.articles) == 0:
                session.delete(s)
            else:
                s.active = False
                s.replacement_candidate = True

    session.commit()

    summary = {
        "countries": country_summary,
        "total": len(sources_data),
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
    }
    return summary


def main() -> None:
    from app.db import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        summary = seed_sources(session)
        logger.info("Source seeding complete:")
        logger.info(f"  Total configured: {summary['total']}")
        logger.info(f"  Inserted:          {summary['inserted']}")
        logger.info(f"  Updated:           {summary['updated']}")
        logger.info(f"  Unchanged:         {summary['unchanged']}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
