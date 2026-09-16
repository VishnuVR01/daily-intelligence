"""
Unit Tests for RAG Benchmark & Evaluator System
Verifies dataset schema, metric calculations, citation validity checks,
temporal accuracy validation, negative-test refusal logic, and error handling.
"""

from datetime import datetime, date, timezone
import json
import os
import pytest

from app.models import Article, Source
from scripts.evaluate_rag import load_benchmark_dataset, calculate_question_metrics, run_evaluation


def test_benchmark_dataset_validation():
    """Verify benchmarks/rag_v1.json exists, parses, and contains ~25 valid items."""
    dataset = load_benchmark_dataset("benchmarks/rag_v1.json")
    assert len(dataset) >= 20, f"Expected at least 20 benchmark items, found {len(dataset)}"

    required_keys = {
        "id", "category", "question", "expected_date_scope",
        "expected_topics", "expected_entities", "expected_min_evidence",
        "must_cite_sources", "should_be_answerable"
    }

    for item in dataset:
        missing = required_keys - set(item.keys())
        assert not missing, f"Item {item.get('id')} missing required fields: {missing}"


def test_calculate_question_metrics_precision_and_hit_rate():
    """Verify hit_rate, evidence_count, duplicate_rate, and source_diversity calculations."""
    item = {
        "id": "RAG-TEST-1",
        "category": "test",
        "question": "Test question?",
        "expected_date_scope": "all",
        "expected_article_ids": [10, 20, 30],
        "expected_topics": ["ai"],
        "should_be_answerable": True,
    }

    s1 = Source(name="Source A")
    s2 = Source(name="Source B")
    a1 = Article(id=10, title="Art 1", source=s1, primary_category="AI")
    a2 = Article(id=20, title="Art 2", source=s2, primary_category="AI")

    rag_result = {
        "citations": [
            {"article_id": 10, "headline": "Art 1"},
            {"article_id": 20, "headline": "Art 2"},
        ],
        "answer": "Test answer",
        "evidence_count": 2,
        "insufficient_evidence": False,
    }

    metrics = calculate_question_metrics(item, rag_result, [a1, a2], execution_time_ms=120.0)

    assert metrics["evidence_count"] == 2
    assert metrics["expected_hit_rate"] == round(2 / 3, 4)
    assert metrics["citation_validity"] is True
    assert metrics["fake_citations_count"] == 0
    assert metrics["source_diversity"] == 1.0
    assert metrics["duplicate_rate"] == 0.0


def test_citation_validation_detects_fake_citations():
    """Verify citation_validity flags citations for un-retrieved article IDs."""
    item = {
        "id": "RAG-TEST-2",
        "category": "test",
        "question": "Fake citation test?",
        "expected_date_scope": "all",
        "should_be_answerable": True,
    }

    a1 = Article(id=10, title="Art 1", source=Source(name="Source A"))

    rag_result = {
        "citations": [
            {"article_id": 10, "headline": "Art 1"},
            {"article_id": 999, "headline": "Fabricated Citation"},
        ],
        "answer": "Answer with fake citation [999].",
        "evidence_count": 1,
        "insufficient_evidence": False,
    }

    metrics = calculate_question_metrics(item, rag_result, [a1], execution_time_ms=100.0)

    assert metrics["citation_validity"] is False
    assert metrics["fake_citations_count"] == 1


def test_temporal_validation_pass_and_fail():
    """Verify temporal_pass logic for today vs all scopes."""
    item_all = {
        "id": "RAG-TEST-3",
        "category": "test",
        "question": "Archive test?",
        "expected_date_scope": "all",
        "should_be_answerable": True,
    }

    a_old = Article(id=5, title="Old Art", published_at=datetime(2025, 1, 1, tzinfo=timezone.utc))
    metrics_all = calculate_question_metrics(item_all, {}, [a_old], execution_time_ms=50.0)
    assert metrics_all["temporal_pass"] is True

    item_today = {
        "id": "RAG-TEST-4",
        "category": "test",
        "question": "Today test?",
        "expected_date_scope": "today",
        "should_be_answerable": True,
    }

    metrics_today_fail = calculate_question_metrics(item_today, {}, [a_old], execution_time_ms=50.0)
    assert metrics_today_fail["temporal_pass"] is False


def test_negative_test_refusal_evaluation():
    """Verify refusal_pass for unanswerable negative tests."""
    neg_item = {
        "id": "RAG-NEG-1",
        "category": "insufficient_evidence",
        "question": "What are sales for non-existent product?",
        "expected_date_scope": "all",
        "should_be_answerable": False,
    }

    rag_refusal = {
        "answer": "No matching intelligence records were found in the archive for this query.",
        "evidence_count": 0,
        "citations": [],
        "insufficient_evidence": True,
    }

    metrics = calculate_question_metrics(neg_item, rag_refusal, [], execution_time_ms=80.0)
    assert metrics["refusal_pass"] is True


def test_graceful_rag_failure_handling():
    """Verify evaluator handles RAG errors gracefully without throwing unhandled exceptions."""
    neg_item = {
        "id": "RAG-ERR-1",
        "category": "test",
        "question": "Error test?",
        "expected_date_scope": "all",
        "should_be_answerable": True,
    }

    error_rag_res = {
        "answer": "Execution Error: Database timeout",
        "evidence_count": 0,
        "citations": [],
        "insufficient_evidence": True,
    }

    metrics = calculate_question_metrics(neg_item, error_rag_res, [], execution_time_ms=300.0)
    assert metrics["execution_time_ms"] == 300.0
    assert metrics["evidence_count"] == 0
    assert metrics["citation_validity"] is True
