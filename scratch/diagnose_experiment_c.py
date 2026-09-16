import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["OLLAMA_ENABLED"] = "false"

import json
from datetime import datetime, timezone
from app.db import SessionLocal
from app.config import get_settings
get_settings.cache_clear()

from app.models import Article
from repositories.articles import search_articles_v1, get_article_ai_output
from scripts.validate_gold_fingerprints import validate_gold_fingerprints

dataset, _ = validate_gold_fingerprints('benchmarks/rag_v1_validated.json')
db = SessionLocal()

print("=" * 90)
print("EXPERIMENT C — RANKING DIAGNOSTIC FOR CANDIDATES IN POSITIONS 11-40")
print("=" * 90)

missed_candidates = []

for item in dataset:
    q_id = item["id"]
    q_text = item["question"]
    core_ids = item.get("gold_core_article_ids", [])
    if not core_ids or not item.get("should_be_answerable", True):
        continue

    # Run search with query expansion enabled
    search_res = search_articles_v1(
        db,
        query=q_text,
        relevant_only=True,
        limit=10,
        candidate_limit=40,
        enable_query_expansion=True,
    )

    final_top10_ids = [a.id for a in search_res.get("articles", [])]
    scores = search_res.get("scores", {})

    # Fetch raw 40 candidates
    raw_res = search_articles_v1(
        db,
        query=q_text,
        relevant_only=True,
        limit=40,
        candidate_limit=40,
        enable_query_expansion=True,
    )
    raw_cand_articles = raw_res.get("articles", [])
    raw_cand_ids = [a.id for a in raw_cand_articles]

    for art_id in core_ids:
        if art_id in raw_cand_ids and art_id not in final_top10_ids:
            cand_rank = raw_cand_ids.index(art_id) + 1
            art = next(a for a in raw_cand_articles if a.id == art_id)
            ai_out = get_article_ai_output(art)
            score = scores.get(art_id, 0.0)

            missed_candidates.append({
                "question_id": q_id,
                "article_id": art_id,
                "title": art.title,
                "candidate_rank": cand_rank,
                "current_hybrid_score": score,
                "ai_relevance": ai_out.relevance_score if ai_out else None,
                "ai_importance": ai_out.importance_score if ai_out else None,
                "primary_category": art.primary_category or (ai_out.primary_category if ai_out else None),
                "source": art.source.name if art.source else None,
                "trust_tier": art.source.trust_tier if art.source else None,
            })

            print(f"[{q_id}] Missed Core Article {art_id} ('{art.title[:40]}...') | Cand Rank #{cand_rank} | Current Score: {score}")

print("=" * 90)
print(f"TOTAL MISSED CORE ARTICLES PRESENT IN CANDIDATES (11-40): {len(missed_candidates)}")
print("=" * 90)

db.close()
