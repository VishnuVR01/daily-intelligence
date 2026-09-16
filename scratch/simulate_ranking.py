import sys
import os
sys.path.insert(0, os.path.abspath("."))
import json
import statistics
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import func
from app.db import SessionLocal
from app.models import Article, ArticleAIOutput, Source

def run_full_simulation():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        articles = (
            db.query(Article)
            .join(ArticleAIOutput)
            .filter(ArticleAIOutput.is_relevant == True)
            .all()
        )

        candidates = []
        for a in articles:
            outs = a.ai_outputs or []
            if not outs:
                continue
            latest_out = sorted(outs, key=lambda x: x.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[0]

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

            # Bounded Recency pts (max 20)
            if a.published_at:
                days_old = (now - a.published_at).total_seconds() / 86400.0
                rec_pts = max(0.0, 20.0 - (days_old * 2.0))
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

        print(f"\n--- FULL DATABASE SIMULATED EDITORIAL RANKING (TOP 30 OF {len(candidates)} RELEVANT ARTICLES) ---")
        for idx, c in enumerate(top_30, 1):
            clean_title = c['title'].encode("ascii", errors="ignore").decode("ascii")
            clean_source = c['source'].encode("ascii", errors="ignore").decode("ascii")
            print(f"{idx:2d}. [Score: {c['editorial_score']:4.1f}] (Imp: {c['importance']:2.0f}) [{c['category']}] {clean_title[:65]}... | {clean_source}")

        return top_30

    finally:
        db.close()

if __name__ == "__main__":
    run_full_simulation()
