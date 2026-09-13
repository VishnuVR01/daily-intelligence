from datetime import datetime, timedelta, timezone
import math
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models import Article, ArticleCountry, ArticleAIOutput, Country, Source


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


def get_today_ai_context_stats(db: Session) -> dict[str, Any]:
    """
    Aggregates live AI analysis statistics from ArticleAIOutput table for context sidebar widgets.
    """
    from app.entity_metadata import get_country_info
    from app.intelligence_groups import INTELLIGENCE_GROUPS

    total_processed = db.query(ArticleAIOutput).count()
    relevant_count = db.query(ArticleAIOutput).filter(ArticleAIOutput.is_relevant == True).count()
    out_of_scope_count = db.query(ArticleAIOutput).filter(ArticleAIOutput.is_relevant == False).count()
    tech_success_count = relevant_count + out_of_scope_count
    unprocessed_or_failed = max(0, total_processed - tech_success_count)
    success_rate = (tech_success_count / total_processed * 100.0) if total_processed > 0 else 0.0

    topic_counts: dict[str, int] = {}
    country_counts: dict[str, int] = {}

    outputs = (
        db.query(ArticleAIOutput)
        .filter(ArticleAIOutput.is_relevant == True, ArticleAIOutput.output_json.is_not(None))
        .order_by(ArticleAIOutput.id.desc())
        .limit(100)
        .all()
    )

    for out in outputs:
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
        "total_processed": total_processed,
        "relevant_today": relevant_count,
        "out_of_scope_today": out_of_scope_count,
        "unprocessed_or_failed": unprocessed_or_failed,
        "success_rate": round(success_rate, 1),
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

    raw_articles = query.limit(limit * 2).all()

    if curated_only:
        raw_articles = [a for a in raw_articles if not is_article_out_of_scope(a)]

    if (mode or "balanced").lower() == "chronological":
        return raw_articles[:limit]

    return apply_editorial_diversity(raw_articles, max_per_source=2, max_items=limit)


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


def search_articles(
    db: Session, query_str: str, page: int = 1, page_size: int = 25
) -> dict[str, Any]:
    """Search articles by title or raw_summary."""
    if page < 1:
        page = 1

    clean_q = query_str.strip().lower()
    if not clean_q:
        return {
            "articles": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 1,
            "query": query_str,
            "has_prev": False,
            "has_next": False,
        }

    search_filter = or_(
        func.lower(Article.title).like(f"%{clean_q}%"),
        func.lower(Article.raw_summary).like(f"%{clean_q}%"),
    )

    query = (
        db.query(Article)
        .options(joinedload(Article.source))
        .filter(_valid_published_filter())
        .filter(search_filter)
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
        "articles": items,
        "total": total_items,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "query": query_str,
        "has_prev": page > 1,
        "has_next": page < total_pages,
    }


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



