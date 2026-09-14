"""
Benchmark script for Historical Intelligence Search v1 and Grounded RAG v1.
Executes 10 representative historical queries and measures performance, context budgeting, and citation accuracy.
"""

import time
import json
from typing import Any, Dict, List

from app.db import SessionLocal
from repositories.articles import search_articles_v1
from services.rag import ask_archive


BENCHMARK_QUERIES = [
    "semiconductor supply chains",
    "RBI inflation",
    "oil markets",
    "BRICS trade",
    "AI infrastructure",
    "NVIDIA data centres",
    "Ukraine negotiations",
    "commodity prices",
    "warehouse automation",
    "Federal Reserve interest rates",
]


def run_benchmark() -> Dict[str, Any]:
    db = SessionLocal()
    results: List[Dict[str, Any]] = []

    print("================================================================================")
    print("HISTORICAL SEARCH & RAG BENCHMARK EVALUATION (10 QUERIES)")
    print("================================================================================")

    total_search_time = 0.0
    total_rag_time = 0.0
    total_citations = 0
    total_valid_citations = 0

    try:
        for idx, query in enumerate(BENCHMARK_QUERIES, 1):
            print(f"\n[{idx}/10] Query: '{query}'")

            # 1. Search Benchmark
            t0 = time.perf_counter()
            search_res = search_articles_v1(db, query=query, limit=10, relevant_only=False)
            search_ms = (time.perf_counter() - t0) * 1000.0
            total_search_time += search_ms

            matched_count = search_res["total"]
            top_articles = search_res["articles"]
            print(f"  |- Search: {search_ms:.2f} ms | Found {matched_count} matches")

            # 2. RAG Benchmark
            t1 = time.perf_counter()
            rag_output = ask_archive(db=db, question=query, max_evidence_count=8)
            rag_ms = (time.perf_counter() - t1) * 1000.0
            total_rag_time += rag_ms

            executive_answer = rag_output.get("executive_answer", "")
            key_themes = rag_output.get("key_themes", [])
            citations = rag_output.get("citations", [])
            context_meta = rag_output.get("context_meta", {})
            raw_offline = rag_output.get("raw_offline", False)

            # 3. Citation Accuracy Verification
            num_citations = len(citations)
            valid_citations = 0
            for cite in citations:
                c_id = cite.get("article_id")
                c_url = cite.get("canonical_url")
                if c_id and c_url and c_url.startswith("http"):
                    valid_citations += 1

            total_citations += num_citations
            total_valid_citations += valid_citations

            query_eval = {
                "query": query,
                "search_ms": round(search_ms, 2),
                "matched_count": matched_count,
                "rag_ms": round(rag_ms, 2),
                "rag_offline": raw_offline,
                "context_article_count": context_meta.get("article_count", 0),
                "context_char_count": context_meta.get("total_chars", 0),
                "key_themes_count": len(key_themes),
                "citations_count": num_citations,
                "valid_citations_count": valid_citations,
                "citation_accuracy_pct": round((valid_citations / num_citations * 100.0), 1) if num_citations > 0 else 100.0,
            }
            results.append(query_eval)

            print(f"  |- RAG: {rag_ms:.2f} ms | Context: {context_meta.get('article_count', 0)} articles ({context_meta.get('total_chars', 0)} chars)")
            print(f"  |- Output: {len(key_themes)} themes | Citations: {valid_citations}/{num_citations} valid (Offline fallback: {raw_offline})")

        num_q = len(BENCHMARK_QUERIES)
        avg_search_ms = total_search_time / num_q
        avg_rag_ms = total_rag_time / num_q
        citation_accuracy = (total_valid_citations / total_citations * 100.0) if total_citations > 0 else 100.0

        summary = {
            "query_count": num_q,
            "avg_search_latency_ms": round(avg_search_ms, 2),
            "avg_rag_latency_ms": round(avg_rag_ms, 2),
            "total_citations": total_citations,
            "total_valid_citations": total_valid_citations,
            "overall_citation_accuracy_pct": round(citation_accuracy, 1),
            "queries": results,
        }

        print("\n================================================================================")
        print("SUMMARY BENCHMARK METRICS")
        print("================================================================================")
        print(f"Average Search Latency : {summary['avg_search_latency_ms']} ms")
        print(f"Average RAG Latency    : {summary['avg_rag_latency_ms']} ms")
        print(f"Total Citations        : {summary['total_citations']}")
        print(f"Valid Citations        : {summary['total_valid_citations']} ({summary['overall_citation_accuracy_pct']}%)")
        print("================================================================================")

        return summary

    finally:
        db.close()


if __name__ == "__main__":
    benchmark_res = run_benchmark()
    with open("scratch/benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(benchmark_res, f, indent=2)
