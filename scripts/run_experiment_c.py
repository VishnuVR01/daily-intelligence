import os
import sys
from pathlib import Path

# Add current working directory to sys.path
sys.path.insert(0, os.getcwd())

import json
import time
from typing import Dict, Any, List

from app.db import SessionLocal
from services.rag import ask_archive, parse_date_semantics
from scripts.evaluate_rag import run_evaluation

BENCHMARK_PATH = "benchmarks/rag_v1_validated.json"

def run_experiment_c():
    if not os.path.exists(BENCHMARK_PATH):
        print(f"Error: Benchmark file {BENCHMARK_PATH} not found.")
        sys.exit(1)
        
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        benchmark_data = json.load(f)
        benchmark = benchmark_data.get("questions", benchmark_data)

    db = SessionLocal()
    
    print("=" * 70)
    print("RUNNING RAG v1.1 EXPERIMENT C EVALUATION")
    print("=" * 70)
    
    variants = [
        {"name": "v1_validated_baseline", "exp": False, "rerank": False, "label": "Official Baseline"},
        {"name": "exp_b_corrected", "exp": True, "rerank": False, "label": "Exp B Corrected"},
        {"name": "exp_c_reranked", "exp": True, "rerank": True, "label": "Exp C Reranked"}
    ]
    
    results_by_variant = {}
    
    try:
        for var in variants:
            print(f"\nEvaluating Variant: {var['label']} ({var['name']})...")
            start_time = time.time()
            
            # Evaluate using standard run_evaluation harness
            temp_json = f"scratch/eval_{var['name']}.json"
            temp_md = f"scratch/eval_{var['name']}.md"
            results = run_evaluation(
                benchmark_path=BENCHMARK_PATH,
                json_report_path=temp_json,
                md_report_path=temp_md,
                enable_query_expansion=var["exp"],
                enable_query_aware_reranking=var["rerank"],
                skip_llm=True,
            )
            
            elapsed = time.time() - start_time
            results["total_elapsed_seconds"] = round(elapsed, 2)
            results_by_variant[var["name"]] = results
            
            agg = results["aggregate_metrics"]
            print(f"  Core Hit Rate: {agg['core_retrieval_hit_rate']*100.0:.1f}%")
            print(f"  Optional Coverage: {agg['optional_gold_coverage']*100.0:.1f}%")
            print(f"  Temporal Accuracy: {agg['temporal_accuracy_pct']:.1f}%")
            print(f"  Citation Validity: {agg['citation_validity_pct']:.1f}%")
            print(f"  Unsupported Citation Rate: {agg['unsupported_citation_rate_pct']:.1f}%")
            print(f"  Refusal Accuracy: {agg['negative_test_refusal_accuracy_pct']:.1f}%")
            print(f"  Source Diversity: {agg['average_source_diversity']*100.0:.1f}%")
            print(f"  Avg Evidence Count: {agg['average_evidence_count']:.1f}")

        # Now let's trace missed gold for C4 classification
        print("\nTracing Missed Gold Associations across A, B, C...")
        missed_trace = trace_missed_gold(db, benchmark)
        
        # Save JSON output
        output_data = {
            "experiment": "RAG v1.1 Experiment C — Query-Aware Reranking",
            "variants": results_by_variant,
            "missed_gold_trace": missed_trace
        }
        
        output_file = Path("reports/rag_v1_1_experiment_c.json")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)
        print(f"\nReport written to {output_file}")
        
    finally:
        db.close()

def trace_missed_gold(db, benchmark: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # We want to check all 70 core gold associations across questions
    from repositories.articles import search_articles_v1
    from services.query_expansion import expand_query
    
    traces = []
    
    for q in benchmark:
        q_id = q["id"]
        q_text = q["question"]
        gold_ids = set(q.get("gold_core_article_ids", []))
        if not gold_ids:
            continue
        date_from, date_to = parse_date_semantics(q_text)
        
        # Candidate pool = 40, final = 10
        # Variant A
        res_a = search_articles_v1(db, query=q_text, limit=10, candidate_limit=40, enable_query_expansion=False, enable_query_aware_reranking=False, date_from=date_from, date_to=date_to)
        a_final_ids = [a.id for a in res_a["articles"]]
        a_cand_ids = res_a.get("candidate_article_ids", [])
        
        # Variant B
        res_b = search_articles_v1(db, query=q_text, limit=10, candidate_limit=40, enable_query_expansion=True, enable_query_aware_reranking=False, date_from=date_from, date_to=date_to)
        b_final_ids = [a.id for a in res_b["articles"]]
        b_cand_ids = res_b.get("candidate_article_ids", [])
        
        # Variant C
        res_c = search_articles_v1(db, query=q_text, limit=10, candidate_limit=40, enable_query_expansion=True, enable_query_aware_reranking=True, date_from=date_from, date_to=date_to)
        c_final_ids = [a.id for a in res_c["articles"]]
        c_cand_ids = res_c.get("candidate_article_ids", [])
        
        for g_id in gold_ids:
            a_rank = a_final_ids.index(g_id) + 1 if g_id in a_final_ids else (a_cand_ids.index(g_id) + 1 if g_id in a_cand_ids else None)
            b_rank = b_final_ids.index(g_id) + 1 if g_id in b_final_ids else (b_cand_ids.index(g_id) + 1 if g_id in b_cand_ids else None)
            c_rank = c_final_ids.index(g_id) + 1 if g_id in c_final_ids else (c_cand_ids.index(g_id) + 1 if g_id in c_cand_ids else None)
            
            in_a_top10 = g_id in a_final_ids
            in_b_top10 = g_id in b_final_ids
            in_c_top10 = g_id in c_final_ids
            
            recovered = not in_b_top10 and in_c_top10
            
            if in_c_top10:
                classification = "RECOVERED_BY_RERANK" if recovered else "HIT_IN_TOP_10"
            elif g_id in c_cand_ids:
                classification = "STILL_BELOW_TOP_K"
            elif g_id in b_cand_ids or g_id in a_cand_ids:
                classification = "FILTERED_BY_DIVERSITY"
            else:
                classification = "LEXICAL_CANDIDATE_MISS"
                
            traces.append({
                "question_id": q_id,
                "article_id": g_id,
                "baseline_rank": a_rank,
                "exp_b_rank": b_rank,
                "exp_c_rank": c_rank,
                "recovered": recovered,
                "classification": classification,
                "in_c_top10": in_c_top10
            })
            
    return traces

if __name__ == "__main__":
    run_experiment_c()
