"""Unit test suite for Stage 4B: Entity Extraction & Resolution.
"""

import json
import pytest
from pathlib import Path
from sqlalchemy.orm import Session

from app.models import Article, ArticleAIOutput, Entity, EntityAlias, EntityMention
from services.knowledge.extraction import parse_entities_from_ai_output
from services.knowledge.normalization import (
    normalize_entity_type,
    normalize_entity_name,
    CANONICAL_ONTOLOGY,
)
from services.knowledge.resolution import resolve_entity, is_generic_term
from services.knowledge.service import process_article_entities


def test_ontology_mapping():
    assert normalize_entity_type("CENTRAL_BANK") == "CENTRAL_BANK"
    assert normalize_entity_type("central_bank") == "CENTRAL_BANK"
    assert normalize_entity_type("company") == "COMPANY"
    assert normalize_entity_type("corporation") == "COMPANY"
    assert normalize_entity_type("country") == "COUNTRY"
    assert normalize_entity_type("person") == "PERSON"
    assert normalize_entity_type("commodity") == "COMMODITY"
    assert normalize_entity_type("technology") == "TECHNOLOGY"
    assert normalize_entity_type("product") == "PRODUCT"
    assert normalize_entity_type("government_body") == "GOVERNMENT_BODY"
    assert normalize_entity_type("unknown_type") == "ORGANIZATION"


def test_normalize_entity_name():
    assert normalize_entity_name("Apple Inc.") == "apple"
    assert normalize_entity_name("Federal Reserve") == "federal reserve"
    assert normalize_entity_name("U.S. Dollar") == "u.s. dollar"


def test_generic_term_suppression():
    assert is_generic_term("government") is True
    assert is_generic_term("officials") is True
    assert is_generic_term("company") is True
    assert is_generic_term("analysts") is True
    assert is_generic_term("Federal Reserve") is False


def test_extraction_parser():
    ai_output_json = {
        "entities": [
            {"name": "Federal Reserve", "type": "CENTRAL_BANK"},
            "Microsoft",
            {"name": "Jerome Powell", "type": "PERSON"},
        ],
        "key_entities": ["United States", "Apple"],
    }
    extracted = parse_entities_from_ai_output(ai_output_json)
    assert len(extracted) >= 3
    names = [e["raw_name"] for e in extracted]
    assert "Federal Reserve" in names
    assert "Microsoft" in names
    assert "Jerome Powell" in names


def test_benchmark_dataset(test_db_session: Session):
    benchmark_file = Path(__file__).resolve().parent.parent / "benchmarks" / "entity_resolution_v1.json"
    assert benchmark_file.exists()

    with open(benchmark_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    total = len(cases)
    correct = 0
    false_merges = 0
    false_merge_details = []

    for case in cases:
        raw_name = case["raw_name"]
        raw_type = case["raw_type"]
        expected_canonical = case["expected_canonical"]
        should_resolve = case["should_resolve"]

        resolved = resolve_entity(test_db_session, raw_name, raw_type)

        if not should_resolve:
            if resolved is None:
                correct += 1
        else:
            if resolved is not None and resolved["canonical_name"] == expected_canonical:
                correct += 1
            elif resolved is not None and resolved["canonical_name"] != expected_canonical:
                false_merges += 1
                false_merge_details.append(
                    f"raw_name={raw_name}, expected={expected_canonical}, got={resolved['canonical_name']}"
                )

    precision = (correct / total) * 100
    assert false_merges == 0, f"Expected 0 false merges, got {false_merges}: {false_merge_details}"
    assert precision >= 95.0, f"Expected precision >= 95%, got {precision:.2f}%"


def test_process_article_entities_idempotency(test_db_session: Session):
    # Setup test article and AI output
    article = Article(
        title="Fed Raises Rates Test 4B",
        canonical_url="http://example.com/fed-rates-test-4b-unique",
        extracted_text="The Federal Reserve raised rates. Jerome Powell spoke in the US.",
        source_id=None,
    )
    test_db_session.add(article)
    test_db_session.flush()

    ai_output = ArticleAIOutput(
        article_id=article.id,
        status="success",
        is_relevant=True,
        importance_score=85,
        primary_category="MONETARY_POLICY",
        output_json={
            "entities": [
                {"name": "Federal Reserve", "type": "CENTRAL_BANK"},
                {"name": "Jerome Powell", "type": "PERSON"},
                {"name": "US", "type": "COUNTRY"},
            ]
        },
    )
    test_db_session.add(ai_output)
    test_db_session.commit()


    # First run
    res1 = process_article_entities(test_db_session, article.id)
    assert res1["mentions_created"] > 0

    # Verify mentions in DB
    mentions1 = test_db_session.query(EntityMention).filter(EntityMention.article_id == article.id).all()
    count1 = len(mentions1)

    # Second run without --reprocess (should skip)
    res2 = process_article_entities(test_db_session, article.id)
    assert res2["skipped"] is True

    # Third run with --reprocess (should update idempotently without creating duplicate mentions)
    res3 = process_article_entities(test_db_session, article.id, reprocess=True)
    mentions3 = test_db_session.query(EntityMention).filter(EntityMention.article_id == article.id).all()
    assert len(mentions3) == count1
