"""
Daily Edition Engine v1 Service
Deterministic, explainable, source-diverse, and category-diverse daily newspaper edition generator.
Snapshot Date: September 2026
"""

from datetime import datetime, date, timedelta, timezone
from difflib import SequenceMatcher
import math
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models import Article, ArticleAIOutput, Country, DailyEdition, EditionArticle, Source


# ==============================================================================
# ALGORITHM & SCORING CONFIGURATION
# ==============================================================================

ALGORITHM_VERSION = "edition_v1"

# Weight Distribution (sums to 1.0)
WEIGHT_RELEVANCE = 0.35
WEIGHT_IMPORTANCE = 0.30
WEIGHT_RECENCY = 0.15
WEIGHT_TRUST = 0.10
WEIGHT_SOURCE_DIVERSITY = 0.05
WEIGHT_GEO_DIVERSITY = 0.05

# Editorial Caps
DEFAULT_MAX_PER_SOURCE = 2
DEFAULT_MAX_CATEGORY_PCT = 0.30  # Max 30% of edition from any single category
DEFAULT_MAX_COUNTRY_PCT = 0.25   # Max 25% of edition from any single primary country

# Target Edition Size
TARGET_MIN_ARTICLES = 12
TARGET_MAX_ARTICLES = 25

# Trust Tier Score Mapping (normalized 0.0 - 1.0)
TRUST_TIER_SCORES: Dict[str, float] = {
    "institutional": 1.0,
    "primary": 1.0,
    "useful": 0.8,
    "specialist": 0.8,
    "open_source_signal": 0.6,
    "social_signal": 0.4,
    "state_affiliated": 0.2,
}

# Editorial Section Order & Mappings
SECTION_NAMES = [
    "Top Intelligence",
    "Strategic Briefs",
    "Geopolitics",
    "Markets & Economy",
    "Business",
    "AI & Technology",
    "Energy & Commodities",
    "Supply Chain & Trade",
    "Industry & Operations",
    "World Watch",
]

CATEGORY_TO_SECTION_MAP: Dict[str, str] = {
    "geopolitics": "Geopolitics",
    "politics": "Geopolitics",
    "markets & economy": "Markets & Economy",
    "markets": "Markets & Economy",
    "economy": "Markets & Economy",
    "business": "Business",
    "ai & technology": "AI & Technology",
    "ai": "AI & Technology",
    "tech": "AI & Technology",
    "technology": "AI & Technology",
    "energy": "Energy & Commodities",
    "oil": "Energy & Commodities",
    "commodities": "Energy & Commodities",
    "supply chain & trade": "Supply Chain & Trade",
    "trade": "Supply Chain & Trade",
    "supply chain": "Supply Chain & Trade",
    "industry & operations": "Industry & Operations",
    "industry": "Industry & Operations",
    "sustainability": "World Watch",
    "climate": "World Watch",
    "world": "World Watch",
    "international": "World Watch",
    "research": "Strategic Briefs",
}


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def resolve_edition_date(target_date: Optional[date | str] = None) -> date:
    """Resolve target date to a local date in APP_TIMEZONE (Europe/London)."""
    if isinstance(target_date, date):
        return target_date
    if isinstance(target_date, str) and target_date.strip():
        return date.fromisoformat(target_date.strip())

    settings = get_settings()
    try:
        tz = ZoneInfo(settings.app_timezone)
        return datetime.now(tz).date()
    except Exception:
        return datetime.now(timezone.utc).date()


def get_utc_window_for_date(target_date: date) -> Tuple[datetime, datetime]:
    """
    Convert local calendar date (00:00:00 to 23:59:59 Europe/London) to UTC boundaries.
    """
    settings = get_settings()
    try:
        tz = ZoneInfo(settings.app_timezone)
    except Exception:
        tz = timezone.utc

    start_local = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=tz)
    end_local = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, 999999, tzinfo=tz)

    s_utc = start_local.astimezone(timezone.utc)
    e_utc = end_local.astimezone(timezone.utc)
    return s_utc.replace(tzinfo=None), e_utc.replace(tzinfo=None)


def get_article_ai_output(art: Article) -> Optional[ArticleAIOutput]:
    """Extract latest successful ArticleAIOutput for an article."""
    if not hasattr(art, "ai_outputs") or not art.ai_outputs:
        return None
    success_outputs = [o for o in art.ai_outputs if o.status == "success"]
    if not success_outputs:
        return None
    return sorted(success_outputs, key=lambda x: x.created_at, reverse=True)[0]


def get_primary_country_code(art: Article) -> Optional[str]:
    """Extract primary country code from article or its source."""
    if art.countries and len(art.countries) > 0:
        return art.countries[0].code.upper()
    if art.source and art.source.country_code:
        return art.source.country_code.upper()
    return None


def calculate_title_similarity(t1: str, t2: str) -> float:
    """Calculate token Jaccard + SequenceMatcher similarity between two headlines."""
    if not t1 or not t2:
        return 0.0

    tokens1 = set(t1.lower().split())
    tokens2 = set(t2.lower().split())

    if not tokens1 or not tokens2:
        return 0.0

    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)
    jaccard = intersection / float(union) if union > 0 else 0.0

    seq_ratio = SequenceMatcher(None, t1.lower(), t2.lower()).ratio()
    return max(jaccard, seq_ratio)


# ==============================================================================
# SCORING & SELECTION REASON
# ==============================================================================

def score_article(
    article: Article,
    window_end_utc: datetime,
    selected_source_counts: Dict[int, int],
    selected_country_counts: Dict[str, int],
) -> Tuple[float, Dict[str, Any]]:
    """
    Calculate deterministic 0.0 - 100.0 edition score and structured component breakdown.
    """
    ai_output = get_article_ai_output(article)
    source = article.source

    # 1. Relevance (0.0 - 1.0)
    rel_score = float(ai_output.relevance_score) if (ai_output and ai_output.relevance_score is not None) else 70.0
    rel_comp = min(1.0, max(0.0, rel_score / 100.0))

    # 2. Importance (0.0 - 1.0)
    imp_score = float(ai_output.importance_score) if (ai_output and ai_output.importance_score is not None) else 50.0
    imp_comp = min(1.0, max(0.0, imp_score / 100.0))

    # 3. Recency Decay (0.0 - 1.0) over 36-hour window
    pub_time = article.published_at or article.collected_at or window_end_utc
    if pub_time.tzinfo is None:
        pub_time = pub_time.replace(tzinfo=timezone.utc)
    if window_end_utc.tzinfo is None:
        window_end_utc = window_end_utc.replace(tzinfo=timezone.utc)

    age_seconds = max(0.0, (window_end_utc - pub_time).total_seconds())
    age_hours = age_seconds / 3600.0
    rec_comp = max(0.0, 1.0 - (age_hours / 36.0))

    # 4. Source Trust Component (0.0 - 1.0)
    trust_tier = (source.trust_tier if source else "useful").lower()
    trust_comp = TRUST_TIER_SCORES.get(trust_tier, 0.5)

    # 5. Source Diversity Bonus (0.0 - 1.0)
    src_id = source.id if source else 0
    current_src_count = selected_source_counts.get(src_id, 0)
    src_div_comp = 1.0 if current_src_count == 0 else (0.5 if current_src_count == 1 else 0.0)

    # 6. Geographic Diversity Bonus (0.0 - 1.0)
    country_code = get_primary_country_code(article)
    current_geo_count = selected_country_counts.get(country_code, 0) if country_code else 0
    geo_div_comp = 1.0 if current_geo_count == 0 else (0.5 if current_geo_count == 1 else 0.2)

    total_score = (
        (WEIGHT_RELEVANCE * rel_comp)
        + (WEIGHT_IMPORTANCE * imp_comp)
        + (WEIGHT_RECENCY * rec_comp)
        + (WEIGHT_TRUST * trust_comp)
        + (WEIGHT_SOURCE_DIVERSITY * src_div_comp)
        + (WEIGHT_GEO_DIVERSITY * geo_div_comp)
    ) * 100.0

    breakdown = {
        "relevance_comp": round(rel_comp, 3),
        "importance_comp": round(imp_comp, 3),
        "recency_comp": round(rec_comp, 3),
        "trust_comp": round(trust_comp, 3),
        "src_div_comp": round(src_div_comp, 3),
        "geo_div_comp": round(geo_div_comp, 3),
        "raw_relevance": rel_score,
        "raw_importance": imp_score,
        "age_hours": round(age_hours, 1),
        "trust_tier": trust_tier,
    }

    return round(total_score, 2), breakdown


def build_selection_reason(article: Article, score: float, breakdown: Dict[str, Any]) -> str:
    """Generate concise human-readable selection explanation."""
    reasons = []

    rel = breakdown.get("raw_relevance", 70)
    imp = breakdown.get("raw_importance", 50)
    age = breakdown.get("age_hours", 0)
    tier = breakdown.get("trust_tier", "useful")

    if rel >= 85:
        reasons.append(f"High relevance ({int(rel)})")
    elif rel >= 70:
        reasons.append(f"Relevant ({int(rel)})")

    if imp >= 80:
        reasons.append(f"High importance ({int(imp)})")
    elif imp >= 65:
        reasons.append(f"Notable importance ({int(imp)})")

    if tier in ["institutional", "primary"]:
        reasons.append("Institutional source")
    elif tier in ["useful", "specialist"]:
        reasons.append("Specialist source")

    if age <= 6:
        reasons.append(f"Recent ({age:.1f}h ago)")
    elif age <= 18:
        reasons.append("Fresh story")

    if not reasons:
        reasons.append(f"Score {score:.1f}")

    return ", ".join(reasons)


# ==============================================================================
# MAIN GENERATION PIPELINE
# ==============================================================================

def generate_daily_edition(
    db: Session,
    edition_date: Optional[date | str] = None,
    force: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any] | DailyEdition:
    """
    Generate or return the deterministic Daily Edition for target_date.
    """
    target_d = resolve_edition_date(edition_date)
    start_utc, end_utc = get_utc_window_for_date(target_d)
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    # 1. Idempotency Check
    existing_edition = (
        db.query(DailyEdition)
        .filter(
            DailyEdition.edition_date == target_d,
            DailyEdition.algorithm_version == ALGORITHM_VERSION,
        )
        .first()
    )

    if existing_edition and not force and not dry_run:
        return existing_edition

    # 2. Fetch Base Candidate Pool in Window
    raw_articles = (
        db.query(Article)
        .options(
            joinedload(Article.source),
            joinedload(Article.ai_outputs),
            joinedload(Article.countries),
        )
        .filter(
            Article.published_at.is_not(None),
            Article.published_at >= start_utc,
            Article.published_at <= end_utc,
            Article.published_at <= now_utc,
        )
        .order_by(Article.published_at.desc())
        .all()
    )


    # If published_at window yields too few articles (< 10), fallback to collected_at in window
    if len(raw_articles) < 10:
        raw_articles = (
            db.query(Article)
            .options(
                joinedload(Article.source),
                joinedload(Article.ai_outputs),
                joinedload(Article.countries),
            )
            .filter(
                func.coalesce(Article.published_at, Article.collected_at) >= start_utc,
                func.coalesce(Article.published_at, Article.collected_at) <= end_utc,
                func.coalesce(Article.published_at, Article.collected_at) <= now_utc,
            )
            .order_by(func.coalesce(Article.published_at, Article.collected_at).desc())
            .all()
        )

    # 3. Eligibility Filtering & Excluded Reason Accounting
    eligible_articles: List[Article] = []
    excluded_counts = {
        "excluded_out_of_scope": 0,
        "excluded_null_relevance": 0,
        "excluded_ai_failed": 0,
        "excluded_invalid_category": 0,
        "excluded_inactive_source": 0,
        "total_excluded": 0,
    }

    for art in raw_articles:
        if art.source and not art.source.active:
            excluded_counts["excluded_inactive_source"] += 1
            continue

        ai_output = get_article_ai_output(art)
        if not ai_output:
            excluded_counts["excluded_ai_failed"] += 1
            continue

        if ai_output.is_relevant is False:
            excluded_counts["excluded_out_of_scope"] += 1
            continue

        if ai_output.is_relevant is None:
            excluded_counts["excluded_null_relevance"] += 1
            continue

        category = ai_output.primary_category or art.primary_category or (art.source.category if art.source else None)
        if not category:
            excluded_counts["excluded_invalid_category"] += 1
            continue

        eligible_articles.append(art)

    excluded_counts["total_excluded"] = sum(excluded_counts.values())

    # 4. Preliminary Scoring
    scored_candidates: List[Tuple[Article, float, Dict[str, Any]]] = []
    for art in eligible_articles:
        score, breakdown = score_article(art, end_utc, {}, {})
        scored_candidates.append((art, score, breakdown))

    # Sort descending by score
    scored_candidates.sort(key=lambda x: x[1], reverse=True)

    # 5. Non-AI Deduplication
    suppressed_duplicates = []
    deduped_candidates: List[Tuple[Article, float, Dict[str, Any]]] = []
    seen_urls = set()

    for item in scored_candidates:
        art, score, breakdown = item
        if art.canonical_url in seen_urls:
            suppressed_duplicates.append({
                "article_id": art.id,
                "title": art.title,
                "reason": "exact_url_duplicate",
            })
            continue

        # Check headline similarity against already kept candidates
        is_dup = False
        for kept_art, kept_score, _ in deduped_candidates:
            sim = calculate_title_similarity(art.title, kept_art.title)
            if sim >= 0.70:
                is_dup = True
                suppressed_duplicates.append({
                    "article_id": art.id,
                    "title": art.title,
                    "kept_article_id": kept_art.id,
                    "kept_title": kept_art.title,
                    "similarity": round(sim, 3),
                    "reason": "headline_similarity_duplicate",
                })
                break

        if not is_dup:
            seen_urls.add(art.canonical_url)
            deduped_candidates.append(item)

    # 6. Diversity Caps Enforcement
    selected_items: List[Tuple[Article, float, Dict[str, Any]]] = []
    source_counts: Dict[int, int] = {}
    category_counts: Dict[str, int] = {}
    country_counts: Dict[str, int] = {}

    max_per_source = DEFAULT_MAX_PER_SOURCE
    trigger_caps = []

    # First Pass: Strict caps
    for item in deduped_candidates:
        if len(selected_items) >= TARGET_MAX_ARTICLES:
            break

        art, score, breakdown = item
        src_id = art.source_id or 0
        ai_out = get_article_ai_output(art)
        cat = (ai_out.primary_category if ai_out else art.primary_category) or "World"
        country_code = get_primary_country_code(art) or "GLOBAL"

        # Source Cap Check
        if source_counts.get(src_id, 0) >= max_per_source:
            trigger_caps.append({"type": "source_cap", "article_id": art.id, "source_id": src_id})
            continue

        # Category Cap Check (Max 30% of target max, i.e. 7 articles)
        max_cat_count = math.ceil(TARGET_MAX_ARTICLES * DEFAULT_MAX_CATEGORY_PCT)
        if category_counts.get(cat, 0) >= max_cat_count:
            trigger_caps.append({"type": "category_cap", "article_id": art.id, "category": cat})
            continue

        # Country Cap Check (Max 25% of target max, i.e. 6 articles for non-global)
        if country_code != "GLOBAL":
            max_geo_count = math.ceil(TARGET_MAX_ARTICLES * DEFAULT_MAX_COUNTRY_PCT)
            if country_counts.get(country_code, 0) >= max_geo_count:
                trigger_caps.append({"type": "country_cap", "article_id": art.id, "country": country_code})
                continue

        # Accept article
        selected_items.append(item)
        source_counts[src_id] = source_counts.get(src_id, 0) + 1
        category_counts[cat] = category_counts.get(cat, 0) + 1
        country_counts[country_code] = country_counts.get(country_code, 0) + 1

    # Controlled Fallback if edition size is under target minimum (e.g. < 12)
    if len(selected_items) < TARGET_MIN_ARTICLES and len(deduped_candidates) > len(selected_items):
        for item in deduped_candidates:
            if len(selected_items) >= TARGET_MIN_ARTICLES:
                break
            if item not in selected_items:
                selected_items.append(item)
                trigger_caps.append({"type": "cap_relaxed_fallback", "article_id": item[0].id})

    # Re-calculate final scores with diversity context
    final_scored_items: List[Tuple[Article, float, Dict[str, Any]]] = []
    final_src_counts: Dict[int, int] = {}
    final_geo_counts: Dict[str, int] = {}

    for art, _, _ in selected_items:
        src_id = art.source_id or 0
        cc = get_primary_country_code(art) or "GLOBAL"
        final_src_counts[src_id] = final_src_counts.get(src_id, 0) + 1
        final_geo_counts[cc] = final_geo_counts.get(cc, 0) + 1

    for art, _, _ in selected_items:
        final_score, breakdown = score_article(art, end_utc, final_src_counts, final_geo_counts)
        final_scored_items.append((art, final_score, breakdown))

    final_scored_items.sort(key=lambda x: x[1], reverse=True)

    # 7. Select Lead Story
    lead_item = None
    for item in final_scored_items:
        art, score, breakdown = item
        # Favor articles with high importance and non-niche category
        if breakdown.get("raw_importance", 0) >= 50:
            lead_item = item
            break
    if not lead_item and final_scored_items:
        lead_item = final_scored_items[0]

    lead_article_id = lead_item[0].id if lead_item else None

    # 8. Section Assignment & Ordering
    assigned_sections: Dict[str, List[Dict[str, Any]]] = {sec: [] for sec in SECTION_NAMES}
    position = 1

    # Top Intelligence section starts with Lead Story
    if lead_item:
        lead_art, lead_score, lead_bk = lead_item
        reason = build_selection_reason(lead_art, lead_score, lead_bk) + " (Lead Story)"
        assigned_sections["Top Intelligence"].append({
            "article": lead_art,
            "article_id": lead_art.id,
            "score": lead_score,
            "reason": reason,
            "reason_json": lead_bk,
            "position": position,
        })
        position += 1

    for item in final_scored_items:
        art, score, bk = item
        if lead_item and art.id == lead_item[0].id:
            continue

        ai_out = get_article_ai_output(art)
        cat_raw = (ai_out.primary_category if ai_out else art.primary_category) or "world"
        target_section = CATEGORY_TO_SECTION_MAP.get(cat_raw.lower(), "World Watch")

        # Top 3 highest remaining scores go to Top Intelligence if space
        if len(assigned_sections["Top Intelligence"]) < 3 and score >= 75.0:
            target_section = "Top Intelligence"
        elif len(assigned_sections["Strategic Briefs"]) < 4 and bk.get("raw_importance", 0) >= 70:
            target_section = "Strategic Briefs"

        reason = build_selection_reason(art, score, bk)
        assigned_sections[target_section].append({
            "article": art,
            "article_id": art.id,
            "score": score,
            "reason": reason,
            "reason_json": bk,
            "position": position,
        })
        position += 1

    # Build Distributions for Diagnostic Metadata
    src_dist = {}
    cat_dist = {}
    country_dist = {}

    total_edition_articles = 0
    for sec, items in assigned_sections.items():
        total_edition_articles += len(items)
        for it in items:
            art = it["article"]
            src_name = art.source.name if art.source else "Unknown Source"
            ai_out = get_article_ai_output(art)
            cat_name = (ai_out.primary_category if ai_out else art.primary_category) or "World"
            c_code = get_primary_country_code(art) or "GLOBAL"

            src_dist[src_name] = src_dist.get(src_name, 0) + 1
            cat_dist[cat_name] = cat_dist.get(cat_name, 0) + 1
            country_dist[c_code] = country_dist.get(c_code, 0) + 1

    metadata_json = {
        "edition_date": str(target_d),
        "utc_window_start": start_utc.isoformat(),
        "utc_window_end": end_utc.isoformat(),
        "eligible_count": len(eligible_articles),
        "excluded_counts": excluded_counts,
        "suppressed_duplicates_count": len(suppressed_duplicates),
        "suppressed_duplicates": suppressed_duplicates,
        "trigger_caps": trigger_caps,
        "selected_article_count": total_edition_articles,
        "lead_article_id": lead_article_id,
        "section_counts": {sec: len(items) for sec, items in assigned_sections.items() if items},
        "source_distribution": src_dist,
        "category_distribution": cat_dist,
        "country_distribution": country_dist,
        "top_ranked_scores": [
            {
                "article_id": it[0].id,
                "title": it[0].title,
                "score": it[1],
                "reason": build_selection_reason(it[0], it[1], it[2]),
            }
            for it in final_scored_items[:10]
        ],
    }

    # 9. Dry Run Output
    if dry_run:
        return {
            "status": "dry_run",
            "edition_date": str(target_d),
            "algorithm_version": ALGORITHM_VERSION,
            "lead_article": lead_item[0].title if lead_item else None,
            "article_count": total_edition_articles,
            "metadata_json": metadata_json,
            "assigned_sections": {
                sec: [
                    {
                        "article_id": it["article_id"],
                        "title": it["article"].title,
                        "score": it["score"],
                        "reason": it["reason"],
                    }
                    for it in items
                ]
                for sec, items in assigned_sections.items()
                if items
            },
        }

    # 10. Persist Edition to Database
    if existing_edition and force:
        db.query(EditionArticle).filter(EditionArticle.edition_id == existing_edition.id).delete()
        db.delete(existing_edition)
        db.flush()

    new_edition = DailyEdition(
        edition_date=target_d,
        algorithm_version=ALGORITHM_VERSION,
        status="published",
        generated_at=now_utc,
        lead_article_id=lead_article_id,
        article_count=total_edition_articles,
        metadata_json=metadata_json,
    )
    db.add(new_edition)
    db.flush()

    for sec_name, items in assigned_sections.items():
        for item in items:
            ea = EditionArticle(
                edition_id=new_edition.id,
                article_id=item["article_id"],
                section=sec_name,
                position=item["position"],
                edition_score=item["score"],
                selection_reason=item["reason"],
                selection_reason_json=item["reason_json"],
                created_at=now_utc,
            )
            db.add(ea)

    db.commit()
    db.refresh(new_edition)

    return new_edition
