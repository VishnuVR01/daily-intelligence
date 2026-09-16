import sys
import os
sys.path.insert(0, os.path.abspath("."))
import json
from sqlalchemy import func
from app.db import SessionLocal
from app.models import Article, ArticleAIOutput

def find_rich_day():
    db = SessionLocal()
    try:
        results = (
            db.query(func.date(Article.published_at), func.count(Article.id))
            .join(ArticleAIOutput)
            .filter(ArticleAIOutput.is_relevant == True)
            .group_by(func.date(Article.published_at))
            .order_by(func.count(Article.id).desc())
            .all()
        )
        print("Top AI-reviewed dates:")
        for r in results[:10]:
            print(f"Date: {r[0]} | Relevant Articles: {r[1]}")
    finally:
        db.close()

if __name__ == "__main__":
    find_rich_day()
