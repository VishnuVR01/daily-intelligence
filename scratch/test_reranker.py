import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["OLLAMA_ENABLED"] = "false"

import json
from app.db import SessionLocal
from app.config import get_settings
get_settings.cache_clear()

from app.models import Article
from repositories.articles import search_articles_v1
from scripts.validate_gold_fingerprints import validate_gold_fingerprints

dataset, _ = validate_gold_fingerprints('benchmarks/rag_v1_validated.json')
db = SessionLocal()

print("=" * 90)
print("TESTING QUERY-AWARE RERANKING TUNED FORMULA")
print("=" * 90)

total_eligible = 0
base_hits = 0
exp_b_hits = 0
exp_c_hits = 0

for item in dataset:
    q_id = item["id"]
    q_text = item["question"]
    core_ids = set(item.get("gold_core_article_ids", []))
    if not core_ids or not item.get("should_be_answerable", True):
        continue

    total_eligible += len(core_ids)

    # Variant A (Baseline)
    res_A = search_articles_v1(db, query=q_text, relevant_only=True, limit=10, candidate_limit=40, enable_query_expansion=False)
    ret_A = set(res_A.get("retrieved_article_ids", [a.id for a in res_A.get("articles", [])]))
    hits_A = core_ids.intersection(ret_A)
    base_hits += len(hits_A)

    # Variant B (Query Expansion)
    res_B = search_articles_v1(db, query=q_text, relevant_only=True, limit=10, candidate_limit=40, enable_query_expansion=True)
    ret_B = set(res_B.get("retrieved_article_ids", [a.id for a in res_B.get("articles", [])]))
    hits_B = core_ids.intersection(ret_B)
    exp_b_hits += len(hits_B)

    # Variant C (Query Expansion + Query-Aware Reranking)
    res_C = search_articles_v1(db, query=q_text, relevant_only=True, limit=10, candidate_limit=40, enable_query_expansion=True, enable_query_aware_reranking=True)
    ret_C = set(res_C.get("retrieved_article_ids", [a.id for a in res_C.get("articles", [])]))
    hits_C = core_ids.intersection(ret_C)
    exp_c_hits += len(hits_C)

    diff_C_B = hits_C - hits_B
    diff_B_C = hits_B - hits_C
    print(f"[{q_id}] A: {len(hits_A)}/{len(core_ids)} | B: {len(hits_B)}/{len(core_ids)} | C: {len(hits_C)}/{len(core_ids)}" +
          (f" -> RECOVERED: {list(diff_C_B)}" if diff_C_B else "") +
          (f" -> DROPPED: {list(diff_B_C)}" if diff_B_C else ""))

print("=" * 90)
print(f"TOTAL ELIGIBLE CORE GOLD: {total_eligible}")
print(f"VARIANT A CORE HITS:     {base_hits} / {total_eligible} ({base_hits/total_eligible*100:.1f}%)")
print(f"VARIANT B CORE HITS:     {exp_b_hits} / {total_eligible} ({exp_b_hits/total_eligible*100:.1f}%)")
print(f"VARIANT C CORE HITS:     {exp_c_hits} / {total_eligible} ({exp_c_hits/total_eligible*100:.1f}%)")
print("=" * 90)

db.close()
