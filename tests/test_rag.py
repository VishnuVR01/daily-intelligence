"""
Unit & integration tests for Local Grounded RAG Engine Service (v1).
"""

from datetime import datetime, date, timedelta, timezone
from unittest.mock import patch
import pytest
from sqlalchemy.orm import Session

from app.models import Article, ArticleAIOutput, Country, Source
from services.rag import ask_archive, _call_ollama_rag


@pytest.fixture
def rag_sample_data(test_db_session: Session):
    """Seed test articles for RAG evidence retrieval and citations."""
    src = Source(name="Financial Times", source_family="news", trust_tier="institutional", category="Markets & Economy")
    test_db_session.add(src)
    test_db_session.flush()

    now_utc = datetime.now(timezone.utc)

    art1 = Article(
        source_id=src.id,
        title="Reserve Bank Inflation Outlook and Interest Rate Policy",
        canonical_url="https://ft.com/rbi-inflation-policy-2026",
        published_at=now_utc - timedelta(days=1),
        primary_category="Markets & Economy",
    )
    test_db_session.add(art1)
    test_db_session.flush()

    ai1 = ArticleAIOutput(
        article_id=art1.id,
        is_relevant=True,
        relevance_score=95,
        importance_score=90,
        primary_category="Markets & Economy",
        summary="RBI Governor announced benchmark rate pause due to moderating consumer inflation.",
        output_json={"topics": ["Inflation", "Monetary Policy"], "entities": [{"name": "RBI"}]},
        status="success",
    )
    test_db_session.add(ai1)
    test_db_session.commit()

    return {"art1": art1, "src": src, "now_utc": now_utc}


def test_rag_empty_question(test_db_session: Session):
    res = ask_archive(test_db_session, question="")
    assert res["insufficient_evidence"] is True
    assert res["evidence_count"] == 0
    assert len(res["citations"]) == 0


def test_rag_no_matching_evidence(test_db_session: Session):
    res = ask_archive(test_db_session, question="nonexistentquantumteleportationkeyword999")
    assert res["insufficient_evidence"] is True
    assert res["evidence_count"] == 0
    assert "No matching intelligence records" in res["answer"]


@patch("services.rag._call_ollama_rag")
def test_rag_grounded_answer_with_citations(mock_ollama, test_db_session: Session, rag_sample_data):
    art1 = rag_sample_data["art1"]

    mock_ollama.return_value = {
        "answer": "The Reserve Bank announced a policy rate pause as inflation moderated [1].",
        "key_themes": ["Inflation", "Monetary Policy"],
        "confidence": "high",
        "insufficient_evidence": False,
        "cited_record_numbers": [1],
    }

    res = ask_archive(test_db_session, question="What did RBI say about inflation?")

    assert res["insufficient_evidence"] is False
    assert res["evidence_count"] >= 1
    assert "Reserve Bank" in res["answer"]
    assert len(res["citations"]) == 1

    # Verify real citation mapping
    cit = res["citations"][0]
    assert cit["article_id"] == art1.id
    assert cit["headline"] == art1.title
    assert cit["canonical_url"] == art1.canonical_url


@patch("services.rag._call_ollama_rag")
def test_rag_fallback_when_ollama_offline(mock_ollama, test_db_session: Session, rag_sample_data):
    art1 = rag_sample_data["art1"]
    mock_ollama.return_value = None  # Simulate offline Ollama

    res = ask_archive(test_db_session, question="inflation policy")

    assert res["evidence_count"] >= 1
    assert len(res["citations"]) >= 1
    assert res["citations"][0]["article_id"] == art1.id
    assert "Financial Times" in res["answer"]
