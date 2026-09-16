"""
CLI tool for generating Daily Intelligence Editions.
Usage:
  python -m scripts.generate_edition --today --dry-run
  python -m scripts.generate_edition --today
  python -m scripts.generate_edition --date 2026-09-13 --force
"""

import argparse
from datetime import date
import json
import sys

from app.db import SessionLocal
from app.models import DailyEdition
from services.edition import generate_daily_edition, resolve_edition_date


def print_diagnostic_report(edition_data: dict, is_persisted: bool = False):
    meta = edition_data.get("metadata_json", {})
    ex = meta.get("excluded_counts", {})

    print("\n" + "=" * 70)
    print(f" DAILY EDITION DIAGNOSTIC REPORT {'(PERSISTED)' if is_persisted else '(DRY RUN)'}")
    print("=" * 70)
    print(f" Edition Date:              {meta.get('edition_date')}")
    print(f" Algorithm Version:         {edition_data.get('algorithm_version', 'edition_v1')}")
    print(f" UTC Window Start:          {meta.get('utc_window_start')}")
    print(f" UTC Window End:            {meta.get('utc_window_end')}")
    print("-" * 70)
    print(f" Eligible Articles:         {meta.get('eligible_count', 0)}")
    print(f" Excluded Out-Of-Scope:     {ex.get('excluded_out_of_scope', 0)}")
    print(f" Excluded NULL Relevance:   {ex.get('excluded_null_relevance', 0)}")
    print(f" Excluded AI Failed:        {ex.get('excluded_ai_failed', 0)}")
    print(f" Excluded Invalid Category: {ex.get('excluded_invalid_category', 0)}")
    print(f" Excluded Inactive Source:  {ex.get('excluded_inactive_source', 0)}")
    print(f" Total Excluded:            {ex.get('total_excluded', 0)}")
    print("-" * 70)
    print(f" Duplicates Suppressed:     {meta.get('suppressed_duplicates_count', 0)}")
    print(f" Final Selected Articles:   {meta.get('selected_article_count', 0)}")
    print(f" Lead Article ID:           {meta.get('lead_article_id')}")
    print(f" Lead Story Title:          {edition_data.get('lead_article', 'N/A')}")
    print("=" * 70)

    print("\n[SECTION BREAKDOWN]")
    sec_counts = meta.get("section_counts", {})
    for sec, cnt in sec_counts.items():
        print(f"  - {sec:<24}: {cnt} articles")

    print("\n[CATEGORY DISTRIBUTION]")
    cat_dist = meta.get("category_distribution", {})
    for cat, cnt in sorted(cat_dist.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {cat:<24}: {cnt} articles")

    print("\n[SOURCE DISTRIBUTION]")
    src_dist = meta.get("source_distribution", {})
    for src, cnt in sorted(src_dist.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {src:<28}: {cnt} articles")

    print("\n[COUNTRY DISTRIBUTION]")
    geo_dist = meta.get("country_distribution", {})
    for cc, cnt in sorted(geo_dist.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {cc:<10}: {cnt} articles")

    caps = meta.get("trigger_caps", [])
    if caps:
        print("\n[TRIGGERED CAPS & FALLBACKS]")
        for c in caps[:10]:
            print(f"  - {c.get('type')}: article_id {c.get('article_id')}")

    print("\n[TOP 10 RANKED CANDIDATE SCORES]")
    top_scores = meta.get("top_ranked_scores", [])
    for idx, cand in enumerate(top_scores, 1):
        print(f"  {idx:2d}. [{cand['score']:5.2f}] ID {cand['article_id']}: {cand['title'][:55]}...")
        print(f"      Reason: {cand['reason']}")

    print("\n" + "=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Generate Daily Intelligence Edition")
    parser.add_argument("--date", type=str, help="Edition date YYYY-MM-DD")
    parser.add_argument("--today", action="store_true", help="Generate edition for today's date")
    parser.add_argument("--force", action="store_true", help="Force regeneration if edition exists")
    parser.add_argument("--dry-run", action="store_true", help="Perform dry run without database writes")

    args = parser.parse_args()

    if not args.date and not args.today:
        print("Error: Specify either --today or --date YYYY-MM-DD")
        sys.exit(1)

    target_date = resolve_edition_date(args.date if args.date else None)

    db = SessionLocal()
    try:
        res = generate_daily_edition(
            db,
            edition_date=target_date,
            force=args.force,
            dry_run=args.dry_run,
        )

        if args.dry_run:
            print_diagnostic_report(res, is_persisted=False)
        elif isinstance(res, DailyEdition):
            edition_dict = {
                "id": res.id,
                "edition_date": str(res.edition_date),
                "algorithm_version": res.algorithm_version,
                "lead_article": res.lead_article.title if res.lead_article else "None",
                "article_count": res.article_count,
                "metadata_json": res.metadata_json or {},
            }
            print_diagnostic_report(edition_dict, is_persisted=True)
            print(f"Successfully persisted DailyEdition #{res.id} for {res.edition_date}.")
        else:
            print(f"Edition for {target_date} already exists. Use --force to regenerate.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
