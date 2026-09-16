import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["OLLAMA_ENABLED"] = "false"
from app.config import get_settings
get_settings.cache_clear()
import json
from app.db import SessionLocal
from services.rag import ask_archive
from scripts.validate_gold_fingerprints import validate_gold_fingerprints

dataset, _ = validate_gold_fingerprints('benchmarks/rag_v1_validated.json')
db = SessionLocal()

print("=" * 80)
print("BASELINE CORE GOLD RETRIEVAL INSPECTION")
print("=" * 80)

total_core = 0
total_hits = 0

for q in dataset:
    core_ids = set(q.get('gold_core_article_ids', []))
    if not core_ids:
        print(f"{q['id']} ({q['category']}): NEGATIVE TEST (No core gold)")
        continue
    
    res = ask_archive(db, q['question'])
    retrieved_ids = set(res.get('retrieved_article_ids', []))
    hits = core_ids.intersection(retrieved_ids)
    misses = core_ids - retrieved_ids
    
    total_core += len(core_ids)
    total_hits += len(hits)
    
    status = "FULL HIT" if not misses else ("PARTIAL HIT" if hits else "ZERO HIT")
    print(f"{q['id']} [{status}] ({q['category']}): {len(hits)}/{len(core_ids)} hits. Ret: {list(retrieved_ids)} | Core: {list(core_ids)} | Missed: {list(misses)}")

hit_rate = round(total_hits / total_core, 4) if total_core > 0 else 0.0
print("=" * 80)
print(f"TOTAL CORE GOLD ARTICLES: {total_core}")
print(f"TOTAL CORE GOLD HITS:     {total_hits}")
print(f"CORE RETRIEVAL HIT RATE:  {hit_rate * 100:.1f}%")
print("=" * 80)

db.close()
