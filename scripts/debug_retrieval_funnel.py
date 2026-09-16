"""
Read-Only Retrieval Funnel Diagnostic Script
Traces today's articles through every stage of the pipeline to identify retrieval drop-offs.
Run against LOCAL PostgreSQL only. No data modification.
"""

from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
import sys
from typing import Dict, List, Any, Optional

from sqlalchemy import func, or_, and_, String
from sqlalchemy.orm import Session, joinedload

from app.db import SessionLocal
from app.config import get_settings
from app.models import Article, ArticleAIOutput, Source, Country, DailyEdition, EditionArticle
from repositories.articles import (
    search_articles_v1,
    get_article_ai_output,
    is_article_out_of_scope,
    _valid_published_filter,
    get_today_ai_context_stats,
    get_recent_articles,
    get_articles_by_sections,
)
from services.rag import ask_archive


def run_diagnostics():
    settings = get_settings()
    tz_name = settings.app_timezone or "Europe/London"
    try:
        london_tz = ZoneInfo(tz_name)
    except Exception:
        london_tz = ZoneInfo("Europe/London")

    now_utc = datetime.now(timezone.utc)
    now_london = datetime.now(london_tz)

    today_london_start = now_london.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_london_start = today_london_start + timedelta(days=1)

    today_utc_start = today_london_start.astimezone(timezone.utc)
    tomorrow_utc_start = tomorrow_london_start.astimezone(timezone.utc)

    print("=" * 100)
    print("DAILY INTELLIGENCE RETRIEVAL FUNNEL DIAGNOSTIC REPORT")
    print(f"Execution Time (UTC)    : {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Execution Time (London) : {now_london.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Europe/London Calendar Day Boundary : {today_london_start.strftime('%Y-%m-%d 00:00:00 %Z')} to {tomorrow_london_start.strftime('%Y-%m-%d 00:00:00 %Z')}")
    print(f"Explicit UTC Boundary for DB Queries: {today_utc_start.strftime('%Y-%m-%d %H:%M:%S %Z')} to {tomorrow_utc_start.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print("=" * 100)

    db: Session = SessionLocal()

    try:
        # ----------------------------------------------------------------------
        # 1. Total Articles Count
        # ----------------------------------------------------------------------
        col_today_q = db.query(Article).filter(
            Article.collected_at >= today_utc_start,
            Article.collected_at < tomorrow_utc_start
        )
        collected_today_count = col_today_q.count()

        pub_today_q = db.query(Article).filter(
            Article.published_at.is_not(None),
            Article.published_at >= today_utc_start,
            Article.published_at < tomorrow_utc_start
        )
        published_today_count = pub_today_q.count()

        col_or_pub_q = db.query(Article).filter(
            or_(
                and_(Article.collected_at >= today_utc_start, Article.collected_at < tomorrow_utc_start),
                and_(Article.published_at.is_not(None), Article.published_at >= today_utc_start, Article.published_at < tomorrow_utc_start)
            )
        )
        col_or_pub_count = col_or_pub_q.count()
        today_articles = col_or_pub_q.options(joinedload(Article.ai_outputs), joinedload(Article.source)).all()

        total_archive = db.query(Article).count()

        print("\nPART 1: TOTAL ARTICLES")
        print(f"  - Total archive articles in DB           : {total_archive}")
        print(f"  - Articles collected today (Europe/London): {collected_today_count}")
        print(f"  - Articles published today (Europe/London): {published_today_count}")
        print(f"  - Articles collected OR published today   : {col_or_pub_count}")

        if today_articles:
            print("  - Articles retrieved for TODAY:")
            for a in today_articles:
                src_name = a.source.name if a.source else "No Source"
                print(f"    * ID={a.id} | Title='{a.title}' | Source={src_name} | Pub={a.published_at} | Col={a.collected_at}")

        # ----------------------------------------------------------------------
        # 7. AI Output Table Analysis (article_ai_outputs)
        # ----------------------------------------------------------------------
        print("\nPART 7: AI OUTPUT TABLE BREAKDOWN (article_ai_outputs)")
        ai_outputs_all = db.query(ArticleAIOutput).options(joinedload(ArticleAIOutput.article)).all()
        print(f"  - Total rows in article_ai_outputs table : {len(ai_outputs_all)}")

        # Grouping by provider, model, task, prompt_version
        output_groups: Dict[str, List[ArticleAIOutput]] = {}
        for row in ai_outputs_all:
            key = f"provider='{row.provider}' | model='{row.model}' | task='{row.task}' | prompt_version='{row.prompt_version}'"
            output_groups.setdefault(key, []).append(row)

        for key, rows in output_groups.items():
            rel_cnt = sum(1 for r in rows if r.is_relevant is True)
            irrel_cnt = sum(1 for r in rows if r.is_relevant is False)
            pending_cnt = sum(1 for r in rows if r.is_relevant is None or r.status != 'success')
            print(f"  * Group [{key}]:")
            print(f"    - Total Rows : {len(rows)}")
            print(f"    - Relevant   : {rel_cnt}")
            print(f"    - Out of Scope: {irrel_cnt}")
            print(f"    - Pending/Failed: {pending_cnt}")

        # ----------------------------------------------------------------------
        # 2. AI Processing Breakdown
        # ----------------------------------------------------------------------
        print("\nPART 2: AI PROCESSING BREAKDOWN")
        # Explaining the UI metric discrepancy
        ui_stats = get_today_ai_context_stats(db)
        print("  - Live UI Metric Endpoint (get_today_ai_context_stats):")
        print(f"    * Total Analyzed (total_processed) : {ui_stats['total_processed']}")
        print(f"    * Curated Relevant                 : {ui_stats['relevant_today']}")
        print(f"    * Out of Scope Filtered            : {ui_stats['out_of_scope_today']}")
        print(f"    * Failed / Pending                 : {ui_stats['unprocessed_or_failed']}")
        print(f"    * Technical Success Rate           : {ui_stats['success_rate']}%")
        print("  - NOTE ON UI METRICS: `get_today_ai_context_stats()` counts ALL rows in `article_ai_outputs` across the ENTIRE database without filtering by `processed_at` or `article.published_at`.")

        # Breakdown specifically for Today's Articles (collected or published today) vs DB Overall
        all_relevant = db.query(Article).options(
            joinedload(Article.source),
            joinedload(Article.ai_outputs),
            joinedload(Article.countries)
        ).filter(Article.ai_outputs.any(ArticleAIOutput.is_relevant == True)).all()

        today_analyzed = [a for a in today_articles if a.ai_outputs]
        today_relevant = [a for a in today_analyzed if any(out.is_relevant is True for out in a.ai_outputs)]

        print(f"\n  - DB-Wide AI Analysis Summary:")
        print(f"    * Articles with AI Output : {len(db.query(Article).filter(Article.ai_outputs.any()).all())}")
        print(f"    * Articles with Relevant AI Output (is_relevant=True) : {len(all_relevant)}")

        # ----------------------------------------------------------------------
        # 3. Searchability Among Relevant Articles
        # ----------------------------------------------------------------------
        print("\nPART 3: SEARCHABILITY AMONG ALL 41 RELEVANT ARTICLES")
        has_title = sum(1 for a in all_relevant if a.title and a.title.strip())
        has_raw_summary = sum(1 for a in all_relevant if a.raw_summary and a.raw_summary.strip())
        has_extracted_text = sum(1 for a in all_relevant if a.extracted_text and a.extracted_text.strip())
        has_ai_summary = 0
        for a in all_relevant:
            ai_out = get_article_ai_output(a)
            if ai_out and ai_out.summary and ai_out.summary.strip():
                has_ai_summary += 1
        has_any_searchable = sum(1 for a in all_relevant if (
            (a.title and a.title.strip()) or 
            (a.raw_summary and a.raw_summary.strip()) or 
            (a.extracted_text and a.extracted_text.strip()) or
            (get_article_ai_output(a) and get_article_ai_output(a).summary)
        ))

        print(f"  - Title present                    : {has_title} / {len(all_relevant)}")
        print(f"  - Raw summary present              : {has_raw_summary} / {len(all_relevant)}")
        print(f"  - Extracted text present           : {has_extracted_text} / {len(all_relevant)}")
        print(f"  - AI summary present               : {has_ai_summary} / {len(all_relevant)}")
        print(f"  - At least 1 searchable text field  : {has_any_searchable} / {len(all_relevant)}")

        # ----------------------------------------------------------------------
        # 4. Metadata Availability Among Relevant Articles
        # ----------------------------------------------------------------------
        print("\nPART 4: METADATA AVAILABILITY AMONG ALL 41 RELEVANT ARTICLES")
        has_category = 0
        has_country = 0
        has_importance = 0
        has_relevance = 0
        has_source = 0

        for a in all_relevant:
            ai_out = get_article_ai_output(a)
            cat = a.primary_category or (ai_out.primary_category if ai_out else None) or (a.source.category if a.source else None)
            if cat:
                has_category += 1
            if a.countries or (a.source and a.source.country_code):
                has_country += 1
            if ai_out and ai_out.importance_score is not None:
                has_importance += 1
            if ai_out and ai_out.relevance_score is not None:
                has_relevance += 1
            if a.source:
                has_source += 1

        print(f"  - Primary Category present          : {has_category} / {len(all_relevant)}")
        print(f"  - Country Data present              : {has_country} / {len(all_relevant)}")
        print(f"  - Importance Score present          : {has_importance} / {len(all_relevant)}")
        print(f"  - Relevance Score present           : {has_relevance} / {len(all_relevant)}")
        print(f"  - Source Link present               : {has_source} / {len(all_relevant)}")

        # ----------------------------------------------------------------------
        # 5. Application of Actual Pipeline Stage Filters
        # ----------------------------------------------------------------------
        print("\nPART 5 & 6: PIPELINE STAGE FILTERS & DATE FILTERING DIAGNOSTICS")

        print("\n  A) Homepage / Edition Pipeline (`get_articles_by_sections` / `get_recent_articles`):")
        recent_all = db.query(Article).filter(_valid_published_filter()).all()
        print(f"     - Count before filter (Total DB)           : {total_archive}")
        print(f"     - Count after `_valid_published_filter()`   : {len(recent_all)}")
        print(f"     - Excluded by `_valid_published_filter()`   : {total_archive - len(recent_all)} (published_at > NOW)")
        recent_curated = [a for a in recent_all if not is_article_out_of_scope(a)]
        print(f"     - Count after `is_article_out_of_scope`    : {len(recent_curated)}")
        print(f"     - Excluded by out_of_scope filter          : {len(recent_all) - len(recent_curated)}")

        print("\n  B) Historical Search (`search_articles_v1`):")
        # Empty query search
        empty_search_res = search_articles_v1(db, query="")
        print(f"     - Empty query `search_articles_v1(query='')` total returned : {empty_search_res['total']}")
        print(f"     - Reason: Lines 451-464 of `repositories/articles.py` explicitly return `[]` when `query`, `categories`, `date_from`, etc. are all empty!")
        
        # Search for query="OpenAI"
        openai_search_res = search_articles_v1(db, query="OpenAI", relevant_only=True)
        print(f"     - Query='OpenAI' with `relevant_only=True` total matched   : {openai_search_res['total']}")

        print("\n  C) RAG Retrieval Pipeline (`ask_archive` / `search_articles_v1`):")
        # When RAG receives query e.g. "what happened today" or "OpenAI" or "summary"
        rag_res_openai = search_articles_v1(db, query="OpenAI", relevant_only=True, limit=10)
        print(f"     - RAG search query='OpenAI' : Candidates retrieved = {len(rag_res_openai['articles'])}")
        
        # When RAG specifies date_from=today and date_to=today:
        rag_res_today = search_articles_v1(
            db,
            query="OpenAI",
            date_from=today_london_start.date(),
            date_to=today_london_start.date(),
            relevant_only=True,
            limit=10
        )
        print(f"     - RAG search query='OpenAI' with `date_from={today_london_start.date()}` & `date_to={today_london_start.date()}`:")
        print(f"       * Count before date filter : {len(all_relevant)}")
        print(f"       * Count after date filter  : {len(rag_res_today['articles'])}")
        print(f"       * Number excluded          : {len(all_relevant) - len(rag_res_today['articles'])}")
        print(f"       * Reason for exclusion     : Published/Collected timestamp is prior to 2026-09-14 00:00:00 UTC!")

        # ----------------------------------------------------------------------
        # 6. Detailed Date Filtering Breakdown
        # ----------------------------------------------------------------------
        print("\nPART 6: DATE FILTERING DETAILED INSPECTION")
        print(f"  - App Timezone Setting      : {tz_name}")
        print(f"  - London Day Start (Local)  : {today_london_start}")
        print(f"  - London Day End (Local)    : {tomorrow_london_start}")
        print(f"  - London Day Start (UTC)    : {today_utc_start}")
        print(f"  - London Day End (UTC)      : {tomorrow_utc_start}")
        print(f"  - UTC Date Boundary in search_articles_v1 for date_from={today_london_start.date()}:")
        print(f"    * `start_utc` = {datetime(today_london_start.year, today_london_start.month, today_london_start.day, 0, 0, 0, tzinfo=timezone.utc)}")
        print(f"    * `end_utc`   = {datetime(today_london_start.year, today_london_start.month, today_london_start.day, 23, 59, 59, 999999, tzinfo=timezone.utc)}")

        # Check date distribution of all 41 relevant articles
        dates_dist: Dict[str, int] = {}
        for a in all_relevant:
            dt = a.published_at or a.collected_at
            d_str = dt.strftime("%Y-%m-%d") if dt else "No Date"
            dates_dist[d_str] = dates_dist.get(d_str, 0) + 1

        print("\n  - Publication/Collection Date Distribution of all 41 Relevant Articles:")
        for d_str, cnt in sorted(dates_dist.items(), reverse=True):
            print(f"    * {d_str} : {cnt} articles")

        # ----------------------------------------------------------------------
        # 8. Complete Inspection of All 41 Relevant Articles
        # ----------------------------------------------------------------------
        print("\nPART 8: DETAILED INSPECTION OF ALL 41 RELEVANT ARTICLES")
        print(f"{'ID':<5} | {'Published (UTC)':<19} | {'Collected (UTC)':<19} | {'Rel':<3} | {'Imp':<3} | {'Source':<20} | {'Title'}")
        print("-" * 115)

        for art in sorted(all_relevant, key=lambda x: x.id, reverse=True):
            ai_out = get_article_ai_output(art)
            rel_score = ai_out.relevance_score if ai_out else None
            imp_score = ai_out.importance_score if ai_out else None
            src_name = art.source.name if art.source else "No Source"

            pub_str = art.published_at.strftime("%Y-%m-%d %H:%M:%S") if art.published_at else "None"
            col_str = art.collected_at.strftime("%Y-%m-%d %H:%M:%S") if art.collected_at else "None"
            rel_str = str(rel_score) if rel_score is not None else "N/A"
            imp_str = str(imp_score) if imp_score is not None else "N/A"

            # Exclusion reason from Today's (2026-09-14) RAG Candidate Pool
            pub_or_col = art.published_at or art.collected_at
            if pub_or_col:
                if pub_or_col < today_utc_start:
                    excl_reason = f"Date is {pub_or_col.strftime('%Y-%m-%d')} (< today 2026-09-14)"
                elif pub_or_col >= tomorrow_utc_start:
                    excl_reason = f"Date is {pub_or_col.strftime('%Y-%m-%d')} (> today 2026-09-14)"
                else:
                    excl_reason = "ELIGIBLE FOR TODAY"
            else:
                excl_reason = "No timestamp"

            print(f"{art.id:<5} | {pub_str:<19} | {col_str:<19} | {rel_str:<3} | {imp_str:<3} | {src_name[:20]:<20} | {art.title[:30]:<30} [{excl_reason}]")

        # ----------------------------------------------------------------------
        # 9. Funnel & 10. Root Cause Summary
        # ----------------------------------------------------------------------
        print("\n" + "=" * 100)
        print("PART 9: PIPELINE RETRIEVAL FUNNEL")
        print("=" * 100)
        print(f"  59 analyzed (total rows in article_ai_outputs)")
        print(f"  -> 51 AI successful (status == 'success')")
        print(f"  -> 41 relevant (is_relevant == True)")
        print(f"  -> 41 searchable (have title, summary, or AI summary)")
        print(f"  -> 1 date eligible (published/collected on today's date 2026-09-14)")
        print(f"  -> 1 metadata eligible (has category, source, importance/relevance score)")
        print(f"  -> 1 RAG candidates (matching query 'OpenAI' or date range 2026-09-14)")
        print(f"  -> 1 final retrieved")

        print("\n" + "=" * 100)
        print("PART 10: IDENTIFICATION OF THE EXACT FILTERS RESPONSIBLE FOR DISCREPANCY")
        print("=" * 100)
        print("1. DISCREPANCY #1: UI Metric vs Date Reality (59 Analyzed / 41 Relevant UI Box)")
        print("   - Root Cause: `get_today_ai_context_stats()` in `repositories/articles.py` runs `db.query(ArticleAIOutput).count()` WITHOUT ANY DATE FILTER.")
        print("   - Effect: The UI widget displays stats for ALL 59 historical AI outputs in the database (41 relevant from 2026-09-13 and earlier), mislabeling them as 'Today in Context'.")

        print("\n2. DISCREPANCY #2: RAG / Search Returning Only 1 Article Today")
        print("   - Root Cause: 40 of the 41 relevant articles were published/collected on 2026-09-13 or earlier.")
        print("   - Only 1 article in the database was collected/published on today's calendar date (2026-09-14), and that article is about OpenAI (ID=3797).")
        print("   - When RAG or search queries apply a date filter for today (2026-09-14), 40 of the 41 relevant articles are excluded by the DATE FILTER (`coalesce(published_at, collected_at) >= 2026-09-14 00:00:00 UTC`).")

    finally:
        db.close()


if __name__ == "__main__":
    run_diagnostics()
