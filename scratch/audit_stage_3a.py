import sys
import os
sys.path.insert(0, os.path.abspath("."))
import json
import statistics
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import func, inspect
from app.db import SessionLocal
from app.models import Article, ArticleAIOutput, Source, DailyEdition, EditionArticle, Base

def run_stage_3a_audit():
    db = SessionLocal()
    try:
        # 1. Inspect Tables in Schema
        engine = db.get_bind()
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        
        has_daily_editions = "daily_editions" in table_names
        has_edition_articles = "edition_articles" in table_names

        daily_editions_cols = [c["name"] for c in inspector.get_columns("daily_editions")] if has_daily_editions else []
        edition_articles_cols = [c["name"] for c in inspector.get_columns("edition_articles")] if has_edition_articles else []

        print("--- SCHEMA INSPECTION ---")
        print(f"daily_editions table exists: {has_daily_editions} | Columns: {daily_editions_cols}")
        print(f"edition_articles table exists: {has_edition_articles} | Columns: {edition_articles_cols}")

        # 2. Importance Score Distribution Analysis
        ai_outputs = db.query(ArticleAIOutput).filter(ArticleAIOutput.status == "success").all()
        importance_scores = []
        for out in ai_outputs:
            if isinstance(out.output_json, dict) and "importance_score" in out.output_json:
                try:
                    val = float(out.output_json["importance_score"])
                    importance_scores.append(val)
                except (ValueError, TypeError):
                    pass

        if importance_scores:
            sorted_scores = sorted(importance_scores)
            n = len(sorted_scores)
            mean_score = statistics.mean(sorted_scores)
            median_score = statistics.median(sorted_scores)
            p25 = sorted_scores[int(n * 0.25)]
            p75 = sorted_scores[int(n * 0.75)]
            p90 = sorted_scores[int(n * 0.90)]

            bands = {
                "90-100 (Critical/Lead)": sum(1 for s in sorted_scores if 90 <= s <= 100),
                "75-89 (High Importance)": sum(1 for s in sorted_scores if 75 <= s < 90),
                "50-74 (Moderate Importance)": sum(1 for s in sorted_scores if 50 <= s < 75),
                "25-49 (Low Importance)": sum(1 for s in sorted_scores if 25 <= s < 50),
                "0-24 (Minor)": sum(1 for s in sorted_scores if 0 <= s < 25),
            }
        else:
            mean_score = median_score = p25 = p75 = p90 = 0.0
            bands = {}

        print("\n--- IMPORTANCE SCORE DISTRIBUTION ---")
        print(f"Total AI Outputs Analyzed: {len(importance_scores)}")
        print(f"Mean: {mean_score:.2f} | Median: {median_score:.2f} | P25: {p25:.2f} | P75: {p75:.2f} | P90: {p90:.2f}")
        print("Bands Breakdown:", json.dumps(bands, indent=2))

        # 3. Analyze Recent Complete Day (Sep 14, 2026 in Europe/London)
        london_tz = ZoneInfo("Europe/London")
        target_date = datetime(2026, 9, 14, tzinfo=london_tz)
        day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        day_end = (day_start + timedelta(days=1))

        articles_day = db.query(Article).filter(
            Article.published_at >= day_start,
            Article.published_at < day_end
        ).all()

        category_dist = {}
        source_dist = {}
        ai_reviewed_count = 0
        relevant_count = 0

        for a in articles_day:
            src_name = a.source.name if a.source else "Unknown"
            source_dist[src_name] = source_dist.get(src_name, 0) + 1

            cat = a.primary_category or (a.source.category if a.source else "General")
            category_dist[cat] = category_dist.get(cat, 0) + 1

            outs = a.ai_outputs or []
            if outs:
                ai_reviewed_count += 1
                latest_out = sorted(outs, key=lambda x: x.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[0]
                if latest_out.is_relevant:
                    relevant_count += 1

        print("\n--- DAY ANALYSIS (2026-09-14 London Time) ---")
        print(f"Raw Articles Published: {len(articles_day)}")
        print(f"AI Reviewed Count: {ai_reviewed_count}")
        print(f"Relevant Count: {relevant_count}")
        print("Category Distribution:", json.dumps(category_dist, indent=2))
        print("Top Sources Distribution:", json.dumps(sorted(source_dist.items(), key=lambda x: x[1], reverse=True)[:10], indent=2))

        # 4. Read-Only Simulation of Editorial Eligibility & Scoring
        # Editorial Score formula (0-100):
        # 1. Importance (40 pts max): (importance_score / 100) * 40
        # 2. Source Trust Tier (20 pts max): Tier 1 (Official/Primary) = 20, Tier 2 (Institutional) = 16, Tier 3 (News) = 12, Other = 8
        # 3. Recency (20 pts max): Bounded bonus based on publication proximity to day_end
        # 4. Strategic Alignment (20 pts max): Primary category in core macro/tech categories (AI, Economy, Energy, Markets, Tech) = 20, others = 10
        candidates = []
        for a in articles_day:
            outs = a.ai_outputs or []
            if not outs:
                continue
            latest_out = sorted(outs, key=lambda x: x.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[0]
            if not latest_out.is_relevant:
                continue

            imp = 70.0
            if isinstance(latest_out.output_json, dict) and "importance_score" in latest_out.output_json:
                try:
                    imp = float(latest_out.output_json["importance_score"])
                except Exception:
                    pass

            imp_pts = (imp / 100.0) * 40.0

            src_type = a.source.source_type if a.source else "rss"
            trust = a.source.trust_tier if a.source else "useful"
            if src_type in ("CENTRAL_BANK", "GOVERNMENT", "COMPANY_PRIMARY"):
                src_pts = 20.0
            elif trust == "core" or src_type == "INSTITUTIONAL_RESEARCH":
                src_pts = 16.0
            elif trust == "useful":
                src_pts = 12.0
            else:
                src_pts = 8.0

            # Recency pts (max 20)
            if a.published_at:
                hours_old = (day_end - a.published_at).total_seconds() / 3600.0
                rec_pts = max(0.0, 20.0 - (hours_old * 0.5))
            else:
                rec_pts = 10.0

            cat = a.primary_category or (a.source.category if a.source else "General")
            if cat in ("AI", "Economy", "Markets", "Energy", "Tech", "Macro", "Business"):
                strat_pts = 20.0
            else:
                strat_pts = 12.0

            score = round(imp_pts + src_pts + rec_pts + strat_pts, 1)

            candidates.append({
                "article_id": a.id,
                "title": a.title,
                "source": a.source.name if a.source else "Unknown",
                "category": cat,
                "importance": imp,
                "published_at": a.published_at.isoformat() if a.published_at else None,
                "editorial_score": score,
                "breakdown": {
                    "importance_pts": round(imp_pts, 1),
                    "source_pts": round(src_pts, 1),
                    "recency_pts": round(rec_pts, 1),
                    "strategic_pts": round(strat_pts, 1),
                },
                "explanation": f"Importance ({imp_pts:.1f}/40) + Source ({src_pts:.1f}/20) + Recency ({rec_pts:.1f}/20) + Strategic ({strat_pts:.1f}/20)"
            })

        candidates.sort(key=lambda c: c["editorial_score"], reverse=True)
        top_30 = candidates[:30]

        print("\n--- SIMULATED EDITORIAL RANKING (TOP 30 CANDIDATES FOR 2026-09-14) ---")
        for idx, c in enumerate(top_30, 1):
            print(f"{idx:2d}. [Score: {c['editorial_score']:4.1f}] (Imp: {c['importance']:2.0f}) [{c['category']}] {c['title'][:65]}... | {c['source']}")

        return {
            "has_daily_editions": has_daily_editions,
            "has_edition_articles": has_edition_articles,
            "daily_editions_cols": daily_editions_cols,
            "edition_articles_cols": edition_articles_cols,
            "importance_stats": {
                "mean": round(mean_score, 2),
                "median": round(median_score, 2),
                "p25": round(p25, 2),
                "p75": round(p75, 2),
                "p90": round(p90, 2),
                "bands": bands
            },
            "day_analysis": {
                "articles_published": len(articles_day),
                "ai_reviewed": ai_reviewed_count,
                "relevant": relevant_count,
                "category_dist": category_dist,
                "source_dist": source_dist
            },
            "simulated_top_30": top_30
        }

    finally:
        db.close()

if __name__ == "__main__":
    run_stage_3a_audit()
