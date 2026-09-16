"""
Orchestration CLI Command: Generate Daily Edition (Sprint 3 Stage 3E).
Usage: python scripts/generate_daily_edition.py [--date YYYY-MM-DD] [--dry-run]
Pipeline: Selection -> Persistence (GENERATED) -> Market Snapshot -> Synthesis -> Validation -> Persistence.
Does NOT automatically PUBLISH.
"""
import sys
import argparse
import time
from datetime import date, datetime, timezone
import pytz

from app.db import SessionLocal
from services.editorial.selection import (
    generate_daily_edition_selection,
    save_daily_edition_selection,
)
from services.editorial.synthesis import (
    synthesize_event_editorial,
    synthesize_edition_brief_and_themes,
    save_editorial_synthesis,
)
from services.markets import get_market_service


def generate_edition_main():
    parser = argparse.ArgumentParser(description="Generate Daily Edition for a specified date.")
    parser.add_argument("--date", type=str, help="Target edition date in YYYY-MM-DD format.")
    parser.add_argument("--dry-run", action="store_true", help="Run selection and synthesis without committing to database.")
    args = parser.parse_args()

    london_tz = pytz.timezone("Europe/London")
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"Error: Invalid date format '{args.date}'. Expected YYYY-MM-DD.")
            sys.exit(1)
    else:
        target_date = datetime.now(london_tz).date()

    print("================================================================================")
    print(f"GENERATING DAILY EDITION FOR DATE: {target_date} {'(DRY RUN)' if args.dry_run else ''}")
    print("================================================================================")

    start_time = time.time()
    db = SessionLocal()

    try:
        # 1. Selection
        print("[1/4] Running Editorial Selection Engine...")
        audit_res = generate_daily_edition_selection(db=db, target_date=target_date)

        print(f"      Eligible Articles:   {audit_res.candidate_articles_count}")
        print(f"      Candidate Clusters:  {audit_res.candidate_events_count}")
        print(f"      Selected Events:     {audit_res.selected_events_count}")
        print(f"      Readiness Gate:      {audit_res.readiness}")
        print(f"      Lead Story:          {audit_res.lead_story_title or 'None'}")

        if audit_res.selected_events_count == 0:
            print(f"\n[RESULT] PREPARING — Edition for {target_date} contains insufficient events.")
            sys.exit(0)

        if args.dry_run:
            print("\n[DRY RUN] Skipping database persistence and synthesis.")
            sys.exit(0)

        # 2. Persist Selection (GENERATED status)
        print("[2/4] Persisting Daily Edition selection...")
        edition = save_daily_edition_selection(db=db, edition_audit=audit_res, target_date=target_date, status="GENERATED")

        # Capture market snapshot for historical fidelity
        try:
            ms = get_market_service()
            if hasattr(ms, "_cached_snapshots") and ms._cached_snapshots:
                snap_dict = {
                    snap.symbol: {
                        "name": snap.display_name,
                        "price": snap.latest_close,
                        "change": snap.change_value,
                        "change_percent": snap.change_percent,
                        "direction": snap.direction.value if hasattr(snap.direction, "value") else str(snap.direction),
                    }
                    for snap in ms._cached_snapshots
                }
                meta = dict(edition.metadata_json or {})
                meta["market_snapshot"] = snap_dict
                edition.metadata_json = meta
                db.commit()
        except Exception as snap_err:
            print(f"      Warning: Could not capture market snapshot: {snap_err}")

        # 3. Editorial Synthesis
        print("[3/4] Synthesizing Editorial Prose & Brief...")
        prose_results = []
        fallback_count = 0
        success_count = 0

        for sel_ev in audit_res.selected_events:
            ev_res = synthesize_event_editorial(db=db, event_selection=sel_ev, edition_date=target_date)
            prose_results.append(ev_res)
            if ev_res.status == "SUCCESS":
                success_count += 1
            else:
                fallback_count += 1

        brief_res = synthesize_edition_brief_and_themes(db=db, edition_audit=audit_res, event_prose_results=prose_results)

        # 4. Save Synthesis
        print("[4/4] Saving Editorial Synthesis Snapshots...")
        save_editorial_synthesis(db=db, edition=edition, event_prose_results=prose_results, edition_brief_result=brief_res)

        elapsed = time.time() - start_time
        status_str = "SUCCESS_WITH_FALLBACKS" if fallback_count > 0 else "SUCCESS"

        print("================================================================================")
        print(f"GENERATION COMPLETE ({elapsed:.2f}s)")
        print(f"  Status:               {status_str}")
        print(f"  Edition ID:           {edition.id}")
        print(f"  Events Synthesized:   {len(prose_results)} (Success: {success_count}, Fallback: {fallback_count})")
        print(f"  Morning Brief Status: {brief_res.status}")
        print(f"  Themes Generated:     {len(brief_res.key_themes_json)}")
        print("================================================================================")

    except Exception as exc:
        print(f"\n[ERROR] Edition Generation Failed: {exc}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    generate_edition_main()
