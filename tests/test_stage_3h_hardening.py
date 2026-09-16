import pytest
from datetime import date, datetime, timezone
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.main import app
from app.models import Article, Source, EventCluster, DailyEdition, EditionEvent, EventEditorialProse, EditionBrief, ArticleAIOutput
from services.editorial.clustering import resolve_article_category
from services.editorial.selection import (
    map_category_to_section,
    calculate_lead_significance_score,
    CATEGORY_TO_SECTION,
)
from services.editorial.validator import is_generic_theme_title
from services.editorial.synthesis import EditionBriefResult, synthesize_edition_brief_and_themes


@pytest.fixture
def client():
    return TestClient(app)


def test_category_resolution_hierarchy_and_ayana_bio(test_db_session: Session):
    # 1. Test Ayana Bio resolution
    source = Source(name="AgFunderNews", feed_url="https://example.com/feed", category="commodities", trust_tier="useful")
    test_db_session.add(source)
    test_db_session.commit()

    art = Article(
        source_id=source.id,
        title="Exclusive: Ayana Bio acquires Meati Foods assets for a steal to scale plant cell culture tech with Zenfold in India",
        canonical_url="https://example.com/ayana-bio-1",
        published_at=datetime.now(timezone.utc),
    )
    test_db_session.add(art)
    test_db_session.commit()

    ai_out = ArticleAIOutput(
        article_id=art.id,
        primary_category="Industry & Operations",
        is_relevant=True,
        importance_score=75,
        status="success",
    )
    test_db_session.add(ai_out)
    test_db_session.commit()

    # AI primary category priority check
    resolved_cat = resolve_article_category(art, ai_out)
    assert resolved_cat == "Industry & Operations"

    section = map_category_to_section(resolved_cat)
    assert section == "BUSINESS"  # NOT ENERGY!


def test_generic_theme_rejection():
    bad_themes = [
        "Tech Key Developments",
        "World Developments",
        "Business News",
        "Energy Updates",
        "Technology Stories",
        "Key Developments",
    ]
    for bt in bad_themes:
        assert is_generic_theme_title(bt) is True

    good_themes = [
        "AI Infrastructure Efficiency",
        "European Airspace Security",
        "Middle East Humanitarian Conditions",
        "Monetary Policy Divergence",
        "Energy Supply Pressure",
    ]
    for gt in good_themes:
        assert is_generic_theme_title(gt) is False


def test_lead_significance_score(test_db_session: Session):
    source_gov = Source(name="Federal Reserve", feed_url="https://example.com/fed", source_type="CENTRAL_BANK", trust_tier="core")
    source_blog = Source(name="AWS Machine Learning Blog", feed_url="https://example.com/aws", source_type="COMPANY_PRIMARY", trust_tier="useful")
    test_db_session.add_all([source_gov, source_blog])
    test_db_session.commit()

    art_fed = Article(source_id=source_gov.id, title="FOMC Rate Decision", canonical_url="https://example.com/fed-1")
    art_aws = Article(source_id=source_blog.id, title="Prompt Caching Update", canonical_url="https://example.com/aws-1")
    test_db_session.add_all([art_fed, art_aws])
    test_db_session.commit()

    # Fed event with corroboration
    cl_fed = type("MockCluster", (), {
        "cluster_score": 65.0,
        "distinct_source_count": 2,
        "primary_article": art_fed,
        "primary_article_id": art_fed.id,
    })()

    # AWS event single source
    cl_aws = type("MockCluster", (), {
        "cluster_score": 75.0,
        "distinct_source_count": 1,
        "primary_article": art_aws,
        "primary_article_id": art_aws.id,
    })()

    score_fed = calculate_lead_significance_score(cl_fed, "ECONOMY", {})
    score_aws = calculate_lead_significance_score(cl_aws, "TECH", {})

    # Fed gets +10 corroboration + +10 domain + +15 central bank = +35 -> 100.0 max
    # AWS gets +0 corroboration + +0 domain = 75.0
    assert score_fed > score_aws


def test_lifecycle_status_language(test_db_session: Session, client: TestClient):
    ed_date = date(2026, 9, 15)

    # 1. Preparing state
    ed_prep = DailyEdition(edition_date=ed_date, status="DRAFT", readiness="PREPARING", article_count=0, event_count=0)
    test_db_session.add(ed_prep)
    test_db_session.commit()

    res_prep = client.get(f"/edition/{ed_date}")
    assert res_prep.status_code == 200
    assert "MORNING EDITION PREPARING" in res_prep.text
    assert "Preparation in progress" in res_prep.text

    # 2. Ready but not published state
    ed_prep.status = "GENERATED"
    ed_prep.readiness = "READY"
    test_db_session.commit()

    res_ready = client.get(f"/edition/{ed_date}")
    assert res_ready.status_code == 200
    assert "READY FOR PUBLICATION" in res_ready.text
    assert "Ready for Publication" in res_ready.text
    assert "PUBLISHED" not in res_ready.text

    # 3. Published state
    ed_prep.status = "PUBLISHED"
    test_db_session.commit()

    res_pub = client.get(f"/edition/{ed_date}")
    assert res_pub.status_code == 200
    assert "PUBLISHED" in res_pub.text
    assert "Published 07:05 BST" in res_pub.text or "Published" in res_pub.text
