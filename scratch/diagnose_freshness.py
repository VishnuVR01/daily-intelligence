import sys
import json
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import func, desc, or_, and_
from sqlalchemy.orm import joinedload

sys.path.insert(0, '.')
from app.db import SessionLocal
from app.models import Article, ArticleAIOutput, Source, DailyEdition, EditionArticle

def run_diagnostic():
    db = SessionLocal()
    london_tz = ZoneInfo("Europe/London")
    now_utc = datetime.now(timezone.utc)
    now_london = now_utc.astimezone(london_tz)

    print("=" * 80)
    print("STAGE 2C.1 LATEST BRIEFINGS FRESHNESS DIAGNOSTIC")
    print(f"Current Local Time (Europe/London): {now_london.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Current UTC Time:                  {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print("=" * 80)

    # ---------------------------------------------------------
    # 1. DATABASE FRESHNESS AUDIT
    # ---------------------------------------------------------
    print("\n--- 1. DATABASE FRESHNESS AUDIT ---")
    
    max_collected = db.query(func.max(Article.collected_at)).scalar()
    max_published = db.query(func.max(Article.published_at)).scalar()
    
    if max_collected and max_collected.tzinfo is None:
        max_collected = max_collected.replace(tzinfo=timezone.utc)
    if max_published and max_published.tzinfo is None:
        max_published = max_published.replace(tzinfo=timezone.utc)

    max_collected_lon = max_collected.astimezone(london_tz) if max_collected else None
    max_published_lon = max_published.astimezone(london_tz) if max_published else None

    mins_since_collected = (now_utc - max_collected).total_seconds() / 60.0 if max_collected else None

    print(f"MAX(Article.collected_at): {max_collected_lon.strftime('%Y-%m-%d %H:%M:%S %Z') if max_collected_lon else 'N/A'}")
    print(f"MAX(Article.published_at): {max_published_lon.strftime('%Y-%m-%d %H:%M:%S %Z') if max_published_lon else 'N/A'}")
    print(f"Minutes since last collection: {mins_since_collected:.1f} minutes" if mins_since_collected is not None else "N/A")

    # Time cutoffs (Europe/London 15:00 today)
    today_1500_lon = now_london.replace(hour=15, minute=0, second=0, microsecond=0)
    today_1500_utc = today_1500_lon.astimezone(timezone.utc)

    c_30m = db.query(Article).filter(Article.collected_at >= now_utc - timedelta(minutes=30)).count()
    c_1h  = db.query(Article).filter(Article.collected_at >= now_utc - timedelta(hours=1)).count()
    c_2h  = db.query(Article).filter(Article.collected_at >= now_utc - timedelta(hours=2)).count()
    c_4h  = db.query(Article).filter(Article.collected_at >= now_utc - timedelta(hours=4)).count()
    c_1500 = db.query(Article).filter(Article.collected_at >= today_1500_utc).count()

    print(f"Articles collected in last 30 minutes: {c_30m}")
    print(f"Articles collected in last 1 hour:     {c_1h}")
    print(f"Articles collected in last 2 hours:    {c_2h}")
    print(f"Articles collected in last 4 hours:    {c_4h}")
    print(f"Articles collected since 15:00 local:  {c_1500}")

    print("\nNewest 20 articles by collected_at:")
    newest_20_collected = (
        db.query(Article)
        .options(joinedload(Article.source))
        .order_by(Article.collected_at.desc())
        .limit(20)
        .all()
    )

    print(f"{'ID':<6} | {'Source':<25} | {'Title':<40} | {'Published (London)':<22} | {'Collected (London)':<22}")
    print("-" * 125)
    for a in newest_20_collected:
        pub_str = a.published_at.astimezone(london_tz).strftime('%Y-%m-%d %H:%M:%S') if a.published_at else 'N/A'
        col_str = a.collected_at.astimezone(london_tz).strftime('%Y-%m-%d %H:%M:%S') if a.collected_at else 'N/A'
        src_name = a.source.name if a.source else "Unknown"
        title_clean = a.title.encode('ascii', 'replace').decode('ascii')
        title_trunc = (title_clean[:37] + "...") if len(title_clean) > 40 else title_clean
        print(f"{a.id:<6} | {src_name[:25]:<25} | {title_trunc:<40} | {pub_str:<22} | {col_str:<22}")

    # ---------------------------------------------------------
    # 2. SOURCE INGESTION AUDIT
    # ---------------------------------------------------------
    print("\n--- 2. SOURCE INGESTION AUDIT ---")
    # Check max collected_at per source
    sources_status = (
        db.query(
            Source.name,
            func.max(Article.collected_at).label("max_collected"),
            func.count(Article.id).label("total_arts")
        )
        .join(Article, Article.source_id == Source.id, isouter=True)
        .group_by(Source.name)
        .order_by(desc("max_collected"))
        .all()
    )
    print("Recent activity per source (Top 10 most recently collected):")
    for s_name, max_c, count in sources_status[:10]:
        max_c_str = max_c.astimezone(london_tz).strftime('%Y-%m-%d %H:%M:%S') if max_c else 'Never'
        print(f"  Source: {s_name[:30]:<30} | Last Collected: {max_c_str} | Total Articles: {count}")

    # ---------------------------------------------------------
    # 3. AI QUEUE AUDIT
    # ---------------------------------------------------------
    print("\n--- 3. AI QUEUE AUDIT ---")
    arts_since_1500 = (
        db.query(Article)
        .options(joinedload(Article.ai_outputs))
        .filter(Article.collected_at >= today_1500_utc)
        .all()
    )
    
    unprocessed = 0
    processing = 0
    comp_relevant = 0
    comp_out_of_scope = 0
    failed = 0
    retryable = 0

    for a in arts_since_1500:
        if not a.ai_outputs:
            unprocessed += 1
        else:
            out = a.ai_outputs[0]
            st = out.status
            if st == "processing":
                processing += 1
            elif st == "success":
                if out.is_relevant:
                    comp_relevant += 1
                else:
                    comp_out_of_scope += 1
            elif st == "out_of_scope":
                comp_out_of_scope += 1
            elif st in ["failed", "timeout", "unavailable", "temporary_error"]:
                failed += 1
                retryable += 1
            else:
                failed += 1

    print(f"Total articles collected since 15:00 local: {len(arts_since_1500)}")
    print(f"  UNPROCESSED:             {unprocessed}")
    print(f"  PROCESSING:              {processing}")
    print(f"  COMPLETED_RELEVANT:      {comp_relevant}")
    print(f"  COMPLETED_OUT_OF_SCOPE:  {comp_out_of_scope}")
    print(f"  FAILED:                  {failed}")
    print(f"  RETRYABLE:               {retryable}")

    print("\nNewest 20 articles & AI status:")
    print(f"{'ID':<6} | {'Collected (London)':<22} | {'AI Status':<18} | {'Is Relevant':<11} | {'Title':<45}")
    print("-" * 110)
    for a in newest_20_collected:
        col_str = a.collected_at.astimezone(london_tz).strftime('%Y-%m-%d %H:%M:%S') if a.collected_at else 'N/A'
        if not a.ai_outputs:
            status_str = "UNPROCESSED"
            rel_str = "N/A"
        else:
            out = a.ai_outputs[0]
            status_str = out.status
            rel_str = str(out.is_relevant)
        title_trunc = (a.title[:42] + "...") if len(a.title) > 45 else a.title
        print(f"{a.id:<6} | {col_str:<22} | {status_str:<18} | {rel_str:<11} | {title_trunc:<45}")

    # ---------------------------------------------------------
    # 4. AI WORKER AUDIT
    # ---------------------------------------------------------
    print("\n--- 4. AI WORKER AUDIT ---")
    latest_ai_output = (
        db.query(ArticleAIOutput)
        .order_by(ArticleAIOutput.created_at.desc())
        .first()
    )
    if latest_ai_output:
        proc_at = latest_ai_output.processed_at or latest_ai_output.created_at
        proc_at_lon = proc_at.astimezone(london_tz) if proc_at else None
        print(f"Last AI Output record created_at: {proc_at_lon.strftime('%Y-%m-%d %H:%M:%S %Z') if proc_at_lon else 'N/A'}")
        print(f"Last AI Output details: ID={latest_ai_output.id}, Article ID={latest_ai_output.article_id}, Status={latest_ai_output.status}, Relevant={latest_ai_output.is_relevant}")
    else:
        print("No AI Output records found.")

    stuck_processing = (
        db.query(ArticleAIOutput)
        .filter(ArticleAIOutput.status == "processing")
        .all()
    )
    print(f"Articles currently in 'processing' status: {len(stuck_processing)}")

    # ---------------------------------------------------------
    # 5. LATEST RELEVANT ARTICLE
    # ---------------------------------------------------------
    print("\n--- 5. LATEST RELEVANT ARTICLE ---")
    latest_relevant = (
        db.query(Article)
        .join(ArticleAIOutput, Article.id == ArticleAIOutput.article_id)
        .options(joinedload(Article.source), joinedload(Article.ai_outputs))
        .filter(ArticleAIOutput.status == "success", ArticleAIOutput.is_relevant == True)
        .order_by(Article.collected_at.desc())
        .first()
    )
    if latest_relevant:
        pub_str = latest_relevant.published_at.astimezone(london_tz).strftime('%Y-%m-%d %H:%M:%S') if latest_relevant.published_at else 'N/A'
        col_str = latest_relevant.collected_at.astimezone(london_tz).strftime('%Y-%m-%d %H:%M:%S') if latest_relevant.collected_at else 'N/A'
        out = latest_relevant.ai_outputs[0]
        proc_str = out.processed_at.astimezone(london_tz).strftime('%Y-%m-%d %H:%M:%S') if out.processed_at else 'N/A'
        print(f"Newest Relevant Article ID:   {latest_relevant.id}")
        print(f"Title:                         {latest_relevant.title}")
        print(f"Source:                        {latest_relevant.source.name if latest_relevant.source else 'N/A'}")
        print(f"Published (London):            {pub_str}")
        print(f"Collected (London):            {col_str}")
        print(f"Processed (London):            {proc_str}")
    else:
        print("No relevant articles found.")

    # ---------------------------------------------------------
    # 6. & 7. /LATEST QUERY AUDIT & BALANCED VS CHRONOLOGICAL
    # ---------------------------------------------------------
    print("\n--- 6 & 7. /LATEST QUERY AUDIT & BALANCED VS PURE CHRONOLOGICAL ---")
    from repositories.articles import get_recent_articles

    balanced_articles = get_recent_articles(db, category=None, limit=50, mode="balanced")
    chrono_articles = get_recent_articles(db, category=None, limit=50, mode="chronological")

    print(f"Total articles returned (Balanced):      {len(balanced_articles)}")
    if balanced_articles:
        top_b = balanced_articles[0]
        top_b_col = top_b.collected_at.astimezone(london_tz).strftime('%Y-%m-%d %H:%M:%S') if top_b.collected_at else 'N/A'
        top_b_pub = top_b.published_at.astimezone(london_tz).strftime('%Y-%m-%d %H:%M:%S') if top_b.published_at else 'N/A'
        print(f"  Newest in Balanced: ID={top_b.id} | Source={top_b.source.name if top_b.source else 'N/A'} | Published={top_b_pub} | Collected={top_b_col} | Title={top_b.title[:40]}")

    print(f"Total articles returned (Chronological): {len(chrono_articles)}")
    if chrono_articles:
        top_c = chrono_articles[0]
        top_c_col = top_c.collected_at.astimezone(london_tz).strftime('%Y-%m-%d %H:%M:%S') if top_c.collected_at else 'N/A'
        top_c_pub = top_c.published_at.astimezone(london_tz).strftime('%Y-%m-%d %H:%M:%S') if top_c.published_at else 'N/A'
        print(f"  Newest in Chrono:   ID={top_c.id} | Source={top_c.source.name if top_c.source else 'N/A'} | Published={top_c_pub} | Collected={top_c_col} | Title={top_c.title[:40]}")

    # ---------------------------------------------------------
    # 8. END-TO-END TRACE (5 NEWEST ARTICLES IN POSTGRESQL)
    # ---------------------------------------------------------
    print("\n--- 8. END-TO-END TRACE (5 NEWEST ARTICLES IN POSTGRESQL) ---")
    newest_5_db = (
        db.query(Article)
        .options(joinedload(Article.source), joinedload(Article.ai_outputs))
        .order_by(func.coalesce(Article.published_at, Article.collected_at).desc())
        .limit(5)
        .all()
    )

    balanced_ids = [a.id for a in balanced_articles]
    chrono_ids = [a.id for a in chrono_articles]

    trace_results = []
    for a in newest_5_db:
        ai_out = a.ai_outputs[0] if a.ai_outputs else None
        ai_state = ai_out.status if ai_out else "UNPROCESSED"
        is_rel = ai_out.is_relevant if ai_out else None
        
        # Latest Eligible logic in get_recent_articles:
        # _valid_published_filter() requires published_at is None OR published_at <= now()
        now = datetime.now(timezone.utc)
        pub = a.published_at
        if pub and pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        eligible = (pub is None or pub <= now)
        
        ret_balanced = a.id in balanced_ids
        ret_chrono = a.id in chrono_ids

        reason = "Included"
        if not eligible:
            reason = "Future published_at date"
        elif not ret_balanced and ret_chrono:
            reason = "Dropped by apply_editorial_diversity (max_per_source=2 cap)"
        elif not ret_balanced and not ret_chrono:
            reason = "Cut off by LIMIT 100 before ranking"

        col_str = a.collected_at.astimezone(london_tz).strftime('%Y-%m-%d %H:%M:%S') if a.collected_at else 'N/A'
        pub_str = a.published_at.astimezone(london_tz).strftime('%Y-%m-%d %H:%M:%S') if a.published_at else 'N/A'

        trace_results.append({
            "id": a.id,
            "title": a.title,
            "source": a.source.name if a.source else "N/A",
            "published_london": pub_str,
            "collected_london": col_str,
            "ai_state": ai_state,
            "is_relevant": is_rel,
            "eligible": eligible,
            "returned_balanced": ret_balanced,
            "returned_chrono": ret_chrono,
            "reason": reason,
        })

    print(json.dumps(trace_results, indent=2))

    # ---------------------------------------------------------
    # 9. TEST / FIXTURE CONTAMINATION
    # ---------------------------------------------------------
    print("\n--- 9. TEST / FIXTURE CONTAMINATION AUDIT ---")
    test_articles = (
        db.query(Article)
        .options(joinedload(Article.source))
        .filter(
            or_(
                Article.title.ilike("%test%"),
                Article.canonical_url.ilike("%test%"),
                Article.source.has(Source.name.ilike("%test%")),
            )
        )
        .all()
    )
    print(f"Total test/fixture articles found in database: {len(test_articles)}")
    for ta in test_articles[:10]:
        pub_str = ta.published_at.astimezone(london_tz).strftime('%Y-%m-%d %H:%M:%S') if ta.published_at else 'N/A'
        col_str = ta.collected_at.astimezone(london_tz).strftime('%Y-%m-%d %H:%M:%S') if ta.collected_at else 'N/A'
        src_name = ta.source.name if ta.source else "N/A"
        t_title = ta.title.encode('ascii', 'ignore').decode('ascii')
        t_url = ta.canonical_url.encode('ascii', 'ignore').decode('ascii')
        print(f"  Test Article ID={ta.id} | Source={src_name} | Title={t_title[:40]} | Published={pub_str} | Collected={col_str} | URL={t_url[:40]}")

    # ---------------------------------------------------------
    # 10. FRESHNESS METRICS
    # ---------------------------------------------------------
    print("\n--- 10. FRESHNESS METRICS ---")
    ingestion_freshness_min = (now_utc - max_collected).total_seconds() / 60.0 if max_collected else None
    source_freshness_min = (now_utc - max_published).total_seconds() / 60.0 if max_published else None

    latest_proc_rel = (
        db.query(ArticleAIOutput)
        .filter(ArticleAIOutput.status == "success", ArticleAIOutput.is_relevant == True)
        .order_by(ArticleAIOutput.processed_at.desc())
        .first()
    )
    ai_freshness_min = None
    if latest_proc_rel and latest_proc_rel.processed_at:
        proc_dt = latest_proc_rel.processed_at
        if proc_dt.tzinfo is None:
            proc_dt = proc_dt.replace(tzinfo=timezone.utc)
        ai_freshness_min = (now_utc - proc_dt).total_seconds() / 60.0

    briefing_freshness_min = None
    if balanced_articles:
        top_art = balanced_articles[0]
        top_dt = top_art.published_at or top_art.collected_at
        if top_dt and top_dt.tzinfo is None:
            top_dt = top_dt.replace(tzinfo=timezone.utc)
        briefing_freshness_min = (now_utc - top_dt).total_seconds() / 60.0

    print(f"INGESTION FRESHNESS:  {ingestion_freshness_min:.1f} minutes" if ingestion_freshness_min else "N/A")
    print(f"SOURCE FRESHNESS:     {source_freshness_min:.1f} minutes" if source_freshness_min else "N/A")
    print(f"AI FRESHNESS:         {ai_freshness_min:.1f} minutes" if ai_freshness_min else "N/A")
    print(f"BRIEFING FRESHNESS:   {briefing_freshness_min:.1f} minutes" if briefing_freshness_min else "N/A")

    db.close()

if __name__ == "__main__":
    run_diagnostic()
