"""
CLI Command: Explicitly Publish Daily Edition (Sprint 3 Stage 3E).
Usage: python scripts/publish_daily_edition.py --date YYYY-MM-DD
Verifies readiness, selection presence, synthesis availability, and sets status='PUBLISHED'.
"""
import sys
import argparse
from datetime import datetime, timezone
import pytz

from app.db import SessionLocal
from services.editorial.publication import publish_daily_edition


def publish_edition_main():
    parser = argparse.ArgumentParser(description="Publish Daily Edition for a specified date.")
    parser.add_argument("--date", type=str, required=True, help="Target edition date in YYYY-MM-DD format.")
    args = parser.parse_args()

    try:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        print(f"Error: Invalid date format '{args.date}'. Expected YYYY-MM-DD.")
        sys.exit(1)

    print("================================================================================")
    print(f"PUBLISHING DAILY EDITION FOR DATE: {target_date}")
    print("================================================================================")

    db = SessionLocal()
    try:
        edition = publish_daily_edition(db=db, target_date=target_date)
        pub_at = (edition.metadata_json or {}).get("published_at", datetime.now(timezone.utc).isoformat())

        print(f"SUCCESS: Daily Edition {edition.id} ({target_date}) is now PUBLISHED.")
        print(f"  Published At:   {pub_at}")
        print(f"  Status:         {edition.status}")
        print(f"  Event Count:    {edition.event_count}")
        print(f"  Readiness:      {edition.readiness}")
        print("================================================================================")

    except Exception as exc:
        print(f"PUBLICATION FAILED: {exc}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    publish_edition_main()
