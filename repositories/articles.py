from datetime import date, datetime, timedelta, timezone
import math
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, String
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models import Article, ArticleCountry, ArticleAIOutput, Country, DailyEdition, EditionArticle, Source
from services.query_expansion import expand_query, ExpandedQueryResult


def _valid_published_filter():
    """Rule 6: Never display articles whose published_at > current time."""
    now = datetime.now(timezone.utc)
    return or_(Article.published_at.is_(None), Article.published_at <= now)


def count_total_articles(db: Session) -> int:
    """Count all stored articles in the archive (SELECT COUNT(*) FROM articles)."""
    return db.query(Article).count()



def count_articles_today(db: Session, tz_name: str | None = None) -> int:
    """
    Count articles whose published_at falls within the current local calendar day in APP_TIMEZONE (Europe/London).
    today_start <= published_at < tomorrow_start AND published_at <= NOW()
    """
    if tz_name is None:
        tz_name = get_settings().app_timezone

    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc

    now_local = datetime.now(tz)
    today_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start_local = today_start_local + timedelta(days=1)

    today_start = today_start_local.astimezone(timezone.utc)
    tomorrow_start = tomorrow_start_local.astimezone(timezone.utc)
    now_utc = datetime.now(timezone.utc)

    return (
        db.query(Article)
        .filter(
            Article.published_at.is_not(None),
            Article.published_at >= today_start,
            Article.published_at < tomorrow_start,
            Article.published_at <= now_utc,
        )
        .count()
    )


def count_active_sources(db: Session) -> int:
    """Count active sources where active == True."""
    return db.query(Source).filter(Source.active == True).count()  # noqa: E712


def get_archive_stats(db: Session) -> dict[str, int]:
    """Calculate metric stats: Total Archive, Today's Articles, Active Sources."""
    return {
        "total_archive": count_total_articles(db),
        "today_articles": count_articles_today(db),
        "active_sources": count_active_sources(db),
    }


def get_categories(db: Session) -> list[str]:
    """Get list of active source categories."""
    results = (
        db.query(Source.category)
        .filter(Source.active == True, Source.category.is_not(None))  # noqa: E712
        .distinct()
        .all()
    )
    categories = [r[0] for r in results if r[0]]
    # Ensure default core categories appear in clean order
    default_order = ["AI", "Markets", "Geopolitics"]
    ordered = [c for c in default_order if c in categories]
    for c in sorted(categories):
        if c not in ordered:
            ordered.append(c)
    return ordered


def apply_editorial_diversity(
    articles: list[Article],
    max_per_source: int = 2,
    max_items: int = 50,
) -> list[Article]:
    """
    Deterministic editorial selection to prevent single-source domination.
    Limits articles per source to max_per_source where alternative sources exist,
    favoring recency and diversity across sources and regions.
    """
    if not articles:
        return []

    source_counts: dict[int, int] = {}
    selected: list[Article] = []
    overflow: list[Article] = []

    for art in articles:
        source_id = art.source_id or 0
        current_count = source_counts.get(source_id, 0)
        if current_count < max_per_source:
            selected.append(art)
            source_counts[source_id] = current_count + 1
        else:
            overflow.append(art)

    if len(selected) < max_items and overflow:
        remaining_needed = max_items - len(selected)
        selected.extend(overflow[:remaining_needed])

    return selected[:max_items]


def is_article_out_of_scope(art: Article) -> bool:
    """Returns True if the article has been evaluated by AI as out of scope (is_relevant == False)."""
    if not hasattr(art, "ai_outputs") or not art.ai_outputs:
        return False
    latest_output = sorted(art.ai_outputs, key=lambda x: x.created_at, reverse=True)[0]
    return latest_output.is_relevant is False


def get_article_ai_output(art: Article) -> Any:
    """Returns the latest ArticleAIOutput record for an article, if any."""
    if not hasattr(art, "ai_outputs") or not art.ai_outputs:
        return None
    return sorted(art.ai_outputs, key=lambda x: x.created_at, reverse=True)[0]


def get_today_ai_context_stats(db: Session, tz_name: str | None = None) -> dict[str, Any]:
    """
    Aggregates live AI analysis statistics from ArticleAIOutput table for context sidebar widgets,
    strictly filtered to today's local calendar day in APP_TIMEZONE (Europe/London).
    """
    from app.entity_metadata import get_country_info
    from app.intelligence_groups import INTELLIGENCE_GROUPS

    if tz_name is None:
        tz_name = get_settings().app_timezone or "Europe/London"

    try:
        local_tz = ZoneInfo(tz_name)
    except Exception:
        local_tz = timezone.utc

    now_local = datetime.now(local_tz)
    today_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start_local = today_start_local + timedelta(days=1)

    today_start_utc = today_start_local.astimezone(timezone.utc)
    tomorrow_start_utc = tomorrow_start_local.astimezone(timezone.utc)

    # 1. News Today Counts
    articles_collected_today = (
        db.query(Article)
        .filter(
            Article.collected_at >= today_start_utc,
            Article.collected_at < tomorrow_start_utc,
        )
        .count()
    )

    articles_published_today = (
        db.query(Article)
        .filter(
            Article.published_at.is_not(None),
            Article.published_at >= today_start_utc,
            Article.published_at < tomorrow_start_utc,
        )
        .count()
    )

    # 2. Today's Article Population (Europe/London calendar day)
    today_article_filter = or_(
        and_(Article.collected_at >= today_start_utc, Article.collected_at < tomorrow_start_utc),
        and_(Article.published_at.is_not(None), Article.published_at >= today_start_utc, Article.published_at < tomorrow_start_utc),
    )

    today_articles = (
        db.query(Article)
        .options(joinedload(Article.ai_outputs))
        .filter(today_article_filter)
        .all()
    )

    relevant_count = 0
    out_of_scope_count = 0
    ai_processing_failed = 0
    awaiting_ai_processing = 0
    relevant_outputs = []

    failed_statuses = {"failed", "invalid_json", "timeout", "unavailable", "temporary_error"}

    for art in today_articles:
        outs = art.ai_outputs or []
        if not outs:
            awaiting_ai_processing += 1
            continue

        latest_out = sorted(
            outs,
            key=lambda x: x.created_at or x.processed_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )[0]
        st = latest_out.status

        if st == "success":
            if latest_out.is_relevant is False:
                out_of_scope_count += 1
            else:
                relevant_count += 1
                if latest_out.output_json:
                    relevant_outputs.append(latest_out)
        elif st == "out_of_scope":
            out_of_scope_count += 1
        elif st in failed_statuses:
            ai_processing_failed += 1
        else:
            awaiting_ai_processing += 1

    ai_processed = relevant_count + out_of_scope_count
    total_eligible = ai_processed + awaiting_ai_processing + ai_processing_failed
    processing_coverage = (ai_processed / total_eligible * 100.0) if total_eligible > 0 else 0.0

    topic_counts: dict[str, int] = {}
    country_counts: dict[str, int] = {}

    for out in relevant_outputs:
        if isinstance(out.output_json, dict):
            for t in out.output_json.get("topics", []):
                if isinstance(t, str) and t.strip():
                    t_clean = t.strip().lstrip("#").strip()
                    if t_clean:
                        if t_clean[0].islower():
                            t_clean = t_clean.capitalize()
                        topic_counts[t_clean] = topic_counts.get(t_clean, 0) + 1
            for c in out.output_json.get("countries", []):
                if isinstance(c, str) and c.strip():
                    c_clean = c.strip()
                    country_counts[c_clean] = country_counts.get(c_clean, 0) + 1

    sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:6]
    top_topics_formatted = [{"name": t[0], "count": t[1]} for t in sorted_topics]

    # Map country counts to group counts
    group_counts: dict[str, int] = {}
    for c_raw, count in country_counts.items():
        info = get_country_info(c_raw)
        c_code = info["code"]
        if c_code:
            for g_key, g_data in INTELLIGENCE_GROUPS.items():
                if g_key != "world" and c_code in g_data.get("country_codes", []):
                    group_counts[g_data["name"]] = group_counts.get(g_data["name"], 0) + count

    sorted_groups = sorted(group_counts.items(), key=lambda x: x[1], reverse=True)[:2]
    sorted_countries = sorted(country_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    global_focus_items = []
    for g_name, g_count in sorted_groups:
        global_focus_items.append({
            "type": "group",
            "name": g_name,
            "icon": "🌐",
            "count": g_count,
        })

    for c_raw, count in sorted_countries:
        info = get_country_info(c_raw)
        global_focus_items.append({
            "type": "country",
            "name": info["name"],
            "code": info["code"],
            "flag": info["flag"],
            "count": count,
        })

    top_countries_formatted = []
    for c_raw, count in sorted_countries:
        info = get_country_info(c_raw)
        top_countries_formatted.append({
            "code": info["code"],
            "name": info["name"],
            "flag": info["flag"],
            "count": count,
        })

    return {
        "articles_collected_today": articles_collected_today,
        "articles_published_today": articles_published_today,
        "ai_processed": ai_processed,
        "relevant_today": relevant_count,
        "out_of_scope_today": out_of_scope_count,
        "awaiting_ai_processing": awaiting_ai_processing,
        "ai_processing_failed": ai_processing_failed,
        "processing_coverage": round(processing_coverage, 1),
        # Aliases for backward compatibility
        "total_processed": ai_processed,
        "unprocessed_or_failed": awaiting_ai_processing,
        "success_rate": round(processing_coverage, 1),
        "top_topics": top_topics_formatted,
        "top_countries": top_countries_formatted,
        "global_focus_items": global_focus_items,
    }


def get_recent_articles(
    db: Session, category: str | None = None, limit: int = 50, mode: str = "balanced", curated_only: bool = False
) -> list[Article]:
    """Fetch recent articles optionally filtered by category, excluding future-dated articles."""
    query = (
        db.query(Article)
        .options(joinedload(Article.source), joinedload(Article.ai_outputs))
        .filter(_valid_published_filter())
    )

    if category:
        query = query.join(Article.source).filter(
            func.lower(Source.category) == category.lower()
        )

    # Order by published_at DESC (fallback to collected_at DESC)
    query = query.order_by(
        func.coalesce(Article.published_at, Article.collected_at).desc()
    )

    raw_articles = query.limit(limit * 4).all()

    mode_clean = (mode or "balanced").lower()

    if mode_clean == "chronological":
        if curated_only:
            raw_articles = [a for a in raw_articles if not is_article_out_of_scope(a)]
        return raw_articles[:limit]

    if mode_clean == "ai_curated":
        curated_articles = []
        for a in raw_articles:
            ai_outs = getattr(a, "ai_outputs", [])
            succ_relevant = False
            if ai_outs:
                for ai in ai_outs:
                    if ai.status == "success" and ai.is_relevant is True:
                        succ_relevant = True
                        break
            if succ_relevant and not is_article_out_of_scope(a):
                curated_articles.append(a)

        return apply_editorial_diversity(curated_articles, max_per_source=2, max_items=limit)

    # mode == "balanced" (or default fallback): AI-independent feed with source diversity & scope filtering
    balanced_articles = [a for a in raw_articles if not is_article_out_of_scope(a)]
    return apply_editorial_diversity(balanced_articles, max_per_source=2, max_items=limit)


def get_top_story(db: Session, category: str | None = None) -> Article | None:
    """Fetch the single top lead article for the masthead hero section."""
    query = (
        db.query(Article)
        .options(joinedload(Article.source), joinedload(Article.ai_outputs))
        .filter(_valid_published_filter())
    )
    if category:
        query = query.join(Article.source).filter(
            func.lower(Source.category) == category.lower()
        )
    candidates = query.order_by(func.coalesce(Article.published_at, Article.collected_at).desc()).limit(20).all()
    for cand in candidates:
        if not is_article_out_of_scope(cand):
            return cand
    return candidates[0] if candidates else None


def get_articles_by_sections(db: Session, category: str | None = None, curated_only: bool = True) -> dict[str, list[Article]]:
    """Group recent articles into newspaper section buckets."""
    recent = get_recent_articles(db, category=category, limit=120, mode="balanced", curated_only=curated_only)
    sections = {
        "Top Story": [],
        "World": [],
        "Geopolitics": [],
        "Business": [],
        "Markets & Economy": [],
        "AI & Technology": [],
        "Industry & Operations": [],
        "Supply Chain & Trade": [],
        "Energy": [],
        "Sustainability": [],
        "Research": [],
        "Latest Updates": [],
    }

    if not recent:
        return sections

    filtered_recent = [a for a in recent if not (curated_only and is_article_out_of_scope(a))]
    if not filtered_recent:
        return sections

    # Lead article is top story
    sections["Top Story"] = [filtered_recent[0]]
    remaining = filtered_recent[1:]

    category_mapping = {
        "world": "World",
        "international": "World",
        "geopolitics": "Geopolitics",
        "politics": "Geopolitics",
        "business": "Business",
        "markets & economy": "Markets & Economy",
        "markets": "Markets & Economy",
        "economy": "Markets & Economy",
        "finance": "Markets & Economy",
        "ai & technology": "AI & Technology",
        "ai": "AI & Technology",
        "tech": "AI & Technology",
        "technology": "AI & Technology",
        "industry & operations": "Industry & Operations",
        "industry": "Industry & Operations",
        "operations": "Industry & Operations",
        "mining": "Industry & Operations",
        "manufacturing": "Industry & Operations",
        "construction": "Industry & Operations",
        "supply chain & trade": "Supply Chain & Trade",
        "trade": "Supply Chain & Trade",
        "supply chain": "Supply Chain & Trade",
        "energy": "Energy",
        "oil": "Energy",
        "sustainability": "Sustainability",
        "climate": "Sustainability",
        "research": "Research",
        "science": "Research",
    }

    for art in remaining:
        ai_out = get_article_ai_output(art)
        cat_raw = ""
        if ai_out and ai_out.is_relevant and ai_out.primary_category:
            cat_raw = ai_out.primary_category.lower()
        elif art.source and art.source.category:
            cat_raw = art.source.category.lower()

        matched = False
        for key, section_name in category_mapping.items():
            if key == cat_raw or key in cat_raw:
                if len(sections[section_name]) < 6:
                    sections[section_name].append(art)
                    matched = True
                    break

        if not matched and len(sections["Latest Updates"]) < 8:
            sections["Latest Updates"].append(art)

    # Apply per-section diversity filter
    for s_name in sections:
        if s_name != "Top Story" and sections[s_name]:
            sections[s_name] = apply_editorial_diversity(sections[s_name], max_per_source=2, max_items=6)

    return sections


def get_categories_summary(db: Session) -> list[dict[str, Any]]:
    """Get all categories with active status and total stored article count."""
    categories = get_categories(db)
    summary = []
    for cat in categories:
        count = (
            db.query(Article)
            .join(Article.source)
            .filter(_valid_published_filter())
            .filter(func.lower(Source.category) == cat.lower())
            .count()
        )
        sample = get_recent_articles(db, category=cat, limit=3)
        summary.append(
            {
                "name": cat,
                "count": count,
                "sample_articles": sample,
            }
        )
    return summary


def get_sources_summary(
    db: Session, family: str | None = None, category: str | None = None
) -> list[dict[str, Any]]:
    """Get all sources with metadata, active status, and stored article count, optionally filtered by family or category."""
    query = db.query(Source).order_by(Source.name.asc())

    if family and family.lower() != "all":
        query = query.filter(func.lower(Source.source_family) == family.lower())

    if category and category.lower() != "all":
        query = query.filter(func.lower(Source.category) == category.lower())

    sources = query.all()
    summary = []
    for s in sources:
        count = db.query(Article).filter(Article.source_id == s.id).count()
        summary.append(
            {
                "id": s.id,
                "name": s.name,
                "source_type": s.source_type,
                "source_family": s.source_family,
                "category": s.category,
                "trust_tier": s.trust_tier,
                "active": s.active,
                "website_url": s.website_url,
                "feed_url": s.feed_url,
                "country_code": s.country_code,
                "article_count": count,
            }
        )
    return summary


def search_articles_v1(
    db: Session,
    query: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    categories: Optional[List[str]] = None,
    countries: Optional[List[str]] = None,
    sources: Optional[List[str]] = None,
    min_importance: Optional[int] = None,
    min_relevance: Optional[int] = None,
    relevant_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    page: int = 1,
    candidate_limit: Optional[int] = None,
    enable_query_expansion: bool = False,
    enable_query_aware_reranking: bool = False,
) -> Dict[str, Any]:
    """
    Historical Search Query Service v1 with PostgreSQL Full-Text Search,
    server-side filtering, match explanation extraction, and hybrid ranking.
    """
    clean_q = (query or "").strip()
    page = max(1, page)
    if offset > 0 and page == 1:
        page = (offset // limit) + 1

    if not clean_q and not categories and not countries and not sources and min_importance is None and min_relevance is None and not date_from and not date_to:
        return {
            "articles": [],
            "matched_explanations": {},
            "scores": {},
            "total": 0,
            "page": page,
            "page_size": limit,
            "total_pages": 1,
            "query": query,
            "has_prev": False,
            "has_next": False,
            "filters": {},
        }

    # Base Query
    base_query = (
        db.query(Article)
        .options(
            joinedload(Article.source),
            joinedload(Article.ai_outputs),
            joinedload(Article.countries),
        )
        .filter(_valid_published_filter())
    )

    # 1. Relevant Only Filter
    if relevant_only:
        base_query = base_query.filter(
            Article.ai_outputs.any(ArticleAIOutput.is_relevant == True)  # noqa: E712
        )

    # 2. Date Boundaries
    tz_name = get_settings().app_timezone or "Europe/London"
    try:
        local_tz = ZoneInfo(tz_name)
    except Exception:
        local_tz = timezone.utc

    if date_from:
        start_local = datetime(date_from.year, date_from.month, date_from.day, 0, 0, 0, tzinfo=local_tz)
        start_utc = start_local.astimezone(timezone.utc)
        base_query = base_query.filter(
            func.coalesce(Article.published_at, Article.collected_at) >= start_utc
        )

    if date_to:
        end_local = datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59, 999999, tzinfo=local_tz)
        end_utc = end_local.astimezone(timezone.utc)
        base_query = base_query.filter(
            func.coalesce(Article.published_at, Article.collected_at) <= end_utc
        )

    # 3. Category Filter
    if categories:
        cat_cleans = [c.lower().strip() for c in categories if c and c.strip()]
        if cat_cleans:
            base_query = base_query.filter(
                or_(
                    func.lower(Article.primary_category).in_(cat_cleans),
                    Article.ai_outputs.any(func.lower(ArticleAIOutput.primary_category).in_(cat_cleans)),
                    Article.source.has(func.lower(Source.category).in_(cat_cleans)),
                )
            )

    # 4. Country Filter
    if countries:
        c_cleans = [c.upper().strip() for c in countries if c and c.strip()]
        if c_cleans:
            base_query = base_query.filter(
                or_(
                    Article.countries.any(Country.code.in_(c_cleans)),
                    Article.source.has(Source.country_code.in_(c_cleans)),
                )
            )

    # 5. Source Filter
    if sources:
        src_cleans = [s.strip() for s in sources if s and s.strip()]
        if src_cleans:
            int_srcs = [int(s) for s in src_cleans if s.isdigit()]
            str_srcs = [s.lower() for s in src_cleans if not s.isdigit()]
            src_conditions = []
            if int_srcs:
                src_conditions.append(Article.source_id.in_(int_srcs))
            if str_srcs:
                src_conditions.append(Article.source.has(func.lower(Source.name).in_(str_srcs)))
            if src_conditions:
                base_query = base_query.filter(or_(*src_conditions))

    # 6. Minimum Importance & Relevance Thresholds
    if min_importance is not None:
        base_query = base_query.filter(
            Article.ai_outputs.any(ArticleAIOutput.importance_score >= min_importance)
        )
    if min_relevance is not None:
        base_query = base_query.filter(
            Article.ai_outputs.any(ArticleAIOutput.relevance_score >= min_relevance)
        )

    # 7. Text Search Filter & Matching
    is_postgres = False
    try:
        bind = db.get_bind()
        if bind and bind.dialect.name == "postgresql":
            is_postgres = True
    except Exception:
        pass

    cand_limit = candidate_limit if candidate_limit is not None else (limit * 4)
    raw_candidates: List[Article] = []

    exp_res: Optional[ExpandedQueryResult] = None
    expansion_meta: Dict[str, Any] = {
        "enabled": enable_query_expansion,
        "original_tokens": [],
        "expanded_tokens": [],
        "triggered_rules": [],
        "fts_expression": "",
        "candidate_match_origins": {},
    }

    if enable_query_expansion and clean_q:
        exp_res = expand_query(clean_q)
        expansion_meta["original_tokens"] = exp_res.original_tokens
        expansion_meta["expanded_tokens"] = exp_res.expanded_tokens
        expansion_meta["triggered_rules"] = exp_res.triggered_rules
        expansion_meta["fts_expression"] = exp_res.fts_expression

    if clean_q:
        stop_words = {
            "what", "did", "say", "about", "the", "a", "an", "is", "are", "in", "on", "of", "for", "to", "how", "why", "who", "where", "which", "with",
            "today", "yesterday", "this", "week", "month", "past", "last", "days", "happened", "latest", "news", "show", "tell", "me"
        }
        raw_tokens = [t.lower().strip() for t in clean_q.split() if t.strip()]
        tokens = [t for t in raw_tokens if t not in stop_words and len(t) > 1]
        expanded_tokens = exp_res.expanded_tokens if (exp_res and exp_res.expanded_tokens) else []
        
        if tokens or expanded_tokens:
            token_conditions = []
            for tok in tokens:
                like_pattern = f"%{tok}%"
                token_conditions.append(
                    or_(
                        func.lower(Article.title).like(like_pattern),
                        func.lower(Article.raw_summary).like(like_pattern),
                        Article.ai_outputs.any(func.lower(ArticleAIOutput.summary).like(like_pattern)),
                        Article.ai_outputs.any(func.lower(func.cast(ArticleAIOutput.output_json, String)).like(like_pattern)),
                        func.lower(Article.primary_category).like(like_pattern),
                        Article.source.has(func.lower(Source.name).like(like_pattern)),
                    )
                )

            exp_conditions = []
            for exp_tok in expanded_tokens:
                like_pattern = f"%{exp_tok}%"
                exp_conditions.append(
                    or_(
                        func.lower(Article.title).like(like_pattern),
                        func.lower(Article.raw_summary).like(like_pattern),
                        Article.ai_outputs.any(func.lower(ArticleAIOutput.summary).like(like_pattern)),
                        Article.ai_outputs.any(func.lower(func.cast(ArticleAIOutput.output_json, String)).like(like_pattern)),
                    )
                )

            sql_search_cond = or_(*token_conditions) if token_conditions else None
            exp_sql_cond = or_(*exp_conditions) if exp_conditions else None
            search_conds = [c for c in [sql_search_cond, exp_sql_cond] if c is not None]
            combined_sql_cond = or_(*search_conds) if search_conds else None

            if is_postgres:
                fts_conds = [
                    func.to_tsvector("english", func.coalesce(Article.title, "") + " " + func.coalesce(Article.raw_summary, "")).op("@@")(func.websearch_to_tsquery("english", clean_q)),
                    Article.ai_outputs.any(func.to_tsvector("english", func.coalesce(ArticleAIOutput.summary, "")).op("@@")(func.websearch_to_tsquery("english", clean_q))),
                ]
                if sql_search_cond is not None:
                    fts_conds.append(sql_search_cond)

                if exp_res and exp_res.expanded_tokens:
                    exp_tsquery_str = " | ".join([t.replace(" ", " & ") if " " in t else t for t in exp_res.expanded_tokens])
                    try:
                        fts_conds.append(func.to_tsvector("english", func.coalesce(Article.title, "") + " " + func.coalesce(Article.raw_summary, "")).op("@@")(func.to_tsquery("english", exp_tsquery_str)))
                        fts_conds.append(Article.ai_outputs.any(func.to_tsvector("english", func.coalesce(ArticleAIOutput.summary, "")).op("@@")(func.to_tsquery("english", exp_tsquery_str))))
                    except Exception:
                        pass
                if exp_sql_cond is not None:
                    fts_conds.append(exp_sql_cond)

                fts_query = base_query.filter(or_(*fts_conds))
                raw_candidates = fts_query.limit(cand_limit).all()
            else:
                raw_candidates = base_query.filter(combined_sql_cond).limit(cand_limit).all() if combined_sql_cond is not None else base_query.limit(cand_limit).all()
        else:
            raw_candidates = base_query.order_by(func.coalesce(Article.published_at, Article.collected_at).desc()).limit(cand_limit).all()
    else:
        raw_candidates = base_query.order_by(func.coalesce(Article.published_at, Article.collected_at).desc()).limit(cand_limit).all()

    # 8. Hybrid Ranking & Match Explanation Extraction
    now_utc = datetime.now(timezone.utc)
    scored_items: List[Tuple[Article, float, List[str]]] = []

    query_terms = [t.lower().strip() for t in clean_q.split() if len(t.strip()) > 2]
    expanded_terms = [t.lower().strip() for t in (exp_res.expanded_tokens if exp_res else []) if len(t.strip()) > 2]

    for art in raw_candidates:
        ai_out = get_article_ai_output(art)
        matched_tags: List[str] = []

        title_lower = (art.title or "").lower()
        summary_lower = (art.raw_summary or "").lower()
        ai_summary_lower = (ai_out.summary or "").lower() if ai_out else ""

        # Determine Match Origin
        orig_match = False
        exp_match = False

        if clean_q:
            if clean_q.lower() in title_lower or any(t in title_lower or t in summary_lower or t in ai_summary_lower for t in query_terms):
                orig_match = True

        if expanded_terms:
            if any(t in title_lower or t in summary_lower or t in ai_summary_lower for t in expanded_terms):
                exp_match = True

        if orig_match and exp_match:
            match_origin = "BOTH"
        elif orig_match:
            match_origin = "ORIGINAL_QUERY"
        elif exp_match:
            match_origin = "EXPANSION"
        else:
            match_origin = "ORIGINAL_QUERY"

        expansion_meta["candidate_match_origins"][art.id] = match_origin

        fts_rank = 0.0
        if clean_q:
            if clean_q.lower() in title_lower:
                fts_rank += 50.0
                matched_tags.append(art.title[:30] + "...")
            elif any(t in title_lower for t in query_terms):
                fts_rank += 30.0

            if any(t in summary_lower or t in ai_summary_lower for t in query_terms):
                fts_rank += 15.0

        if enable_query_aware_reranking:
            # 1. Multi-keyword overlap boost (original terms)
            orig_matched_count = sum(1 for t in query_terms if t in title_lower or t in summary_lower or t in ai_summary_lower)
            fts_rank += (orig_matched_count * 8.0)
            if query_terms and all(t in title_lower for t in query_terms):
                fts_rank += 15.0

            # 2. Expansion overlap boost
            if expanded_terms:
                exp_matched_count = sum(1 for t in expanded_terms if t in title_lower or t in summary_lower or t in ai_summary_lower)
                fts_rank += (exp_matched_count * 4.0)

        elif enable_query_expansion and expanded_terms:
            if any(t in title_lower for t in expanded_terms):
                fts_rank += 10.0
                matched_tags.append("(exp) " + art.title[:25] + "...")
            if any(t in summary_lower or t in ai_summary_lower for t in expanded_terms):
                fts_rank += 5.0

        # Topic & Entity Match Bonuses
        if ai_out and isinstance(ai_out.output_json, dict):
            topics = ai_out.output_json.get("topics", [])
            entities = ai_out.output_json.get("entities", [])

            for top in topics:
                if isinstance(top, str):
                    top_clean = top.strip().lstrip("#")
                    if any(t in top_clean.lower() for t in query_terms) or clean_q.lower() in top_clean.lower():
                        fts_rank += 15.0
                        if top_clean not in matched_tags:
                            matched_tags.append(top_clean)
                    elif (enable_query_expansion or enable_query_aware_reranking) and any(t in top_clean.lower() for t in expanded_terms):
                        fts_rank += 5.0

            for ent in entities:
                ent_name = ent.get("name") if isinstance(ent, dict) else str(ent)
                if isinstance(ent_name, str):
                    if any(t in ent_name.lower() for t in query_terms) or clean_q.lower() in ent_name.lower():
                        fts_rank += 15.0
                        if ent_name not in matched_tags:
                            matched_tags.append(ent_name)
                    elif (enable_query_expansion or enable_query_aware_reranking) and any(t in ent_name.lower() for t in expanded_terms):
                        fts_rank += 5.0

        # AI Relevance & Importance
        rel_score = float(ai_out.relevance_score) if (ai_out and ai_out.relevance_score is not None) else 70.0
        imp_score = float(ai_out.importance_score) if (ai_out and ai_out.importance_score is not None) else 50.0

        if enable_query_aware_reranking:
            rel_comp = rel_score * 0.25
            imp_comp = imp_score * 0.20
        else:
            rel_comp = rel_score * 0.15
            imp_comp = imp_score * 0.15

        # Source Trust Boost
        trust_boost = 0.0
        if enable_query_aware_reranking and art.source:
            tier = getattr(art.source, "trust_tier", "")
            if tier == "institutional":
                trust_boost = 5.0
            elif tier == "primary":
                trust_boost = 3.0
            elif tier == "secondary":
                trust_boost = 1.0

        # Recency Decay
        pub_time = art.published_at or art.collected_at or now_utc
        if pub_time.tzinfo is None:
            pub_time = pub_time.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (now_utc - pub_time).total_seconds() / 86400.0)

        if enable_query_aware_reranking and not date_from and not date_to:
            recency_comp = max(0.0, 1.0 - (age_days / 365.0)) * 5.0
        else:
            recency_comp = max(0.0, 1.0 - (age_days / 180.0)) * 5.0

        # Base default match score if no query specified
        base_match = fts_rank if clean_q else 40.0

        total_rank_score = base_match + rel_comp + imp_comp + recency_comp + trust_boost

        # Deduplicate matched_tags
        clean_matched_tags = list(dict.fromkeys(matched_tags))[:5]
        scored_items.append((art, round(total_rank_score, 2), clean_matched_tags))

    # Sort descending by rank score
    scored_items.sort(key=lambda x: x[1], reverse=True)

    total_items = len(scored_items)
    total_pages = math.ceil(total_items / limit) if total_items > 0 else 1
    if page > total_pages and total_pages > 0:
        page = total_pages

    page_offset = (page - 1) * limit
    paged_items = scored_items[page_offset : page_offset + limit]

    final_articles = [it[0] for it in paged_items]
    matched_explanations = {it[0].id: it[2] for it in paged_items}
    scores = {it[0].id: it[1] for it in paged_items}

    return {
        "articles": final_articles,
        "matched_explanations": matched_explanations,
        "scores": scores,
        "total": total_items,
        "limit": limit,
        "offset": page_offset,
        "page": page,
        "page_size": limit,
        "total_pages": total_pages,
        "query": query,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "filters": {
            "date_from": str(date_from) if date_from else None,
            "date_to": str(date_to) if date_to else None,
            "categories": categories,
            "countries": countries,
            "sources": sources,
            "min_importance": min_importance,
            "min_relevance": min_relevance,
            "relevant_only": relevant_only,
        },
        "query_expansion_meta": expansion_meta,
    }


def search_articles(
    db: Session, query_str: str, page: int = 1, page_size: int = 25
) -> dict[str, Any]:
    """Legacy backward-compatible wrapper calling search_articles_v1."""
    return search_articles_v1(db, query=query_str, page=page, limit=page_size)


def get_articles_by_source(
    db: Session, source_identifier: Any, page: int = 1, page_size: int = 25
) -> dict[str, Any]:
    """Fetch paginated articles for a specific source by ID or name."""
    source = None
    if isinstance(source_identifier, int) or (isinstance(source_identifier, str) and source_identifier.isdigit()):
        source = db.query(Source).filter(Source.id == int(source_identifier)).first()
    elif isinstance(source_identifier, str):
        source = db.query(Source).filter(func.lower(Source.name) == source_identifier.lower()).first()

    if not source:
        return {
            "source": None,
            "articles": [],
            "total": 0,
            "page": 1,
            "page_size": page_size,
            "total_pages": 1,
            "has_prev": False,
            "has_next": False,
        }

    if page < 1:
        page = 1

    query = (
        db.query(Article)
        .options(joinedload(Article.source))
        .filter(_valid_published_filter())
        .filter(Article.source_id == source.id)
    )

    total_items = query.count()
    total_pages = math.ceil(total_items / page_size) if total_items > 0 else 1

    if page > total_pages and total_pages > 0:
        page = total_pages

    offset = (page - 1) * page_size
    items = (
        query.order_by(func.coalesce(Article.published_at, Article.collected_at).desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return {
        "source": source,
        "articles": items,
        "total": total_items,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
    }


def get_paginated_articles(
    db: Session,
    page: int = 1,
    page_size: int = 25,
    category: str | None = None,
    date_str: str | None = None,
    source_id: int | None = None,
) -> dict[str, Any]:
    """Fetch paginated articles with optional category, date (YYYY-MM-DD), and source filtering."""
    if page < 1:
        page = 1

    query = (
        db.query(Article)
        .options(joinedload(Article.source))
        .filter(_valid_published_filter())
    )

    if category:
        query = query.join(Article.source).filter(
            func.lower(Source.category) == category.lower()
        )

    if source_id:
        query = query.filter(Article.source_id == source_id)

    if date_str:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            tz = ZoneInfo(get_settings().app_timezone)
            start_local = datetime(dt.year, dt.month, dt.day, 0, 0, 0, tzinfo=tz)
            end_local = start_local + timedelta(days=1)
            start_utc = start_local.astimezone(timezone.utc)
            end_utc = end_local.astimezone(timezone.utc)
            now_utc = datetime.now(timezone.utc)
            query = query.filter(
                Article.published_at.is_not(None),
                Article.published_at >= start_utc,
                Article.published_at < end_utc,
                Article.published_at <= now_utc,
            )
        except ValueError:
            pass

    total_items = query.count()
    total_pages = math.ceil(total_items / page_size) if total_items > 0 else 1

    if page > total_pages and total_pages > 0:
        page = total_pages

    offset = (page - 1) * page_size
    items = (
        query.order_by(
            func.coalesce(Article.published_at, Article.collected_at).desc()
        )
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return {
        "articles": items,
        "total": total_items,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
    }


def get_all_countries(db: Session) -> list[Country]:


    """Get all normalized countries ordered by name."""
    return db.query(Country).order_by(Country.name.asc()).all()


def get_todays_country_counts(db: Session, tz_name: str | None = None) -> dict[str, int]:
    """Count today's articles per country code for map overlay."""
    if tz_name is None:
        tz_name = get_settings().app_timezone

    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc

    now_local = datetime.now(tz)
    today_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start_local = today_start_local + timedelta(days=1)

    today_start = today_start_local.astimezone(timezone.utc)
    tomorrow_start = tomorrow_start_local.astimezone(timezone.utc)
    now_utc = datetime.now(timezone.utc)

    # Base query for today's articles
    today_articles = (
        db.query(Article)
        .options(joinedload(Article.countries), joinedload(Article.source))
        .filter(
            Article.published_at.is_not(None),
            Article.published_at >= today_start,
            Article.published_at < tomorrow_start,
            Article.published_at <= now_utc,
        )
        .all()
    )

    counts: dict[str, int] = {}
    for art in today_articles:
        codes = set()
        for c in art.countries:
            codes.add(c.code)
        if art.source and art.source.country_code:
            codes.add(art.source.country_code)

        for code in codes:
            counts[code] = counts.get(code, 0) + 1

    return counts


def get_todays_world_articles(
    db: Session,
    country_code: str | None = None,
    is_brics: bool = False,
    lens: str | None = None,
    category: str | None = None,
    tz_name: str | None = None,
) -> list[Article]:
    """Fetch today's articles for the interactive world map filtered by country, lens group, or category."""
    if tz_name is None:
        tz_name = get_settings().app_timezone

    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc

    now_local = datetime.now(tz)
    today_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start_local = today_start_local + timedelta(days=1)

    today_start = today_start_local.astimezone(timezone.utc)
    tomorrow_start = tomorrow_start_local.astimezone(timezone.utc)
    now_utc = datetime.now(timezone.utc)

    query = (
        db.query(Article)
        .options(joinedload(Article.source), joinedload(Article.countries))
        .filter(
            Article.published_at.is_not(None),
            Article.published_at >= today_start,
            Article.published_at < tomorrow_start,
            Article.published_at <= now_utc,
        )
    )

    if category:
        query = query.join(Article.source).filter(
            func.lower(Source.category) == category.lower()
        )

    active_lens_key = (lens or "").lower().strip()
    if not active_lens_key and is_brics:
        active_lens_key = "brics"

    if active_lens_key and active_lens_key != "world":
        from app.intelligence_groups import get_group_country_codes
        group_codes = get_group_country_codes(active_lens_key)
        if group_codes:
            query = query.filter(
                or_(
                    Article.countries.any(Country.code.in_(group_codes)),
                    Article.source.has(Source.country_code.in_(group_codes)),
                )
            )

    if country_code:
        cc_clean = country_code.upper()
        query = query.filter(
            or_(
                Article.countries.any(Country.code == cc_clean),
                Article.source.has(Source.country_code == cc_clean),
            )
        )

    return (
        query.order_by(
            func.coalesce(Article.published_at, Article.collected_at).desc()
        )
        .distinct()
        .all()
    )


def get_persisted_daily_edition(db: Session, target_date: Any = None) -> Optional[DailyEdition]:
    """Fetch persisted DailyEdition for a given date in APP_TIMEZONE."""
    from services.edition import ALGORITHM_VERSION, resolve_edition_date
    resolved_d = resolve_edition_date(target_date)

    return (
        db.query(DailyEdition)
        .options(
            joinedload(DailyEdition.lead_article),
            joinedload(DailyEdition.edition_articles).joinedload(EditionArticle.article).joinedload(Article.source),
            joinedload(DailyEdition.edition_articles).joinedload(EditionArticle.article).joinedload(Article.ai_outputs),
            joinedload(DailyEdition.edition_articles).joinedload(EditionArticle.article).joinedload(Article.countries),
        )
        .filter(
            DailyEdition.edition_date == resolved_d,
            DailyEdition.algorithm_version == ALGORITHM_VERSION,
        )
        .first()
    )


def get_edition_articles_by_sections(db: Session, edition: DailyEdition, category: Optional[str] = None) -> dict[str, list[Article]]:
    """Group articles from a persisted DailyEdition into editorial section buckets."""
    sections = {
        "Top Intelligence": [],
        "Strategic Briefs": [],
        "Geopolitics": [],
        "Markets & Economy": [],
        "Business": [],
        "AI & Technology": [],
        "Energy & Commodities": [],
        "Supply Chain & Trade": [],
        "Industry & Operations": [],
        "World Watch": [],
    }

    if not edition or not edition.edition_articles:
        return sections

    # Sort edition articles by position
    sorted_eas = sorted(edition.edition_articles, key=lambda x: x.position)

    cat_clean = category.lower().strip() if category else None

    for ea in sorted_eas:
        art = ea.article
        if not art:
            continue

        if cat_clean:
            ai_out = get_article_ai_output(art)
            art_cat = (ai_out.primary_category if ai_out else art.primary_category) or ""
            if cat_clean not in art_cat.lower():
                continue

        sec_name = ea.section if ea.section in sections else "World Watch"
        sections[sec_name].append(art)

    return sections


def get_edition_top_story(db: Session, edition: DailyEdition) -> Optional[Article]:
    """Fetch lead story from persisted DailyEdition."""
    if not edition:
        return None
    if edition.lead_article:
        return edition.lead_article
    if edition.edition_articles and len(edition.edition_articles) > 0:
        sorted_eas = sorted(edition.edition_articles, key=lambda x: x.position)
        return sorted_eas[0].article
    return None




