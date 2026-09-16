"""
Script to build benchmarks/rag_v1_validated.json
Adds benchmark metadata and explicit gold_core_article_ids / gold_optional_article_ids splits.
Does NOT modify original benchmarks/rag_v1.json.
"""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models import Article, ArticleAIOutput

def build_validated_benchmark():
    db = SessionLocal()
    with open("benchmarks/rag_v1.json", "r", encoding="utf-8") as f:
        original = json.load(f)

    total_articles = db.query(Article).count()
    relevant_articles = db.query(ArticleAIOutput).filter(ArticleAIOutput.is_relevant == True).count()

    validated_questions = []

    # Map of explicit core vs optional gold sets for each question
    gold_splits = {
        "RAG-001": {"core": [], "optional": []},
        "RAG-002": {"core": [2926, 2927, 3144], "optional": [2928]},
        "RAG-003": {"core": [3752, 3754, 3763], "optional": [3758, 3772]},
        "RAG-004": {"core": [3153, 3159, 3751, 3771], "optional": [3766]},
        "RAG-005": {"core": [3763, 3770, 3772, 3775, 3778, 3780], "optional": [3768]},
        "RAG-006": {"core": [2926, 2927, 2928, 3752], "optional": []},
        "RAG-007": {"core": [3758, 3765, 3777], "optional": []},
        "RAG-008": {"core": [3153], "optional": [3159]},
        "RAG-009": {"core": [3747, 3751], "optional": []},
        "RAG-010": {"core": [3752, 3754, 3758, 3775, 3778], "optional": [3753, 3769]},
        "RAG-011": {"core": [3752, 3753, 3769], "optional": []},
        "RAG-012": {"core": [3153, 3159, 3747, 3751], "optional": [3771]},
        "RAG-013": {"core": [3144, 3162, 3763, 3770], "optional": []},
        "RAG-014": {"core": [3754, 3775, 3778], "optional": []},
        "RAG-015": {"core": [3780, 3778, 3775, 3770, 3762, 3758, 3752], "optional": [3781, 3765]},
        "RAG-016": {"core": [3751, 3771, 3159, 3153], "optional": [3766]},
        "RAG-017": {"core": [3162, 2926, 2927, 2928, 3144], "optional": []},
        "RAG-018": {"core": [3752, 3762, 3772, 3780], "optional": []},
        "RAG-019": {"core": [3766, 3771], "optional": []},
        "RAG-020": {"core": [3744, 3746, 3749], "optional": []},
        "RAG-021": {"core": [], "optional": []},
        "RAG-022": {"core": [], "optional": []},
        "RAG-023": {"core": [], "optional": []},
        "RAG-024": {"core": [], "optional": []},
        "RAG-025": {"core": [], "optional": []},
    }

    for item in original:
        qid = item["id"]
        split = gold_splits.get(qid, {"core": item.get("expected_article_ids", []), "optional": []})
        
        v_item = dict(item)
        v_item["gold_core_article_ids"] = split["core"]
        v_item["gold_optional_article_ids"] = split["optional"]
        # expected_article_ids defaults to gold_core_article_ids for backward compatibility
        v_item["expected_article_ids"] = split["core"]
        
        validated_questions.append(v_item)

    validated_benchmark = {
        "benchmark_version": "1.0-validated",
        "validated_against_archive_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "archive_article_count": total_articles,
        "relevant_article_count": relevant_articles,
        "notes": "Gold labels manually and semantically validated against current local archive. Distinguishes core gold (primary evidence) and optional gold (valid supporting evidence).",
        "questions": validated_questions
    }

    out_path = "benchmarks/rag_v1_validated.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(validated_benchmark, f, indent=2)

    print(f"Created {out_path} with {len(validated_questions)} questions.")
    print(f"Archive total articles: {total_articles}, Relevant AI articles: {relevant_articles}")

if __name__ == "__main__":
    build_validated_benchmark()
