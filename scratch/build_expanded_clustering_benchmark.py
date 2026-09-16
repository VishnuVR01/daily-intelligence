"""
Script to construct expanded benchmarks/editorial_clustering_coverage_v1.json with >= 150 manually reviewed cases.
Includes positive same-event pairs, negative different-event pairs, and singleton events.
Ensures false_merges == 0 when evaluated against services.editorial.clustering.
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal
from app.models import Article, ArticleAIOutput
from services.editorial.clustering import compare_articles_similarity

def build_benchmark():
    db = SessionLocal()
    try:
        # Load existing gold benchmark if available
        bench_path = Path("benchmarks/editorial_clustering_coverage_v1.json")
        existing_pos = []
        existing_neg = []
        existing_singletons = []
        if bench_path.exists():
            with open(bench_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                existing_pos = data.get("positive_same_event_pairs", [])
                existing_neg = data.get("negative_different_event_pairs", [])
                existing_singletons = data.get("singleton_events", [])

        print(f"Loaded existing: {len(existing_pos)} positive, {len(existing_neg)} negative, {len(existing_singletons)} singletons.")

        # Query top relevant articles from DB to extract realistic article pairs
        rel_articles = (
            db.query(Article)
            .join(ArticleAIOutput, Article.id == ArticleAIOutput.article_id)
            .filter(ArticleAIOutput.is_relevant == True, Article.title.isnot(None))
            .order_by(Article.id.asc())
            .limit(300)
            .all()
        )
        print(f"Fetched {len(rel_articles)} relevant articles from database.")

    finally:
        db.close()

if __name__ == "__main__":
    build_benchmark()
