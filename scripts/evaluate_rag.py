"""
RAG Evaluation Runner Script (v1)
Runs the complete RAG Benchmark v1 dataset against the local RAG engine (ask_archive)
and computes deterministic precision, citation validity, temporal accuracy, and negative-test refusal metrics.
Generates machine-readable reports/rag_benchmark_v1.json and human-readable reports/rag_benchmark_v1.md.
"""

from datetime import datetime, date, timedelta, timezone
import json
import os
import time
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.config import get_settings
from app.models import Article
from repositories.articles import get_article_ai_output
from services.rag import ask_archive
from scripts.validate_gold_fingerprints import validate_gold_fingerprints


def load_benchmark_dataset(filepath: str = "benchmarks/rag_v1.json") -> List[Dict[str, Any]]:
    if not os.path.isabs(filepath):
        filepath = os.path.join(PROJECT_ROOT, filepath)
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Benchmark dataset not found at {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, dict) and "questions" in data:
            return data["questions"]
        return data


def calculate_question_metrics(
    item: Dict[str, Any],
    rag_result: Dict[str, Any],
    retrieved_articles: List[Article],
    execution_time_ms: float,
    tz_name: str = "Europe/London",
) -> Dict[str, Any]:
    core_ids = set(item.get("gold_core_article_ids", item.get("expected_article_ids", [])))
    optional_ids = set(item.get("gold_optional_article_ids", []))
    expected_topics = [t.lower() for t in item.get("expected_topics", [])]
    expected_entities = [e.lower() for e in item.get("expected_entities", [])]

    retrieved_ids = [a.id for a in retrieved_articles]
    retrieved_titles = [a.title for a in retrieved_articles]
    retrieved_sources = [a.source.name if a.source else "Unknown" for a in retrieved_articles]

    evidence_count = len(retrieved_articles)

    # 1. Expected Core Article Hit Rate & Optional Coverage
    if core_ids:
        core_hits = core_ids.intersection(set(retrieved_ids))
        core_hit_rate = round(len(core_hits) / len(core_ids), 4)
    else:
        core_hit_rate = 1.0 if not item.get("should_be_answerable", True) else 0.0

    if optional_ids:
        optional_hits = optional_ids.intersection(set(retrieved_ids))
        optional_coverage = round(len(optional_hits) / len(optional_ids), 4)
    else:
        optional_coverage = 1.0

    expected_hit_rate = core_hit_rate

    # 2. Topic Coverage
    retrieved_categories = set()
    for a in retrieved_articles:
        ai_out = get_article_ai_output(a)
        cat = a.primary_category or (ai_out.primary_category if ai_out else None) or (a.source.category if a.source else None)
        if cat:
            retrieved_categories.add(cat.lower())

    if expected_topics:
        topic_hits = sum(1 for t in expected_topics if any(t in cat for cat in retrieved_categories))
        topic_coverage = round(topic_hits / len(expected_topics), 4)
    else:
        topic_coverage = 1.0

    # 3. Duplicate Rate & Source Diversity
    if retrieved_ids:
        dup_rate = round(1.0 - (len(set(retrieved_ids)) / len(retrieved_ids)), 4)
        source_diversity = round(len(set(retrieved_sources)) / len(retrieved_sources), 4)
    else:
        dup_rate = 0.0
        source_diversity = 0.0

    # 4. Temporal Scoping Accuracy
    expected_scope = item.get("expected_date_scope", "all")
    try:
        local_tz = ZoneInfo(tz_name)
    except Exception:
        local_tz = timezone.utc

    today_local = datetime.now(local_tz).date()
    temporal_pass = True

    if expected_scope == "today":
        for a in retrieved_articles:
            dt = a.published_at or a.collected_at
            if dt:
                dt_local = dt.astimezone(local_tz).date() if dt.tzinfo else dt.date()
                if dt_local != today_local:
                    temporal_pass = False
                    break
    elif expected_scope == "yesterday":
        yesterday_local = today_local - timedelta(days=1)
        for a in retrieved_articles:
            dt = a.published_at or a.collected_at
            if dt:
                dt_local = dt.astimezone(local_tz).date() if dt.tzinfo else dt.date()
                if dt_local != yesterday_local:
                    temporal_pass = False
                    break
    elif expected_scope == "this_week":
        start_week = today_local - timedelta(days=6)
        for a in retrieved_articles:
            dt = a.published_at or a.collected_at
            if dt:
                dt_local = dt.astimezone(local_tz).date() if dt.tzinfo else dt.date()
                if not (start_week <= dt_local <= today_local):
                    temporal_pass = False
                    break

    # 5. Citation Metrics
    citations = rag_result.get("citations", [])
    citation_count = len(citations)
    fake_citations = 0

    for c in citations:
        c_id = c.get("article_id")
        if c_id not in retrieved_ids:
            fake_citations += 1

    citation_validity = (fake_citations == 0)

    # 6. Negative Test / Refusal Accuracy
    should_be_answerable = item.get("should_be_answerable", True)
    insufficient = bool(rag_result.get("insufficient_evidence", False))
    answer_text = rag_result.get("answer", "")

    if not should_be_answerable:
        # Refusal is valid if insufficient == True OR evidence_count == 0 OR answer mentions insufficient evidence
        refusal_pass = (insufficient or evidence_count == 0 or "insufficient" in answer_text.lower() or "no matching" in answer_text.lower())
    else:
        refusal_pass = True

    answer_zero_evidence = (evidence_count == 0 and len(answer_text) > 50 and not insufficient)

    return {
        "benchmark_id": item["id"],
        "category": item["category"],
        "question": item["question"],
        "expected_date_scope": expected_scope,
        "should_be_answerable": should_be_answerable,
        "execution_time_ms": round(execution_time_ms, 2),
        "evidence_count": evidence_count,
        "retrieved_article_ids": retrieved_ids,
        "retrieved_titles": retrieved_titles,
        "retrieved_sources": retrieved_sources,
        "citation_count": citation_count,
        "fake_citations_count": fake_citations,
        "citation_validity": citation_validity,
        "expected_hit_rate": expected_hit_rate,
        "core_hit_rate": core_hit_rate,
        "optional_coverage": optional_coverage,
        "topic_coverage": topic_coverage,
        "duplicate_rate": dup_rate,
        "source_diversity": source_diversity,
        "temporal_pass": temporal_pass,
        "insufficient_evidence_flag": insufficient,
        "refusal_pass": refusal_pass,
        "answer_zero_evidence_warning": answer_zero_evidence,
        "answer_preview": answer_text[:200] + ("..." if len(answer_text) > 200 else ""),
        "requires_manual_review": True,  # For subjective answer completeness/quality
    }


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_JSON_REPORT = os.path.join(PROJECT_ROOT, "reports", "rag_benchmark_v1.json")
DEFAULT_MD_REPORT = os.path.join(PROJECT_ROOT, "reports", "rag_benchmark_v1.md")


def run_evaluation(
    benchmark_path: str = "benchmarks/rag_v1.json",
    json_report_path: Optional[str] = None,
    md_report_path: Optional[str] = None,
    enable_query_expansion: bool = False,
    enable_query_aware_reranking: bool = False,
    skip_llm: bool = False,
) -> Dict[str, Any]:
    if json_report_path is None:
        json_report_path = os.path.join(PROJECT_ROOT, "reports", "rag_benchmark_v1.json")
    if md_report_path is None:
        md_report_path = os.path.join(PROJECT_ROOT, "reports", "rag_benchmark_v1.md")
    # Pre-scoring Fingerprint Validation: Guard against article-ID/data drift
    dataset, drift_report = validate_gold_fingerprints(benchmark_path)
    settings = get_settings()
    tz_name = settings.app_timezone or "Europe/London"

    db: Session = SessionLocal()
    question_results = []

    print("=" * 90, flush=True)
    print(f"RUNNING RAG EVALUATION BENCHMARK ({len(dataset)} Questions from {benchmark_path})", flush=True)
    print(f"Pre-Scoring Fingerprint Validation: {drift_report['drift_detected_count']} drift events across {drift_report['total_gold_inspections']} gold article checks.", flush=True)
    print("=" * 90, flush=True)

    total_start = time.time()
    successful_execs = 0
    failed_execs = 0

    try:
        for idx, item in enumerate(dataset, 1):
            q_id = item["id"]
            q_text = item["question"]
            print(f"[{idx:02d}/{len(dataset):02d}] {q_id}: {q_text[:60]}...", flush=True)

            start_t = time.time()
            try:
                rag_res = ask_archive(
                    db,
                    question=q_text,
                    enable_query_expansion=enable_query_expansion,
                    enable_query_aware_reranking=enable_query_aware_reranking,
                    skip_llm=skip_llm,
                )
                duration_ms = (time.time() - start_t) * 1000.0
                successful_execs += 1
            except Exception as exc:
                duration_ms = (time.time() - start_t) * 1000.0
                failed_execs += 1
                rag_res = {
                    "question": q_text,
                    "answer": f"Execution Error: {exc}",
                    "confidence": "low",
                    "evidence_count": 0,
                    "citations": [],
                    "insufficient_evidence": True,
                }

            # Fetch retrieved Article objects from DB
            retrieved_ids = rag_res.get("retrieved_article_ids") or [c["article_id"] for c in rag_res.get("citations", []) if "article_id" in c]
            # Also check evidence count from result
            evidence_count = rag_res.get("evidence_count", 0)
            
            # Fetch Article models for retrieved IDs
            articles = []
            if retrieved_ids:
                articles = db.query(Article).filter(Article.id.in_(retrieved_ids)).all()

            metrics = calculate_question_metrics(item, rag_res, articles, duration_ms, tz_name=tz_name)
            metrics["raw_rag_result"] = rag_res
            question_results.append(metrics)

    finally:
        db.close()

    total_duration_sec = round(time.time() - total_start, 2)

    # Compute Aggregates
    total_q = len(question_results)
    answerable_q = [m for m in question_results if m["should_be_answerable"]]
    avg_evidence_count = round(sum(m["evidence_count"] for m in question_results) / total_q, 2) if total_q > 0 else 0.0
    avg_hit_rate = round(sum(m["core_hit_rate"] for m in answerable_q) / len(answerable_q), 4) if answerable_q else 0.0
    avg_optional_coverage = round(sum(m["optional_coverage"] for m in answerable_q) / len(answerable_q), 4) if answerable_q else 0.0
    temporal_accuracy = round(sum(1 for m in question_results if m["temporal_pass"]) / total_q * 100.0, 1) if total_q > 0 else 0.0
    citation_validity_rate = round(sum(1 for m in question_results if m["citation_validity"]) / total_q * 100.0, 1) if total_q > 0 else 0.0
    unsupported_citation_rate = round(sum(1 for m in question_results if m["fake_citations_count"] > 0) / total_q * 100.0, 1) if total_q > 0 else 0.0

    neg_items = [m for m in question_results if not m["should_be_answerable"]]
    neg_refusal_acc = round(sum(1 for m in neg_items if m["refusal_pass"]) / len(neg_items) * 100.0, 1) if neg_items else 100.0

    avg_source_diversity = round(sum(m["source_diversity"] for m in question_results if m["evidence_count"] > 0) / max(1, sum(1 for m in question_results if m["evidence_count"] > 0)), 4)
    exec_success_rate = round(successful_execs / total_q * 100.0, 1) if total_q > 0 else 0.0

    # Overall Score Formula (Weighted baseline metric):
    overall_score = round(
        (0.25 * (avg_hit_rate * 100.0)) +
        (0.25 * temporal_accuracy) +
        (0.20 * citation_validity_rate) +
        (0.20 * neg_refusal_acc) +
        (0.10 * exec_success_rate),
        2
    )

    # Sort questions by performance to find best and worst
    for m in question_results:
        item_score = (m["core_hit_rate"] * 40.0) + (30.0 if m["citation_validity"] else 0.0) + (30.0 if m["temporal_pass"] else 0.0)
        if not m["should_be_answerable"]:
            item_score = 100.0 if m["refusal_pass"] else 0.0
        m["item_score"] = round(item_score, 2)

    sorted_by_score = sorted(question_results, key=lambda x: x["item_score"], reverse=True)
    strongest_5 = sorted_by_score[:5]
    weakest_5 = sorted_by_score[-5:]

    summary_report = {
        "benchmark_version": "1.0-validated",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_questions": total_q,
        "successful_executions": successful_execs,
        "failed_executions": failed_execs,
        "total_duration_sec": total_duration_sec,
        "aggregate_metrics": {
            "overall_baseline_score": overall_score,
            "retrieval_hit_rate": avg_hit_rate,
            "core_retrieval_hit_rate": avg_hit_rate,
            "optional_gold_coverage": avg_optional_coverage,
            "temporal_accuracy_pct": temporal_accuracy,
            "citation_validity_pct": citation_validity_rate,
            "unsupported_citation_rate_pct": unsupported_citation_rate,
            "negative_test_refusal_accuracy_pct": neg_refusal_acc,
            "average_evidence_count": avg_evidence_count,
            "average_source_diversity": avg_source_diversity,
            "execution_success_rate_pct": exec_success_rate,
        },
        "strongest_questions": [s["benchmark_id"] for s in strongest_5],
        "weakest_questions": [w["benchmark_id"] for w in weakest_5],
        "fingerprint_validation_report": drift_report,
        "question_results": question_results,
    }

    # Ensure reports directory exists
    json_report_path = os.path.abspath(json_report_path)
    md_report_path = os.path.abspath(md_report_path)
    os.makedirs(os.path.dirname(json_report_path), exist_ok=True)

    # Write JSON report
    with open(json_report_path, "w", encoding="utf-8") as f:
        # Exclude raw SQLAlchemy objects if any
        clean_summary = json.loads(json.dumps(summary_report, default=str))
        json.dump(clean_summary, f, indent=2)

    # Write Markdown report
    _generate_markdown_report(summary_report, md_report_path)

    print("\n" + "=" * 90)
    print(f"EVALUATION COMPLETE in {total_duration_sec}s")
    print(f"Overall Baseline Score : {overall_score} / 100")
    print(f"Retrieval Hit Rate     : {avg_hit_rate * 100:.1f}%")
    print(f"Temporal Accuracy      : {temporal_accuracy}%")
    print(f"Citation Validity      : {citation_validity_rate}%")
    print(f"Negative Refusal Acc   : {neg_refusal_acc}%")
    print(f"JSON Report written to : {json_report_path}")
    print(f"Markdown Report written: {md_report_path}")
    print("=" * 90)

    return summary_report


def _generate_markdown_report(summary: Dict[str, Any], md_path: str):
    agg = summary["aggregate_metrics"]
    q_results = summary["question_results"]

    lines = []
    lines.append("# RAG Benchmark v1 — Baseline Evaluation Report")
    lines.append("")
    lines.append(f"**Timestamp (UTC)**: {summary['timestamp']}  ")
    lines.append(f"**Total Duration**: {summary['total_duration_sec']}s  ")
    lines.append(f"**Overall Baseline Score**: **{agg['overall_baseline_score']} / 100**")
    lines.append("")

    lines.append("## Executive Summary")
    lines.append("")
    lines.append("| Metric | Value | Target / Ideal |")
    lines.append("| :--- | :---: | :---: |")
    lines.append(f"| **Questions Tested** | `{summary['total_questions']}` | 25 |")
    lines.append(f"| **Successful Executions** | `{summary['successful_executions']}` | 25 |")
    lines.append(f"| **Failed Executions** | `{summary['failed_executions']}` | 0 |")
    lines.append(f"| **Retrieval Hit Rate** | `{agg['retrieval_hit_rate'] * 100:.1f}%` | 100.0% |")
    lines.append(f"| **Temporal Accuracy** | `{agg['temporal_accuracy_pct']}%` | 100.0% |")
    lines.append(f"| **Citation Validity Rate** | `{agg['citation_validity_pct']}%` | 100.0% |")
    lines.append(f"| **Unsupported Citation Rate** | `{agg['unsupported_citation_rate_pct']}%` | 0.0% |")
    lines.append(f"| **Negative-Test Refusal Acc** | `{agg['negative_test_refusal_accuracy_pct']}%` | 100.0% |")
    lines.append(f"| **Average Evidence Count** | `{agg['average_evidence_count']}` | 3–10 |")
    lines.append(f"| **Source Diversity** | `{agg['average_source_diversity']}` | > 0.5 |")
    lines.append(f"| **Execution Success Rate** | `{agg['execution_success_rate_pct']}%` | 100.0% |")
    lines.append("")

    lines.append("## Category Performance")
    lines.append("")
    lines.append("| Category | Total | Avg Evidence | Hit Rate | Citation Valid % | Refusal Acc % |")
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")

    cat_groups: Dict[str, List[Dict[str, Any]]] = {}
    for q in q_results:
        cat_groups.setdefault(q["category"], []).append(q)

    for cat_name, items in sorted(cat_groups.items()):
        c_count = len(items)
        c_avg_ev = round(sum(i["evidence_count"] for i in items) / c_count, 1)
        c_hit = round(sum(i["expected_hit_rate"] for i in items if i["should_be_answerable"]) / max(1, sum(1 for i in items if i["should_be_answerable"])) * 100, 1)
        c_cit = round(sum(1 for i in items if i["citation_validity"]) / c_count * 100, 1)
        c_neg = [i for i in items if not i["should_be_answerable"]]
        c_ref = round(sum(1 for i in c_neg if i["refusal_pass"]) / len(c_neg) * 100, 1) if c_neg else "N/A"

        lines.append(f"| `{cat_name}` | {c_count} | {c_avg_ev} | {c_hit}% | {c_cit}% | {c_ref}{'%' if isinstance(c_ref, float) else ''} |")
    lines.append("")

    lines.append("## Five Strongest Questions")
    lines.append("")
    sorted_q = sorted(q_results, key=lambda x: x.get("item_score", 0), reverse=True)
    for q in sorted_q[:5]:
        lines.append(f"- **{q['benchmark_id']}** ({q['category']}): *\"{q['question']}\"*")
        lines.append(f"  - Hit Rate: {q['expected_hit_rate'] * 100:.1f}%, Evidence Count: {q['evidence_count']}, Citation Validity: {q['citation_validity']}")

    lines.append("")
    lines.append("## Five Weakest Questions")
    lines.append("")
    for q in sorted_q[-5:]:
        lines.append(f"- **{q['benchmark_id']}** ({q['category']}): *\"{q['question']}\"*")
        lines.append(f"  - Hit Rate: {q['expected_hit_rate'] * 100:.1f}%, Evidence Count: {q['evidence_count']}, Temporal Pass: {q['temporal_pass']}, Refusal Pass: {q['refusal_pass']}")

    lines.append("")
    lines.append("## Observed Failure Patterns")
    lines.append("")
    lines.append("1. **Keyword Over-Filtering on Temporal Phrases**: Questions with phrase `today` return 0 evidence when no articles were collected/published on today's specific date.")
    lines.append("2. **Fallback Summary Citation Mapping**: When Ollama is offline or un-invoked, fallback summary mode formats citations using all context records.")
    lines.append("3. **Cross-Language Query Matching**: Queries in English for Finnish news (`Yle News`) rely on PostgreSQL tsvector translation or title matching.")
    lines.append("")

    lines.append("## Manual-Review Queue")
    lines.append("")
    lines.append("The following subjective quality dimensions are queued for manual evaluation in v1:")
    lines.append("- Answer Completeness")
    lines.append("- Analytical Synthesis Quality")
    lines.append("- Evidence Relevance Precision")
    lines.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    run_evaluation()
