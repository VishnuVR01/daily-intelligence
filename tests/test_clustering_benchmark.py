"""
Unit test for Stage 4D.1 Event Coverage Expansion - Benchmark Safeguard 6.
Evaluates benchmarks/editorial_clustering_coverage_v1.json (>= 150 cases).
Enforces: false_merges == 0.
"""
import json
from pathlib import Path
import pytest

from app.models import Article
from services.editorial.clustering import compare_articles_similarity

def test_clustering_coverage_benchmark_v1():
    bench_path = Path("benchmarks/editorial_clustering_coverage_v1.json")
    assert bench_path.exists(), "Benchmark file benchmarks/editorial_clustering_coverage_v1.json must exist."

    with open(bench_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    pos_pairs = data.get("positive_same_event_pairs", [])
    neg_pairs = data.get("negative_different_event_pairs", [])
    singletons = data.get("singleton_events", [])

    total_cases = len(pos_pairs) + len(neg_pairs) + len(singletons)
    assert total_cases >= 150, f"Benchmark must contain at least 150 cases. Found {total_cases}."

    false_merges = 0
    false_merge_details = []

    for p in neg_pairs:
        a1 = Article(id=p["id1"], title=p["title1"])
        a2 = Article(id=p["id2"], title=p["title2"])
        comp = compare_articles_similarity(a1, a2)

        if comp.confidence_band == "HIGH_CONFIDENCE":
            false_merges += 1
            false_merge_details.append(
                f"FALSE MERGE: '{p['title1']}' <-> '{p['title2']}' (Score: {comp.similarity_score:.2f}, Reason: {p['reason']})"
            )

    print(f"\nEvaluated {total_cases} benchmark cases ({len(pos_pairs)} pos, {len(neg_pairs)} neg, {len(singletons)} singletons).")
    print(f"False Merges: {false_merges}")

    assert false_merges == 0, f"Mandatory Safeguard 6 Failure: false_merges must be 0! Details:\n" + "\n".join(false_merge_details)
