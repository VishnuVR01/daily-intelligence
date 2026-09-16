"""
Daily Edition Selection Engine (Sprint 3 Stage 3C).
Deterministic editorial selection converting eligible AI-reviewed articles into Event Clusters,
ranking events deterministically, enforcing section and source caps, assigning roles (LEAD, TOP, SECTION),
and snapshotting Daily Editions.
"""
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
import pytz
from sqlalchemy.orm import Session, joinedload

from app.models import Article, ArticleAIOutput, DailyEdition, EditionEvent, EventCluster, EventClusterArticle, Source
from repositories.articles import is_article_out_of_scope
from services.editorial.clustering import (
    cluster_articles,
    compare_articles_similarity,
    EventClusterResult,
)
from services.editorial.scorer import calculate_article_editorial_score, ArticleEditorialScoreResult

# Canonical Sections
CANONICAL_SECTIONS = ["WORLD", "ECONOMY", "TECH", "ENERGY", "TRADE", "BUSINESS", "SUSTAINABILITY"]

# Section Mapping Table
CATEGORY_TO_SECTION = {
    "ai & technology": "TECH",
    "ai": "TECH",
    "technology": "TECH",
    "tech": "TECH",
    "software": "TECH",
    "semiconductors": "TECH",
    "markets & economy": "ECONOMY",
    "economy": "ECONOMY",
    "macro & fx": "ECONOMY",
    "sovereign yields": "ECONOMY",
    "monetary policy": "ECONOMY",
    "markets": "ECONOMY",
    "commodities": "BUSINESS",
    "precious metals": "BUSINESS",
    "energy": "ENERGY",
    "oil & gas": "ENERGY",
    "clean energy": "ENERGY",
    "power & utilities": "ENERGY",
    "renewable energy": "ENERGY",
    "trade": "TRADE",
    "supply chain": "TRADE",
    "business": "BUSINESS",
    "industry & operations": "BUSINESS",
    "industry": "BUSINESS",
    "corporate": "BUSINESS",
    "biotech": "BUSINESS",
    "agtech": "BUSINESS",
    "sustainability": "SUSTAINABILITY",
    "climate": "SUSTAINABILITY",
    "esg": "SUSTAINABILITY",
    "world": "WORLD",
    "geopolitics": "WORLD",
    "general": "WORLD",
}


def calculate_lead_significance_score(cl: EventClusterResult, section: str, ai_outputs_map: Optional[Dict[int, ArticleAIOutput]] = None) -> float:
    """
    Computes explainable Lead Significance Score (0-100+) used strictly for Lead Story role assignment among selected edition events.
    Does NOT modify general Event Score or section membership ordering.
    """
    score = cl.cluster_score

    # 1. Multi-source corroboration boost
    if cl.distinct_source_count >= 2:
        score += 10.0

    # 2. Macro/Geopolitics/Policy domain boost vs single-source corporate post
    if section in ("ECONOMY", "WORLD", "ENERGY", "TRADE"):
        score += 10.0
    elif cl.primary_article and cl.primary_article.source:
        stype = cl.primary_article.source.source_type
        if stype in ("CENTRAL_BANK", "GOVERNMENT"):
            score += 15.0

    # 3. High importance score boost
    ai_out = (ai_outputs_map.get(cl.primary_article_id) if ai_outputs_map else None)
    imp = ai_out.importance_score if (ai_out and ai_out.importance_score) else 50
    if imp >= 80:
        score += 5.0

    return round(score, 1)


def map_category_to_section(category: Optional[str]) -> str:
    """Maps article or cluster category deterministically to a canonical section."""
    if not category:
        return "WORLD"
    cat_lower = category.strip().lower()
    return CATEGORY_TO_SECTION.get(cat_lower, "WORLD")


@dataclass
class EventSelectionResult:
    cluster_id: str
    canonical_title: str
    primary_article_id: int
    primary_article: Article
    supporting_articles: List[Article]
    section: str
    role: str  # LEAD, TOP, SECTION
    position: int
    event_score: float
    article_score: float
    distinct_source_count: int
    article_count: int
    why_selected: List[str]
    selection_reason_json: Dict[str, Any]
    raw_cluster_result: Optional[EventClusterResult] = None


@dataclass
class EditionAuditResult:
    edition_date: str
    status: str
    readiness: str
    candidate_articles_count: int
    candidate_events_count: int
    selected_events_count: int
    lead_story_title: Optional[str]
    rejected_counts_by_reason: Dict[str, int]
    selected_events: List[EventSelectionResult]
    audit_json: Dict[str, Any]


def get_london_date_window(target_date: date) -> Tuple[datetime, datetime]:
    """
    Computes candidate time window for Europe/London edition_date.
    Includes 48-hour candidate window up to 23:59:59 London time on target_date.
    """
    london_tz = pytz.timezone("Europe/London")
    # End of target day in London
    day_end_local = london_tz.localize(datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59))
    # 48h candidate window back from end of target date
    day_start_local = day_end_local - timedelta(hours=48)
    
    start_utc = day_start_local.astimezone(timezone.utc)
    end_utc = day_end_local.astimezone(timezone.utc)
    return start_utc, end_utc


def fetch_eligible_candidates(
    db: Session,
    start_utc: datetime,
    end_utc: datetime,
    now: Optional[datetime] = None,
) -> Tuple[List[Article], Dict[int, ArticleAIOutput]]:
    """
    Fetches articles eligible for Daily Edition consideration:
    - Published or collected within [start_utc, end_utc]
    - Reject future timestamps (> now)
    - Enabled source
    - Valid title and canonical_url
    - Successful AI processing (status == "success") AND is_relevant == True
    - Not out of scope
    """
    if now is None:
        now = datetime.now(timezone.utc)

    query = (
        db.query(Article)
        .options(joinedload(Article.source), joinedload(Article.ai_outputs))
        .filter(Article.title.isnot(None), Article.title != "")
        .filter(Article.canonical_url.isnot(None), Article.canonical_url != "")
    )

    all_articles = query.all()
    eligible_articles = []
    ai_outputs_map = {}

    for a in all_articles:
        # Source check
        if a.source and not a.source.active:
            continue

        # Timestamp check
        pub_at = a.published_at or a.collected_at
        if not pub_at:
            continue
        if pub_at.tzinfo is None:
            pub_at = pub_at.replace(tzinfo=timezone.utc)

        if pub_at > now or pub_at < start_utc or pub_at > end_utc:
            continue

        # AI output check: require status == "success" AND is_relevant == True
        ai_outs = getattr(a, "ai_outputs", [])
        valid_ai = None
        if ai_outs:
            for ai in ai_outs:
                if ai.status == "success" and ai.is_relevant is True:
                    valid_ai = ai
                    break

        if not valid_ai:
            continue

        # Out-of-scope check
        if is_article_out_of_scope(a):
            continue

        eligible_articles.append(a)
        ai_outputs_map[a.id] = valid_ai

    return eligible_articles, ai_outputs_map


def generate_daily_edition_selection(
    db: Session,
    target_date: date,
    min_quality_threshold: float = 50.0,
    lead_quality_threshold: float = 70.0,
    max_edition_size: int = 20,
    min_publishable_size: int = 10,
    max_per_source: int = 2,
    max_section_share: float = 0.30,
    now: Optional[datetime] = None,
) -> EditionAuditResult:
    """
    Runs the Stage 3C Editorial Selection Engine for a given Europe/London edition_date.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    start_utc, end_utc = get_london_date_window(target_date)

    # 1. Candidate Fetching
    eligible_articles, ai_outputs_map = fetch_eligible_candidates(db, start_utc, end_utc, now=now)

    # 2. Event Clustering v1 (Stage 3B Frozen)
    event_clusters = cluster_articles(
        articles=eligible_articles,
        ai_outputs_map=ai_outputs_map,
        high_confidence_threshold=0.68,
        now=now,
    )

    # 3. Candidate Event Sorting & Ranking
    # Sort deterministically by: Event Score DESC, Primary Importance DESC, Latest Time DESC, Cluster ID ASC
    def cluster_sort_key(cl: EventClusterResult):
        ai_out = ai_outputs_map.get(cl.primary_article_id)
        imp = ai_out.importance_score if (ai_out and ai_out.importance_score) else 50
        time_ts = cl.latest_article_at.timestamp() if cl.latest_article_at else 0
        return (cl.cluster_score, imp, time_ts, -int(cl.primary_article_id))

    event_clusters.sort(key=cluster_sort_key, reverse=True)

    # 4. Constrained Selection Loop
    selected_clusters: List[Tuple[EventClusterResult, str]] = []  # (cluster, section)
    source_counts: Dict[int, int] = {}
    section_counts: Dict[str, int] = {}
    max_section_cap = max(1, int(max_edition_size * max_section_share))  # Max 6 per section for 20 size

    rejection_reasons = {
        "QUALITY_THRESHOLD": 0,
        "SOURCE_CAP": 0,
        "SECTION_CAP": 0,
        "DUPLICATE_SAFETY": 0,
    }

    selected_primaries: List[Article] = []

    for cl in event_clusters:
        if len(selected_clusters) >= max_edition_size:
            break

        # Quality Check
        if cl.cluster_score < min_quality_threshold:
            rejection_reasons["QUALITY_THRESHOLD"] += 1
            continue

        # Primary Article Source Cap Check
        prim_source_id = cl.primary_article.source_id
        if prim_source_id and source_counts.get(prim_source_id, 0) >= max_per_source:
            rejection_reasons["SOURCE_CAP"] += 1
            continue

        # Section Mapping & Section Cap Check
        section = map_category_to_section(cl.category)
        if section_counts.get(section, 0) >= max_section_cap:
            rejection_reasons["SECTION_CAP"] += 1
            continue

        # Secondary Duplicate Safety Check (Section 28)
        is_dup_safety_rejected = False
        if cl.article_count == 1:
            for sel_prim in selected_primaries:
                comp = compare_articles_similarity(cl.primary_article, sel_prim)
                if comp.similarity_score >= 0.55:
                    is_dup_safety_rejected = True
                    break
        if is_dup_safety_rejected:
            rejection_reasons["DUPLICATE_SAFETY"] += 1
            continue

        # Accept Event Cluster
        selected_clusters.append((cl, section))
        selected_primaries.append(cl.primary_article)
        if prim_source_id:
            source_counts[prim_source_id] = source_counts.get(prim_source_id, 0) + 1
        section_counts[section] = section_counts.get(section, 0) + 1


    # 5. Role Assignment (LEAD, TOP, SECTION)
    selected_event_results: List[EventSelectionResult] = []
    lead_story_title = None

    if selected_clusters:
        # Determine Lead Story by Lead Significance Score among qualified candidates (cluster_score >= lead_quality_threshold)
        lead_candidate_idx = None
        best_lead_sig = -1.0

        for idx, (cl, sec) in enumerate(selected_clusters):
            if cl.cluster_score >= lead_quality_threshold:
                sig_score = calculate_lead_significance_score(cl, sec, ai_outputs_map)
                if sig_score > best_lead_sig:
                    best_lead_sig = sig_score
                    lead_candidate_idx = idx

        if lead_candidate_idx is None and selected_clusters and selected_clusters[0][0].cluster_score >= lead_quality_threshold:
            lead_candidate_idx = 0

        has_lead = (lead_candidate_idx is not None)
        if has_lead:
            lead_story_title = selected_clusters[lead_candidate_idx][0].canonical_title

        position = 1
        for idx, (cl, sec) in enumerate(selected_clusters):
            if has_lead and idx == lead_candidate_idx:
                role = "LEAD"
            elif (idx < 4 and has_lead) or (idx < 5 and not has_lead):
                role = "TOP"
            else:
                role = "SECTION"

            primary_score = cl.metadata_json.get("primary_editorial_score", cl.cluster_score)

            why_sel = [
                f"Selected as {role} Story in section {sec}.",
                f"Event Score {cl.cluster_score:.1f} >= Min Quality {min_quality_threshold:.1f}.",
                f"Covered by {cl.distinct_source_count} distinct source(s).",
                f"Primary source '{cl.primary_article.source.name if cl.primary_article.source else 'Unknown'}' under source cap ({source_counts.get(cl.primary_article.source_id, 1)}/{max_per_source}).",
                f"Section '{sec}' under section cap ({section_counts.get(sec, 1)}/{max_section_cap}).",
            ]

            reason_json = {
                "role": role,
                "section": sec,
                "position": position,
                "event_score": cl.cluster_score,
                "primary_article_score": primary_score,
                "distinct_source_count": cl.distinct_source_count,
                "supporting_articles_count": len(cl.supporting_articles),
                "why_selected": why_sel,
            }

            sel_res = EventSelectionResult(
                cluster_id=cl.cluster_id,
                canonical_title=cl.canonical_title,
                primary_article_id=cl.primary_article_id,
                primary_article=cl.primary_article,
                supporting_articles=cl.supporting_articles,
                section=sec,
                role=role,
                position=position,
                event_score=cl.cluster_score,
                article_score=primary_score,
                distinct_source_count=cl.distinct_source_count,
                article_count=cl.article_count,
                why_selected=why_sel,
                selection_reason_json=reason_json,
                raw_cluster_result=cl,
            )
            selected_event_results.append(sel_res)
            position += 1

    # 6. Readiness Gate
    readiness = "READY" if len(selected_event_results) >= min_publishable_size else "PREPARING"

    audit_meta = {
        "edition_date": str(target_date),
        "readiness": readiness,
        "candidate_articles_count": len(eligible_articles),
        "candidate_events_count": len(event_clusters),
        "selected_events_count": len(selected_event_results),
        "lead_story": lead_story_title,
        "rejected_reasons": rejection_reasons,
        "section_counts": section_counts,
        "source_counts": {str(k): v for k, v in source_counts.items()},
    }

    return EditionAuditResult(
        edition_date=str(target_date),
        status="DRAFT",
        readiness=readiness,
        candidate_articles_count=len(eligible_articles),
        candidate_events_count=len(event_clusters),
        selected_events_count=len(selected_event_results),
        lead_story_title=lead_story_title,
        rejected_counts_by_reason=rejection_reasons,
        selected_events=selected_event_results,
        audit_json=audit_meta,
    )


def save_daily_edition_selection(
    db: Session,
    edition_audit: EditionAuditResult,
    target_date: date,
    status: str = "GENERATED",
) -> DailyEdition:
    """
    Persists EditionAuditResult deterministically into daily_editions and edition_events tables.
    Snapshot immutability: Updates DRAFT/GENERATED edition; raises ValueError if PUBLISHED.
    """
    from services.editorial.clustering import save_event_clusters

    # First persist selected event clusters so foreign keys exist
    raw_clusters = [sel.raw_cluster_result for sel in edition_audit.selected_events if sel.raw_cluster_result]
    if raw_clusters:
        save_event_clusters(db, raw_clusters)

    existing_edition = (
        db.query(DailyEdition)
        .filter(DailyEdition.edition_date == target_date, DailyEdition.algorithm_version == "edition_v1")
        .first()
    )

    if existing_edition:
        if existing_edition.status == "PUBLISHED":
            raise ValueError(f"Edition for date {target_date} is PUBLISHED and cannot be regenerated or overwritten.")
        edition = existing_edition
        edition.status = status
        edition.readiness = edition_audit.readiness
        edition.generated_at = datetime.now(timezone.utc)
        edition.audit_json = edition_audit.audit_json
        # Clear existing events
        db.query(EditionEvent).filter(EditionEvent.edition_id == edition.id).delete(synchronize_session=False)
    else:
        edition = DailyEdition(
            edition_date=target_date,
            algorithm_version="edition_v1",
            status=status,
            readiness=edition_audit.readiness,
            generated_at=datetime.now(timezone.utc),
            event_count=edition_audit.selected_events_count,
            audit_json=edition_audit.audit_json,
        )
        db.add(edition)
        db.flush()

    lead_event_id = None
    lead_article_id = None

    for sel_event in edition_audit.selected_events:
        if sel_event.role == "LEAD":
            lead_event_id = sel_event.cluster_id
            lead_article_id = sel_event.primary_article_id

        ee = EditionEvent(
            edition_id=edition.id,
            event_cluster_id=sel_event.cluster_id,
            section=sel_event.section,
            role=sel_event.role,
            position=sel_event.position,
            event_score=sel_event.event_score,
            selection_reason="\n".join(sel_event.why_selected),
            selection_reason_json=sel_event.selection_reason_json,
        )
        db.add(ee)

    edition.lead_event_cluster_id = lead_event_id
    edition.lead_article_id = lead_article_id
    edition.event_count = len(edition_audit.selected_events)
    edition.article_count = sum(e.article_count for e in edition_audit.selected_events)

    db.commit()
    db.refresh(edition)
    return edition
