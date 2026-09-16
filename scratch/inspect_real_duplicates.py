import sys
import os
sys.path.insert(0, os.path.abspath("."))
import json
from datetime import datetime, timezone
from sqlalchemy import func, or_
from app.db import SessionLocal
from app.models import Article, ArticleAIOutput, Source

def inspect_real_data():
    db = SessionLocal()
    try:
        articles = (
            db.query(Article)
            .join(ArticleAIOutput)
            .filter(ArticleAIOutput.is_relevant == True)
            .order_by(Article.published_at.desc().nullslast())
            .all()
        )

        print(f"Total relevant articles for inspection: {len(articles)}")

        # Search for known duplicate events in title/summary
        pairs = []
        seen = set()

        for i in range(len(articles)):
            for j in range(i + 1, min(i + 40, len(articles))):
                a1 = articles[i]
                a2 = articles[j]

                # Check publication gap
                if a1.published_at and a2.published_at:
                    gap_hours = abs((a1.published_at - a2.published_at).total_seconds()) / 3600.0
                    if gap_hours > 48:
                        continue

                t1 = a1.title.lower()
                t2 = a2.title.lower()

                # Common token overlap
                w1 = set(t1.split())
                w2 = set(t2.split())
                common = w1.intersection(w2)
                
                # Check for same event markers
                if len(common) >= 3 or ("fed" in t1 and "fed" in t2) or ("ecb" in t1 and "ecb" in t2) or ("oil" in t1 and "oil" in t2) or ("china" in t1 and "china" in t2):
                    pairs.append({
                        "id1": a1.id,
                        "title1": a1.title,
                        "source1": a1.source.name if a1.source else "",
                        "pub1": a1.published_at.isoformat() if a1.published_at else "",
                        "id2": a2.id,
                        "title2": a2.title,
                        "source2": a2.source.name if a2.source else "",
                        "pub2": a2.published_at.isoformat() if a2.published_at else "",
                        "common_words": list(common)
                    })

        print(f"Found {len(pairs)} candidate similarity pairs for manual inspection.")
        for p in pairs[:15]:
            print(f"Pair [{p['id1']} - {p['id2']}]:\n  1. ({p['source1']}) {p['title1']}\n  2. ({p['source2']}) {p['title2']}\n  Common: {p['common_words']}\n")

        return pairs

    finally:
        db.close()

if __name__ == "__main__":
    inspect_real_data()
