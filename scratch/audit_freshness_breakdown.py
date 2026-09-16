import sys
import os
sys.path.insert(0, os.path.abspath("."))
from datetime import datetime, timezone
import json
from sqlalchemy import func
from app.db import SessionLocal
from app.models import Article, Source, ArticleAIOutput

def run_freshness_audit():
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        # 1. Ingestion freshness
        latest_col = db.query(Article).order_by(Article.collected_at.desc()).first()
        ingestion_freshness = (now - latest_col.collected_at).total_seconds() / 60.0 if latest_col else None

        # 2. Source freshness
        latest_pub = db.query(Article).filter(Article.published_at <= now).order_by(Article.published_at.desc()).first()
        source_freshness = (now - latest_pub.published_at).total_seconds() / 60.0 if latest_pub else None

        # 3. AI freshness
        latest_ai = db.query(ArticleAIOutput).filter(ArticleAIOutput.status == "success").order_by(ArticleAIOutput.processed_at.desc()).first()
        ai_freshness = (now - latest_ai.processed_at).total_seconds() / 60.0 if latest_ai else None

        # 4. Relevant intelligence freshness
        latest_rel = db.query(ArticleAIOutput).filter(ArticleAIOutput.status == "success", ArticleAIOutput.is_relevant == True).order_by(ArticleAIOutput.processed_at.desc()).first()
        relevant_freshness = (now - latest_rel.processed_at).total_seconds() / 60.0 if latest_rel else None

        # 5. Briefing freshness (/latest newest result)
        # /latest queries relevant AI outputs ordered by published_at desc
        latest_brief = (
            db.query(Article)
            .join(ArticleAIOutput)
            .filter(ArticleAIOutput.is_relevant == True, Article.published_at <= now)
            .order_by(Article.published_at.desc())
            .first()
        )
        briefing_freshness = (now - latest_brief.published_at).total_seconds() / 60.0 if latest_brief else None

        # Trace 5 newest database articles
        top5_articles = db.query(Article).order_by(Article.collected_at.desc()).limit(5).all()
        traced = []
        for a in top5_articles:
            ai_out = db.query(ArticleAIOutput).filter(ArticleAIOutput.article_id == a.id).first()
            is_in_latest = (ai_out is not None and ai_out.is_relevant is True)
            traced.append({
                "article_id": a.id,
                "title": a.title[:70],
                "source": a.source.name if a.source else "Unknown",
                "collected_at": a.collected_at.isoformat() if a.collected_at else None,
                "published_at": a.published_at.isoformat() if a.published_at else None,
                "ai_state": ai_out.status if ai_out else "UNPROCESSED",
                "is_relevant": ai_out.is_relevant if ai_out else None,
                "latest_eligible": is_in_latest
            })

        res = {
            "ingestion_freshness_minutes": round(ingestion_freshness, 1) if ingestion_freshness else None,
            "source_freshness_minutes": round(source_freshness, 1) if source_freshness else None,
            "ai_freshness_minutes": round(ai_freshness, 1) if ai_freshness else None,
            "relevant_intelligence_freshness_minutes": round(relevant_freshness, 1) if relevant_freshness else None,
            "briefing_freshness_minutes": round(briefing_freshness, 1) if briefing_freshness else None,
            "traced_top_5_articles": traced
        }

        print(json.dumps(res, indent=2))
        return res
    finally:
        db.close()

if __name__ == "__main__":
    run_freshness_audit()
