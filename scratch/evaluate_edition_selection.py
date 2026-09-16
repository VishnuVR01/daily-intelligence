"""
3-Day Real Archive Backtest & Evaluation Script (Sprint 3 Stage 3C).
Executes Stage 3C Daily Edition Selection Engine against real archive dates,
prints rejection audits, section/source distributions, and metrics.
"""
from datetime import date, datetime, timezone
from app.db import SessionLocal
from services.editorial.selection import (
    generate_daily_edition_selection,
    save_daily_edition_selection,
)

TEST_DATES = [
    date(2026, 9, 15),
    date(2026, 9, 14),
    date(2026, 9, 13),
]

def run_edition_backtest():
    db = SessionLocal()
    try:
        print("================================================================================")
        print("STAGE 3C: DAILY EDITION SELECTION ENGINE — 3-DAY REAL BACKTEST & AUDIT")
        print("================================================================ algorithm_version: edition_v1\n")

        for t_date in TEST_DATES:
            print(f"--- EVALUATING EDITION DATE: {t_date} ---")
            audit_res = generate_daily_edition_selection(
                db=db,
                target_date=t_date,
                min_quality_threshold=50.0,
                lead_quality_threshold=70.0,
                max_edition_size=20,
                min_publishable_size=10,
                max_per_source=2,
                max_section_share=0.30,
            )

            print(f"Readiness Status:          {audit_res.readiness}")
            print(f"Candidate Articles Count:  {audit_res.candidate_articles_count}")
            print(f"Candidate Events Count:    {audit_res.candidate_events_count}")
            print(f"Selected Events Count:     {audit_res.selected_events_count}")
            print(f"Lead Story Title:          {audit_res.lead_story_title or 'None'}")
            print(f"Rejection Reasons Breakdown: {audit_res.rejected_counts_by_reason}")
            print(f"Section Distribution:      {audit_res.audit_json.get('section_counts', {})}")

            print("\n  SELECTED EDITION EVENTS:")
            for idx, ev in enumerate(audit_res.selected_events, 1):
                clean_title = ev.canonical_title.encode("ascii", "replace").decode("ascii")
                print(f"   {idx:2d}. [{ev.role:7s}] Score: {ev.event_score:5.1f} | Sec: {ev.section:13s} | Sources: {ev.distinct_source_count} | {clean_title[:65]}")

            print("\n--------------------------------------------------------------------------------\n")

    finally:
        db.close()

if __name__ == "__main__":
    run_edition_backtest()
