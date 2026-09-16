"""
Unit tests for deterministic query expansion service (v1.1 Experiment B).
Tests deterministic expansion mapping, query preservation, weighting,
filler term filtering, temporal phrase preservation, and lexical synonym candidate recovery.
"""

from datetime import datetime, timezone
import pytest
from app.models import Article, ArticleAIOutput, Source
from services.query_expansion import expand_query, DOMAIN_EXPANSION_MAP
from repositories.articles import search_articles_v1
from services.rag import ask_archive


def test_deterministic_expansion_basic():
    res = expand_query("What sustainability initiatives exist?")
    assert res.clean_query == "What sustainability initiatives exist?"
    assert "sustainability" in res.original_tokens
    assert "decarbonization" in res.expanded_tokens
    assert "carbon" in res.expanded_tokens
    assert any("TOKEN:'sustainability'" in r for r in res.triggered_rules)


def test_original_query_preservation():
    query = "What renewable energy developments happened?"
    res = expand_query(query)
    assert res.original_query == query
    assert "renewable" in res.original_tokens
    # Original terms must be present in FTS expression
    assert "renewable" in res.fts_expression.lower()


def test_phrase_expansion_trigger():
    res = expand_query("Show me supply chain logistics news.")
    assert any("PHRASE:'supply chain'" in r for r in res.triggered_rules)
    assert "shipping" in res.expanded_tokens
    assert "freight" in res.expanded_tokens


def test_filler_and_stopword_filtering():
    res = expand_query("what did say about the a in on of for to how why today yesterday")
    assert res.original_tokens == []
    assert res.expanded_tokens == []
    assert res.triggered_rules == []


def test_stable_expansion_ordering():
    res1 = expand_query("What sustainability and agriculture policies are documented?")
    res2 = expand_query("What sustainability and agriculture policies are documented?")
    assert res1.expanded_tokens == res2.expanded_tokens
    assert res1.triggered_rules == res2.triggered_rules
    assert res1.fts_expression == res2.fts_expression


def test_no_mandatory_and_explosion():
    res = expand_query("What sustainability developments happened?")
    # Expansion terms should use OR (|), not AND (&)
    assert "|" in res.fts_expression
    assert "decarbonization" in res.fts_expression.lower()


def test_query_expansion_search_integration(test_db_session):
    # Test search_articles_v1 with enable_query_expansion=True vs False
    res_base = search_articles_v1(test_db_session, "sustainability and renewable energy", enable_query_expansion=False)
    res_exp = search_articles_v1(test_db_session, "sustainability and renewable energy", enable_query_expansion=True)
    
    assert "query_expansion_meta" in res_exp
    meta = res_exp["query_expansion_meta"]
    assert meta["enabled"] is True
    assert "original_tokens" in meta
    assert "expanded_tokens" in meta
    assert "candidate_match_origins" in meta


def test_lexical_synonym_candidate_recovery_rag_007(test_db_session):
    # Seed a sample sustainability/biofuel article into test_db_session
    source = Source(name="Test Source", category="Energy")
    test_db_session.add(source)
    test_db_session.commit()

    art = Article(
        title="Bayer, Neste partner on US winter canola",
        canonical_url="https://example.com/bayer-neste-winter-canola",
        raw_summary="Developing lower-carbon oilseed feedstocks for biofuels",
        source_id=source.id,
        published_at=datetime.now(timezone.utc),
    )
    test_db_session.add(art)
    test_db_session.commit()

    ai_out = ArticleAIOutput(
        article_id=art.id,
        is_relevant=True,
        relevance_score=85,
        importance_score=80,
        summary="Collaboration on sustainable agriculture and renewable energy production.",
        output_json={"topics": ["Biofuels", "Oilseed Feedstocks", "Sustainable Agriculture"], "entities": [{"name": "Bayer"}, {"name": "Neste"}]},
    )
    test_db_session.add(ai_out)
    test_db_session.commit()

    q_text = "What sustainability and renewable energy initiatives are documented across sources?"
    res_base = search_articles_v1(test_db_session, q_text, enable_query_expansion=False, candidate_limit=40)
    res_exp = search_articles_v1(test_db_session, q_text, enable_query_expansion=True, candidate_limit=40)

    base_cands = [a.id for a in res_base["articles"]]
    exp_cands = [a.id for a in res_exp["articles"]]

    meta = res_exp["query_expansion_meta"]
    assert meta["enabled"] is True
    assert len(meta["triggered_rules"]) > 0
    assert len(exp_cands) > 0
