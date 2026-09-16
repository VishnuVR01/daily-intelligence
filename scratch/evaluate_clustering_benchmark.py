import sys
import os
sys.path.insert(0, os.path.abspath("."))
import json
from datetime import datetime, timezone
from app.db import SessionLocal
from app.models import Article, ArticleAIOutput
from services.editorial.clustering import (
    compare_articles_similarity,
    cluster_articles,
    EventClusterResult
)

def run_benchmark_eval():
    print("=" * 80)
    print("1. CLUSTERING BENCHMARK EVALUATION (benchmarks/editorial_clustering_coverage_v1.json)")
    print("=" * 80)

    bench_path = "benchmarks/editorial_clustering_coverage_v1.json"
    with open(bench_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    pos_pairs = data.get("positive_same_event_pairs", [])
    neg_pairs = data.get("negative_different_event_pairs", [])
    singletons = data.get("singleton_events", [])

    true_positives = 0
    false_negatives = 0  # False Splits
    false_positives = 0  # False Merges
    true_negatives = 0

    print(f"\n--- EVALUATING {len(pos_pairs)} POSITIVE PAIRS (Expected: SAME_EVENT) ---")
    for p in pos_pairs:
        a1 = Article(id=p["id1"], title=p["title1"])
        a2 = Article(id=p["id2"], title=p["title2"])
        comp = compare_articles_similarity(a1, a2)

        is_clustered = (comp.confidence_band == "HIGH_CONFIDENCE")
        if is_clustered:
            true_positives += 1
        else:
            false_negatives += 1
            print(f"  [FALSE SPLIT] Score: {comp.similarity_score:.2f} ({comp.confidence_band}) | '{p['title1'][:50]}' <-> '{p['title2'][:50]}'")

    print(f"\n--- EVALUATING {len(neg_pairs)} NEGATIVE PAIRS (Expected: DIFFERENT_EVENT) ---")
    for p in neg_pairs:
        a1 = Article(id=p["id1"], title=p["title1"])
        a2 = Article(id=p["id2"], title=p["title2"])
        comp = compare_articles_similarity(a1, a2)

        is_clustered = (comp.confidence_band == "HIGH_CONFIDENCE")
        if not is_clustered:
            true_negatives += 1
        else:
            false_positives += 1
            print(f"  [FALSE MERGE] Score: {comp.similarity_score:.2f} ({comp.confidence_band}) | '{p['title1'][:50]}' <-> '{p['title2'][:50]}'")

    precision = true_positives / float(true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / float(true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    print("\n" + "=" * 80)
    print("BENCHMARK METRICS SUMMARY:")
    print(f"  Pairwise Precision: {precision * 100:.1f}%")
    print(f"  Pairwise Recall:    {recall * 100:.1f}%")
    print(f"  Pairwise F1:        {f1 * 100:.1f}%")
    print(f"  False Merges:       {false_positives} (Target: 0)")
    print(f"  False Splits:       {false_negatives}")
    print("=" * 80)

    # 2. Real-Day Simulation
    print("\n" + "=" * 80)
    print("2. REAL-DAY SIMULATION & COMPRESSION ANALYSIS (PostgreSQL Database)")
    print("=" * 80)

    db = SessionLocal()
    try:
        articles = (
            db.query(Article)
            .join(ArticleAIOutput)
            .filter(ArticleAIOutput.is_relevant == True)
            .order_by(Article.published_at.desc().nullslast())
            .limit(100)
            .all()
        )

        ai_map = {}
        for a in articles:
            outs = a.ai_outputs or []
            if outs:
                ai_map[a.id] = sorted(outs, key=lambda x: x.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[0]

        clusters = cluster_articles(articles, ai_outputs_map=ai_map)

        art_count_before = len(articles)
        event_count_after = len(clusters)
        compression_ratio = round((1.0 - (event_count_after / float(art_count_before))) * 100.0, 1)

        singletons = sum(1 for c in clusters if c.article_count == 1)
        multis = sum(1 for c in clusters if c.article_count > 1)
        max_cluster_size = max(c.article_count for c in clusters) if clusters else 0

        print(f"Articles Before Clustering: {art_count_before}")
        print(f"Events After Clustering:   {event_count_after}")
        print(f"Compression Ratio:         {compression_ratio}%")
        print(f"Singleton Events:          {singletons}")
        print(f"Multi-Article Clusters:    {multis}")
        print(f"Largest Cluster Size:      {max_cluster_size}")

        print("\n--- TOP 20 EVENT CLUSTERS ---")
        for idx, cl in enumerate(clusters[:20], 1):
            src_str = f"{cl.distinct_source_count} distinct source(s)"
            clean_t = cl.canonical_title.encode("ascii", errors="ignore").decode("ascii")
            clean_s = (cl.primary_article.source.name if cl.primary_article.source else 'Unknown').encode("ascii", errors="ignore").decode("ascii")
            print(f"{idx:2d}. [Score: {cl.cluster_score:5.1f}] ({cl.article_count} art, {src_str}) [{cl.category}]")
            print(f"    Primary Title: {clean_t[:75]}")
            print(f"    Primary Src:   {clean_s}")
            if cl.supporting_articles:
                supp_titles = [a.title.encode("ascii", errors="ignore").decode("ascii")[:45] for a in cl.supporting_articles]
                print(f"    Supporting:    {supp_titles}")
            print()

        eval_summary = {
            "precision": round(precision * 100, 1),
            "recall": round(recall * 100, 1),
            "f1": round(f1 * 100, 1),
            "false_merges": false_positives,
            "false_splits": false_negatives,
            "articles_before": art_count_before,
            "events_after": event_count_after,
            "compression_ratio_pct": compression_ratio,
            "singleton_events": singletons,
            "multi_article_clusters": multis,
            "max_cluster_size": max_cluster_size,
        }

        return eval_summary

    finally:
        db.close()

if __name__ == "__main__":
    run_benchmark_eval()
