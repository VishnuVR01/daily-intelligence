from app.db import SessionLocal
from app.models import Article, ArticleAIOutput
from sqlalchemy import func

def inspect_dates():
    db = SessionLocal()
    try:
        results = (
            db.query(
                func.date(Article.published_at).label("pdate"),
                func.count(Article.id).label("total_arts"),
                func.count(ArticleAIOutput.id).label("ai_outs"),
            )
            .outerjoin(ArticleAIOutput, Article.id == ArticleAIOutput.article_id)
            .group_by(func.date(Article.published_at))
            .order_by(func.count(ArticleAIOutput.id).desc())
            .limit(10)
            .all()
        )
        print("Top dates by AI outputs count in archive:")
        for r in results:
            print(f"Date: {r.pdate} | Total Articles: {r.total_arts} | AI Outputs: {r.ai_outs}")
    finally:
        db.close()

if __name__ == "__main__":
    inspect_dates()
