"""
Unit tests for Sprint 3 Stage 3D — Editorial Prose & Synthesis Engine.
Tests EvidencePack bounding, validator rules, synthesis fallbacks, failure isolation, snapshot persistence, and published immutability.
"""
from datetime import date, datetime, timezone, timedelta
import pytest
from app.models import (
    Article,
    Source,
    ArticleAIOutput,
    DailyEdition,
    EditionEvent,
    EventEditorialProse,
    EditionBrief,
)
from services.editorial.selection import (
    EventSelectionResult,
    EditionAuditResult,
)
from services.editorial.evidence import build_evidence_pack, format_temporal_label
from services.editorial.validator import validate_event_editorial_output, ValidationResult
from services.editorial.synthesis import (
    synthesize_event_editorial,
    synthesize_edition_brief_and_themes,
    save_editorial_synthesis,
)


@pytest.fixture
def sample_source(test_db_session):
    src = Source(
        name="Financial Times",
        website_url="https://ft.com",
        source_type="NEWS_OUTLET",
        trust_tier="tier1_direct",
    )
    test_db_session.add(src)
    test_db_session.commit()
    test_db_session.refresh(src)
    return src


@pytest.fixture
def sample_article(test_db_session, sample_source):
    art = Article(
        title="ECB Cuts Benchmark Interest Rate by 25 Basis Points to 3.25%",
        canonical_url="https://ft.com/ecb-rate-cut-25bps",
        source_id=sample_source.id,
        published_at=datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc),
        raw_summary="The European Central Bank announced a 25 basis point reduction in key policy rates.",
    )
    test_db_session.add(art)
    test_db_session.commit()
    test_db_session.refresh(art)

    ai_out = ArticleAIOutput(
        article_id=art.id,
        status="success",
        summary="The European Central Bank announced a 25 basis point reduction in key policy rates.",
        importance_score=85,
        relevance_score=90,
    )
    test_db_session.add(ai_out)
    test_db_session.commit()
    return art


def test_format_temporal_label():
    ed_date = date(2026, 9, 15)
    dt_same = datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc)
    dt_overnight = datetime(2026, 9, 15, 3, 0, tzinfo=timezone.utc)
    dt_prev = datetime(2026, 9, 14, 18, 0, tzinfo=timezone.utc)

    assert format_temporal_label(dt_same, ed_date) == "on 15 September 2026"
    assert format_temporal_label(dt_overnight, ed_date) == "overnight on 15 September 2026"
    assert format_temporal_label(dt_prev, ed_date) == "on 14 September 2026"


def make_test_selection(
    cluster_id: str,
    title: str,
    primary_art: Article,
    supp_arts: list = None,
    section: str = "CENTRAL_BANKS",
    role: str = "LEAD_STORY",
    score: float = 90.0,
) -> EventSelectionResult:
    supp = supp_arts or []
    return EventSelectionResult(
        cluster_id=cluster_id,
        canonical_title=title,
        primary_article_id=primary_art.id,
        primary_article=primary_art,
        supporting_articles=supp,
        section=section,
        role=role,
        position=1,
        event_score=score,
        article_score=score,
        distinct_source_count=1,
        article_count=1 + len(supp),
        why_selected=["High editorial score"],
        selection_reason_json={"reason": "test"},
    )


def test_evidence_pack_bounding(test_db_session, sample_article, sample_source):
    supp1 = Article(
        title="Lagarde Cautions Inflation Risks Remain in Eurozone Economy",
        canonical_url="https://ft.com/lagarde-cautions",
        source_id=sample_source.id,
        published_at=datetime(2026, 9, 15, 15, 0, tzinfo=timezone.utc),
    )
    supp2 = Article(
        title="Euro Trades Lower Following Unexpected ECB Monetary Easing Decision",
        canonical_url="https://ft.com/euro-drops",
        source_id=sample_source.id,
        published_at=datetime(2026, 9, 15, 15, 30, tzinfo=timezone.utc),
    )
    supp3 = Article(
        title="German Bund Yields Drop to Three Month Lows",
        canonical_url="https://ft.com/bund-yields",
        source_id=sample_source.id,
        published_at=datetime(2026, 9, 15, 16, 0, tzinfo=timezone.utc),
    )
    supp4 = Article(
        title="Excess Fifth Supporting Article That Should Be Truncated",
        canonical_url="https://ft.com/excess-art",
        source_id=sample_source.id,
        published_at=datetime(2026, 9, 15, 16, 30, tzinfo=timezone.utc),
    )
    test_db_session.add_all([supp1, supp2, supp3, supp4])
    test_db_session.commit()

    sel_event = make_test_selection(
        cluster_id="evt_test_001",
        title="ECB Cuts Interest Rates by 25 Bps",
        primary_art=sample_article,
        supp_arts=[supp1, supp2, supp3, supp4],
        score=92.5,
    )

    pack = build_evidence_pack(sel_event, edition_date=date(2026, 9, 15), max_supporting=3)

    assert pack.event_cluster_id == "evt_test_001"
    assert pack.primary_article.id == sample_article.id
    assert len(pack.supporting_articles) == 3
    assert len(pack.evidence_article_ids) == 4
    assert sample_article.id in pack.evidence_article_ids


def test_validator_rules(test_db_session, sample_article):
    sel_event = make_test_selection(
        cluster_id="evt_val_001",
        title="ECB Cuts Interest Rates by 25 Bps",
        primary_art=sample_article,
        score=90.0,
    )
    pack = build_evidence_pack(sel_event, edition_date=date(2026, 9, 15))

    # 1. Valid output
    valid_out = {
        "event_cluster_id": "evt_val_001",
        "headline": "European Central Bank Cuts Benchmark Rates by 25 Basis Points to 3.25 Percent",
        "summary": "The European Central Bank announced a 25 basis point reduction in key policy rates.",
        "why_it_matters": "Marks a shift in Eurozone monetary policy trajectory.",
        "watch_next": None,
        "evidence_article_ids": [sample_article.id],
    }
    res = validate_event_editorial_output(valid_out, pack)
    assert res.is_valid is True

    # 2. Headline too short
    invalid_headline = dict(valid_out, headline="ECB Rate Cut")
    res_short = validate_event_editorial_output(invalid_headline, pack)
    assert res_short.is_valid is False
    assert any("Headline length" in e for e in res_short.errors)

    # 3. Unfounded numeric token
    invalid_num = dict(valid_out, summary="The ECB cut rates by 99% yesterday.")
    res_num = validate_event_editorial_output(invalid_num, pack)
    assert res_num.is_valid is False
    assert any("Numeric token" in e for e in res_num.errors)

    # 4. Unfounded causal claim
    invalid_causal = dict(valid_out, summary="The ECB decision caused a global market panic.")
    res_causal = validate_event_editorial_output(invalid_causal, pack)
    assert res_causal.is_valid is False
    assert any("Causal trigger phrase" in e for e in res_causal.errors)


def test_synthesis_fallback_when_ollama_offline(test_db_session, sample_article):
    sel_event = make_test_selection(
        cluster_id="evt_off_001",
        title="ECB Cuts Benchmark Interest Rate",
        primary_art=sample_article,
        score=88.0,
    )

    # use_ollama=False simulates offline / timeout
    res = synthesize_event_editorial(db=test_db_session, event_selection=sel_event, edition_date=date(2026, 9, 15), use_ollama=False)

    assert res.status == "FALLBACK"
    assert res.headline == sel_event.canonical_title
    assert sample_article.id in res.evidence_article_ids


def test_snapshot_persistence_and_immutability(test_db_session, sample_article):
    ed_date = date(2026, 9, 15)

    # Create EventCluster first
    from app.models import EventCluster
    ec = EventCluster(
        cluster_id="evt_pers_001",
        canonical_title="ECB Rate Cut",
        category="CENTRAL_BANKS",
        article_count=1,
    )
    test_db_session.add(ec)
    test_db_session.commit()

    # 1. Create DailyEdition in DRAFT status
    edition = DailyEdition(
        edition_date=ed_date,
        status="DRAFT",
    )
    test_db_session.add(edition)
    test_db_session.commit()

    ee = EditionEvent(
        edition_id=edition.id,
        event_cluster_id="evt_pers_001",
        section="CENTRAL_BANKS",
        role="LEAD_STORY",
        position=1,
        event_score=90.0,
    )
    test_db_session.add(ee)
    test_db_session.commit()

    sel_pers = make_test_selection(
        cluster_id="evt_pers_001",
        title="ECB Rate Cut",
        primary_art=sample_article,
        score=90.0,
    )
    prose = synthesize_event_editorial(db=test_db_session, event_selection=sel_pers, edition_date=ed_date, use_ollama=False)

    audit_res = EditionAuditResult(
        edition_date=ed_date,
        status="DRAFT",
        readiness="READY",
        candidate_articles_count=1,
        candidate_events_count=1,
        selected_events_count=1,
        lead_story_title="ECB Rate Cut",
        rejected_counts_by_reason={},
        selected_events=[sel_pers],
        audit_json={"section_counts": {"CENTRAL_BANKS": 1}},
    )

    brief_res = synthesize_edition_brief_and_themes(db=test_db_session, edition_audit=audit_res, event_prose_results=[prose], use_ollama=False)

    # Persist synthesis
    save_editorial_synthesis(db=test_db_session, edition=edition, event_prose_results=[prose], edition_brief_result=brief_res)

    # Check persistence
    db_prose = test_db_session.query(EventEditorialProse).filter(EventEditorialProse.edition_event_id == ee.id).first()
    assert db_prose is not None
    assert db_prose.headline == "ECB Rate Cut"
    assert db_prose.status == "FALLBACK"

    db_brief = test_db_session.query(EditionBrief).filter(EditionBrief.edition_id == edition.id).first()
    assert db_brief is not None
    assert "Daily Edition presents 1 key macro developments" in db_brief.brief_text

    # 2. Immutability guard test
    edition.status = "PUBLISHED"
    test_db_session.commit()

    with pytest.raises(ValueError, match="PUBLISHED and cannot be overwritten"):
        save_editorial_synthesis(db=test_db_session, edition=edition, event_prose_results=[prose], edition_brief_result=brief_res)
