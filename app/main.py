from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any
import logging

from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base, engine, get_db
from app.schema_validation import validate_schema
from app.errors import register_error_handlers
import app.models  # noqa: F401
from app.models import DailyEdition, EditionEvent, EventEditorialProse, EditionBrief, EventCluster, Article
from services.quotes import get_daily_quote
from services.markets import (
    get_market_service,
    get_market_session_status,
    get_market_intelligence,
    generate_market_takeaways,
    generate_svg_mini_chart,
)
from services.rag import ask_archive
from repositories.articles import (
    get_all_countries,
    get_archive_stats,
    get_article_ai_output,
    get_articles_by_sections,
    get_articles_by_source,
    get_categories,
    get_categories_summary,
    get_edition_articles_by_sections,
    get_edition_top_story,
    get_paginated_articles,
    get_persisted_daily_edition,
    get_recent_articles,
    get_sources_summary,
    get_today_ai_context_stats,
    get_todays_country_counts,
    get_todays_world_articles,
    get_top_story,
    is_article_out_of_scope,
    search_articles,
    search_articles_v1,
)

from app.entity_metadata import (
    format_country_badges,
    get_country_info,
    get_sector_description,
    get_source_family_info,
    get_trust_tier_info,
)
from repositories.saved import (
    get_saved_article_ids,
    get_saved_counts,
    is_saved,
    list_saved_articles,
    mark_read,
    mark_unread,
    save_article,
    unsave_article,
)

logger = logging.getLogger("app.main")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Perform database schema validation on application startup without altering data
    try:
        validate_schema(engine, Base.metadata)
    except Exception as exc:
        logger.warning(f"Database schema validation skipped/failed on startup: {exc}")
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)


BASE_DIR = Path(__file__).resolve().parent.parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.globals["format_country_badges"] = format_country_badges
templates.env.globals["get_country_info"] = get_country_info
templates.env.globals["get_sector_description"] = get_sector_description
templates.env.globals["get_source_family_info"] = get_source_family_info
templates.env.globals["get_trust_tier_info"] = get_trust_tier_info
templates.env.globals["get_saved_article_ids"] = get_saved_article_ids
templates.env.globals["get_daily_quote"] = get_daily_quote
templates.env.globals["get_article_ai_output"] = get_article_ai_output
templates.env.globals["is_article_out_of_scope"] = is_article_out_of_scope
templates.env.globals["get_market_session_status"] = get_market_session_status

register_error_handlers(app, templates)

if settings.enable_error_test_routes:
    from app.dev_routes import router as dev_router
    app.include_router(dev_router)


@app.get("/_test/force-error")
def force_error():
    """Internal test route to verify 500 error page handling."""
    raise RuntimeError("Simulated internal database exception for error handler verification")




def get_masthead_date() -> str:
    try:
        tz = ZoneInfo(settings.app_timezone)
        return datetime.now(tz).strftime("%A, %B %d, %Y")
    except Exception:
        return datetime.now().strftime("%A, %B %d, %Y")


@app.get("/health")
def health() -> dict[str, str]:
    db_status = "connected"
    if settings.effective_database_url:
        try:
            from app.db import engine
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            db_status = "disconnected"
    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "database": db_status,
        "app": settings.app_name,
        "environment": settings.app_env,
    }


@app.get("/health/dependencies")
@app.get("/api/health/dependencies")
def health_dependencies() -> dict[str, Any]:
    """Sanitized diagnostic status of app dependencies (Database and Ollama)."""
    from app.db import check_db_health
    from services.ai.ollama import OllamaService

    db_status = check_db_health()
    ollama_svc = OllamaService()
    ollama_status = ollama_svc.get_health_status()

    is_ok = db_status["reachable"] and db_status["schema_valid"] and ollama_status["available"]
    return {
        "status": "ok" if is_ok else "degraded",
        "app": settings.app_name,
        "environment": settings.app_env,
        "database": {
            "configured": db_status["configured"],
            "mode": db_status["mode"],
            "reachable": db_status["reachable"],
            "schema_valid": db_status["schema_valid"],
            "migration_revision": db_status.get("migration_revision"),
        },
        "ollama": {
            "enabled": getattr(settings, "ollama_enabled", True),
            "mode": ollama_status["mode"],
            "available": ollama_status["available"],
            "model_configured": ollama_status["model_configured"],
        },
    }


@app.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    stats = get_archive_stats(db)
    categories = get_categories(db)
    saved_ids = get_saved_article_ids(db)
    daily_quote = get_daily_quote()
    ai_context_stats = get_today_ai_context_stats(db)

    # Global Markets
    try:
        market_svc = get_market_service()
        global_markets, markets_is_stale = await market_svc.get_global_markets()
    except Exception as exc:
        logger.error(f"Error loading global markets for homepage: {exc}")
        global_markets, markets_is_stale = [], False

    # Primary-read persisted DailyEdition for today
    today_edition = get_persisted_daily_edition(db)
    if today_edition:
        top_story = get_edition_top_story(db, today_edition)
        sections = get_edition_articles_by_sections(db, today_edition, category=category)
    else:
        # Safe fallback to dynamic query
        top_story = get_top_story(db, category=category)
        sections = get_articles_by_sections(db, category=category, curated_only=True)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "stats": stats,
            "categories": categories,
            "top_story": top_story,
            "sections": sections,
            "saved_ids": saved_ids,
            "masthead_date": get_masthead_date(),
            "active_category": category,
            "daily_quote": daily_quote,
            "ai_context_stats": ai_context_stats,
            "today_edition": today_edition,
            "global_markets": global_markets,
            "markets_is_stale": markets_is_stale,
        },
    )


@app.get("/markets", response_class=HTMLResponse)
async def markets_dashboard(
    request: Request,
    market: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    # 1. Market Data
    try:
        market_svc = get_market_service()
        global_res = await market_svc.get_global_markets()
        if isinstance(global_res, tuple) and len(global_res) == 2:
            global_markets, markets_is_stale = global_res
        else:
            global_markets, markets_is_stale = [], False

        macro_res = await market_svc.get_macro_commodities()
        if isinstance(macro_res, tuple) and len(macro_res) == 2:
            macro_commodities, macro_is_stale = macro_res
        else:
            macro_commodities, macro_is_stale = [], False

        sovereign_res = await market_svc.get_sovereign_yields()
        if isinstance(sovereign_res, tuple) and len(sovereign_res) == 2:
            sovereign_yields, yields_is_stale = sovereign_res
        else:
            sovereign_yields, yields_is_stale = [], False

        policy_res = await market_svc.get_monetary_policy_rates()
        if isinstance(policy_res, tuple) and len(policy_res) == 2:
            monetary_policy_rates, policy_is_stale = policy_res
        else:
            monetary_policy_rates, policy_is_stale = [], False
    except Exception as exc:
        logger.error(f"Error loading global markets for /markets route: {exc}")
        global_markets, markets_is_stale = [], False
        macro_commodities, macro_is_stale = [], False
        sovereign_yields, yields_is_stale = [], False
        monetary_policy_rates, policy_is_stale = [], False

    # 2. Session Engine
    market_sessions = {
        snap.region: get_market_session_status(snap.region)
        for snap in global_markets
    }

    # 3. Selected Market Resolution
    region_map = {
        "us": "United States",
        "united-states": "United States",
        "uk": "United Kingdom",
        "united-kingdom": "United Kingdom",
        "india": "India",
        "japan": "Japan",
        "europe": "Europe",
        "china": "China",
    }

    selected_region = "United States"
    if market and market.strip().lower() in region_map:
        selected_region = region_map[market.strip().lower()]
    elif market:
        for snap in global_markets:
            if snap.region.lower() == market.strip().lower():
                selected_region = snap.region
                break

    selected_snapshot = next(
        (s for s in global_markets if s.region == selected_region),
        global_markets[0] if global_markets else None
    )
    if selected_snapshot:
        selected_region = selected_snapshot.region

    # 4. Historical Series & SVG Chart
    historical_series = None
    svg_chart = ""
    try:
        historical_series = await market_svc.get_historical_series(selected_region)
        if historical_series and historical_series.daily_points:
            svg_chart = generate_svg_mini_chart(historical_series.daily_points)
    except Exception as exc:
        logger.error(f"Error fetching historical series for {selected_region}: {exc}")

    # 5. Market Intelligence & Takeaways
    intel_data = get_market_intelligence(db, selected_region=selected_region, hours_window=48)
    takeaways = generate_market_takeaways(
        global_markets,
        selected_region,
        intel_data["selected_matches_count"],
        macro_snapshots=macro_commodities,
        yield_snapshots=sovereign_yields,
        policy_snapshots=monetary_policy_rates,
    )
    saved_ids = get_saved_article_ids(db)

    return templates.TemplateResponse(
        request=request,
        name="markets.html",
        context={
            "global_markets": global_markets,
            "markets_is_stale": markets_is_stale,
            "macro_commodities": macro_commodities,
            "macro_is_stale": macro_is_stale,
            "sovereign_yields": sovereign_yields,
            "yields_is_stale": yields_is_stale,
            "monetary_policy_rates": monetary_policy_rates,
            "policy_is_stale": policy_is_stale,
            "market_sessions": market_sessions,
            "selected_snapshot": selected_snapshot,
            "historical_series": historical_series,
            "svg_chart": svg_chart,
            "intel_data": intel_data,
            "takeaways": takeaways,
            "saved_ids": saved_ids,
            "masthead_date": get_masthead_date(),
            "active_market": market,
        },
    )


@app.get("/edition")
def get_latest_edition_redirect(db: Session = Depends(get_db)):
    """
    Redirects to the latest published Daily Edition (/edition/YYYY-MM-DD).
    If no published edition exists, redirects to today's date in Europe/London.
    """
    latest_edition = (
        db.query(DailyEdition)
        .filter(DailyEdition.status == "PUBLISHED")
        .order_by(DailyEdition.edition_date.desc())
        .first()
    )
    if latest_edition:
        target_date_str = latest_edition.edition_date.strftime("%Y-%m-%d")
    else:
        target_date_str = datetime.now(ZoneInfo("Europe/London")).strftime("%Y-%m-%d")

    return RedirectResponse(url=f"/edition/{target_date_str}", status_code=307)


@app.get("/editions", response_class=HTMLResponse)
def get_editions_archive_page(request: Request, db: Session = Depends(get_db)):
    """
    Renders the Historical Daily Edition Archive page listing all editions.
    """
    editions = (
        db.query(DailyEdition)
        .order_by(DailyEdition.edition_date.desc())
        .all()
    )

    editions_data = []
    for ed in editions:
        lead_headline = "Daily Edition"
        if ed.lead_event_cluster_id:
            ee = (
                db.query(EditionEvent)
                .filter(EditionEvent.edition_id == ed.id, EditionEvent.event_cluster_id == ed.lead_event_cluster_id)
                .first()
            )
            if ee:
                prose = db.query(EventEditorialProse).filter(EventEditorialProse.edition_event_id == ee.id).first()
                if prose and prose.headline:
                    lead_headline = prose.headline

        editions_data.append({
            "edition_date": ed.edition_date.strftime("%Y-%m-%d"),
            "formatted_date": ed.edition_date.strftime("%A, %d %B %Y"),
            "status": ed.status,
            "readiness": ed.readiness,
            "event_count": ed.event_count,
            "article_count": ed.article_count,
            "lead_headline": lead_headline,
        })

    return templates.TemplateResponse(
        request=request,
        name="editions_archive.html",
        context={
            "editions": editions_data,
        },
    )


@app.get("/edition/{date_str}", response_class=HTMLResponse)
def get_historical_edition_page(date_str: str, request: Request, db: Session = Depends(get_db)):
    """
    Renders Historical Daily Edition for a specified Europe/London date string (YYYY-MM-DD).
    CRITICAL: Reads strictly persisted database snapshots. Never calls Ollama or mutates state.
    """
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Invalid date format '{date_str}'. Expected YYYY-MM-DD.")

    edition = db.query(DailyEdition).filter(DailyEdition.edition_date == target_date).first()

    if not edition:
        formatted_date = target_date.strftime("%A, %d %B %Y")
        return templates.TemplateResponse(
            request=request,
            name="edition.html",
            context={
                "edition": DailyEdition(edition_date=target_date, status="PREPARING", readiness="PREPARING"),
                "formatted_date": formatted_date,
                "events": [],
                "prev_edition_date": None,
                "next_edition_date": None,
            },
        )

    formatted_date = target_date.strftime("%A, %d %B %Y")

    # Load persisted brief
    brief = db.query(EditionBrief).filter(EditionBrief.edition_id == edition.id).first()

    # Load persisted edition events
    edition_events = db.query(EditionEvent).filter(EditionEvent.edition_id == edition.id).order_by(EditionEvent.position).all()

    events_data = []
    watch_next_items = []

    for ee in edition_events:
        prose = db.query(EventEditorialProse).filter(EventEditorialProse.edition_event_id == ee.id).first()
        cluster = ee.event_cluster

        prim_art = cluster.primary_article if cluster else None

        supp_arts = []
        if cluster and cluster.cluster_articles:
            for ca in cluster.cluster_articles:
                if not ca.is_primary and ca.article:
                    supp_arts.append(ca.article)

        headline = prose.headline if prose else (cluster.canonical_title if cluster else "Featured Event")
        summary = prose.summary if prose else (prim_art.raw_summary[:250] if prim_art and prim_art.raw_summary else headline)
        why_it_matters = prose.why_it_matters if prose else None

        why_selected = []
        if ee.selection_reason_json and isinstance(ee.selection_reason_json, dict):
            why_selected = ee.selection_reason_json.get("why_selected", [])
        elif ee.selection_reason:
            why_selected = [ee.selection_reason]

        ev_dict = {
            "cluster_id": ee.event_cluster_id,
            "headline": headline,
            "summary": summary,
            "why_it_matters": why_it_matters,
            "section": ee.section,
            "role": ee.role,
            "position": ee.position,
            "primary_article": prim_art,
            "supporting_articles": supp_arts,
            "why_selected": why_selected,
        }
        events_data.append(ev_dict)

        if prose and prose.watch_next_json and isinstance(prose.watch_next_json, dict):
            wn_evt = prose.watch_next_json.get("event")
            wn_dt = prose.watch_next_json.get("date_str")
            if wn_evt:
                watch_next_items.append({"event": wn_evt, "date_str": wn_dt})

    lead_event = next((e for e in events_data if e["role"] == "LEAD_STORY"), None)
    if not lead_event and events_data:
        lead_event = events_data[0]

    top_events = [e for e in events_data if e["role"] == "TOP_STORY" and e != lead_event]

    section_groups = {}
    for e in events_data:
        if e != lead_event and e not in top_events:
            section_groups.setdefault(e["section"], []).append(e)

    prev_ed = db.query(DailyEdition.edition_date).filter(DailyEdition.edition_date < target_date).order_by(DailyEdition.edition_date.desc()).first()
    next_ed = db.query(DailyEdition.edition_date).filter(DailyEdition.edition_date > target_date).order_by(DailyEdition.edition_date.asc()).first()

    prev_date_str = str(prev_ed[0]) if prev_ed else None
    next_date_str = str(next_ed[0]) if next_ed else None

    meta = edition.metadata_json or {}
    market_snapshots = meta.get("market_snapshot")
    market_snapshot_label = "HISTORICAL SNAPSHOT"
    # Filter or select Cross-Asset Macro symbols for Daily Edition: Equities, Commodities, Rates, FX
    CROSS_ASSET_KEYS = ["^GSPC", "^FTSE", "BZ=F", "GC=F", "^TNX", "GBPUSD=X", "SPX", "FTSE", "BRENT", "GOLD", "US10Y", "GBP/USD"]
    if market_snapshots and isinstance(market_snapshots, dict):
        filtered_snaps = {}
        for k, v in market_snapshots.items():
            if k in CROSS_ASSET_KEYS or any(ck in k for ck in CROSS_ASSET_KEYS):
                filtered_snaps[k] = v
        if filtered_snaps:
            market_snapshots = filtered_snaps

    return templates.TemplateResponse(
        request=request,
        name="edition.html",
        context={
            "edition": edition,
            "formatted_date": formatted_date,
            "brief": brief,
            "lead_event": lead_event,
            "top_events": top_events,
            "section_groups": section_groups,
            "events": events_data,
            "watch_next_items": watch_next_items,
            "market_snapshots": market_snapshots,
            "market_snapshot_label": market_snapshot_label,
            "prev_edition_date": prev_date_str,
            "next_edition_date": next_date_str,
        },
    )


@app.get("/search", response_class=HTMLResponse)
def search_page(
    request: Request,
    q: str = Query(default=""),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    category: str | None = Query(default=None),
    country: str | None = Query(default=None),
    source: str | None = Query(default=None),
    min_importance: int | None = Query(default=None),
    min_relevance: int | None = Query(default=None),
    relevant_only: int = Query(default=0),
    page: int = Query(default=1),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Historical Intelligence Search v1 route with full-text search and server-side filters."""
    d_from = None
    if date_from:
        try:
            d_from = datetime.strptime(date_from.strip(), "%Y-%m-%d").date()
        except ValueError:
            pass

    d_to = None
    if date_to:
        try:
            d_to = datetime.strptime(date_to.strip(), "%Y-%m-%d").date()
        except ValueError:
            pass

    categories = [category] if category else None
    countries = [country] if country else None
    sources = [source] if source else None

    results = search_articles_v1(
        db,
        query=q,
        date_from=d_from,
        date_to=d_to,
        categories=categories,
        countries=countries,
        sources=sources,
        min_importance=min_importance,
        min_relevance=min_relevance,
        relevant_only=bool(relevant_only),
        limit=20,
        page=page,
    )

    stats = get_archive_stats(db)
    all_categories = get_categories(db)
    all_countries = get_all_countries(db)
    saved_ids = get_saved_article_ids(db)

    return templates.TemplateResponse(
        request=request,
        name="search.html",
        context={
            "q": q,
            "results": results,
            "stats": stats,
            "categories": all_categories,
            "all_countries": all_countries,
            "saved_ids": saved_ids,
            "active_category": category,
            "active_country": country,
            "masthead_date": get_masthead_date(),
            "filters": {
                "date_from": date_from,
                "date_to": date_to,
                "categories": categories or [],
                "countries": countries or [],
                "sources": sources or [],
                "min_importance": min_importance,
                "min_relevance": min_relevance,
                "relevant_only": bool(relevant_only),
            },
        },
    )


@app.get("/research", response_class=HTMLResponse)
def research_page(
    request: Request,
    q: str = Query(default=""),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Intelligence Research Terminal route executing grounded RAG."""
    rag_result = None
    if q and q.strip():
        d_from = None
        if date_from:
            try:
                d_from = datetime.strptime(date_from.strip(), "%Y-%m-%d").date()
            except ValueError:
                pass

        d_to = None
        if date_to:
            try:
                d_to = datetime.strptime(date_to.strip(), "%Y-%m-%d").date()
            except ValueError:
                pass

        filters = {
            "date_from": d_from,
            "date_to": d_to,
            "categories": [category] if category else None,
            "relevant_only": True,
        }

        try:
            rag_result = ask_archive(db, question=q, filters=filters)
        except Exception as exc:
            logger.error(f"Error in research view: {exc}")
            rag_result = {
                "question": q,
                "answer": "Archive research is temporarily unavailable.",
                "confidence": "low",
                "evidence_count": 0,
                "citations": [],
                "key_themes": [],
                "date_range": None,
                "insufficient_evidence": True,
            }

    stats = get_archive_stats(db)
    categories = get_categories(db)
    saved_ids = get_saved_article_ids(db)

    return templates.TemplateResponse(
        request=request,
        name="research.html",
        context={
            "q": q,
            "rag_result": rag_result,
            "stats": stats,
            "categories": categories,
            "saved_ids": saved_ids,
            "active_category": category,
        },
    )


@app.post("/api/research")
def api_research(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """JSON API endpoint for submitting research questions and receiving RAG answers."""
    question = payload.get("question") or payload.get("q") or ""
    filters = payload.get("filters") or {}
    try:
        return ask_archive(db, question=question, filters=filters)
    except Exception as exc:
        logger.error(f"Error in api_research: {exc}")
        return {
            "question": question,
            "answer": "Archive research is temporarily unavailable.",
            "confidence": "low",
            "evidence_count": 0,
            "citations": [],
            "key_themes": [],
            "date_range": None,
            "insufficient_evidence": True,
        }


@app.get("/world", response_class=HTMLResponse)
def world(
    request: Request,
    country: str | None = Query(default=None),
    brics: bool = Query(default=False),
    lens: str | None = Query(default=None),
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    from app.intelligence_groups import (
        get_all_lens_chips,
        get_group_country_codes,
        get_group_info,
    )

    stats = get_archive_stats(db)
    categories = get_categories(db)
    all_countries = get_all_countries(db)
    country_counts = get_todays_country_counts(db)

    active_lens_key = (lens or "").lower().strip()
    if not active_lens_key and brics:
        active_lens_key = "brics"
    if not active_lens_key:
        active_lens_key = "world"

    active_lens_info = get_group_info(active_lens_key)
    lens_country_codes = get_group_country_codes(active_lens_key)
    all_lens_chips = get_all_lens_chips()

    articles = get_todays_world_articles(
        db, country_code=country, is_brics=(active_lens_key == "brics"), lens=active_lens_key, category=category
    )
    saved_ids = get_saved_article_ids(db)

    selected_country = None
    if country:
        selected_country = next((c for c in all_countries if c.code.upper() == country.upper()), None)

    all_countries_json = [
        {
            "code": c.code,
            "name": c.name,
            "region": c.region,
            "is_brics": c.is_brics,
            "is_g7": c.is_g7,
            "is_g20": c.is_g20,
        }
        for c in all_countries
    ]

    return templates.TemplateResponse(
        request=request,
        name="world.html",
        context={
            "stats": stats,
            "categories": categories,
            "all_countries": all_countries,
            "all_countries_json": all_countries_json,
            "country_counts": country_counts,
            "articles": articles,
            "saved_ids": saved_ids,
            "selected_country": selected_country,
            "active_country": country.upper() if country else None,
            "is_brics": (active_lens_key == "brics"),
            "active_lens": active_lens_key,
            "active_lens_info": active_lens_info,
            "lens_country_codes": lens_country_codes,
            "all_lens_chips": all_lens_chips,
            "active_category": category,
            "masthead_date": get_masthead_date(),
        },
    )


@app.get("/latest", response_class=HTMLResponse)
def latest(
    request: Request,
    category: str | None = Query(default=None),
    mode: str = Query(default="balanced"),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    from repositories.ai_queue import get_freshness_sla_metrics
    stats = get_archive_stats(db)
    categories = get_categories(db)
    articles = get_recent_articles(db, category=category, limit=50, mode=mode)
    saved_ids = get_saved_article_ids(db)
    freshness_sla = get_freshness_sla_metrics(db)

    return templates.TemplateResponse(
        request=request,
        name="latest.html",
        context={
            "stats": stats,
            "categories": categories,
            "articles": articles,
            "saved_ids": saved_ids,
            "active_category": category,
            "active_mode": mode,
            "masthead_date": get_masthead_date(),
            "freshness_sla": freshness_sla,
        },
    )


@app.get("/sectors", response_class=HTMLResponse)
@app.get("/categories", response_class=HTMLResponse)
def categories(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    stats = get_archive_stats(db)
    categories_summary = get_categories_summary(db)

    return templates.TemplateResponse(
        request=request,
        name="categories.html",
        context={
            "stats": stats,
            "categories_summary": categories_summary,
            "masthead_date": get_masthead_date(),
        },
    )


@app.get("/category/{slug}", response_class=HTMLResponse)
def category_detail(
    request: Request,
    slug: str,
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    stats = get_archive_stats(db)
    categories = get_categories(db)
    pagination = get_paginated_articles(db, page=page, page_size=25, category=slug)
    saved_ids = get_saved_article_ids(db)

    return templates.TemplateResponse(
        request=request,
        name="category_detail.html",
        context={
            "stats": stats,
            "categories": categories,
            "category": slug,
            "pagination": pagination,
            "saved_ids": saved_ids,
            "masthead_date": get_masthead_date(),
        },
    )


@app.get("/sources", response_class=HTMLResponse)
def sources(
    request: Request,
    family: str | None = Query(default=None),
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    stats = get_archive_stats(db)
    sources_summary = get_sources_summary(db, family=family, category=category)
    categories = get_categories(db)
    source_families = [
        {"key": "all", "label": "All Sources"},
        {"key": "news", "label": "News"},
        {"key": "government", "label": "Government"},
        {"key": "central_bank", "label": "Central Banks"},
        {"key": "consulting", "label": "Consulting"},
        {"key": "university", "label": "Universities"},
        {"key": "research", "label": "Research"},
        {"key": "industry", "label": "Industry"},
        {"key": "open_source", "label": "Open Source"},
    ]

    return templates.TemplateResponse(
        request=request,
        name="sources.html",
        context={
            "stats": stats,
            "sources_summary": sources_summary,
            "categories": categories,
            "source_families": source_families,
            "active_family": family or "all",
            "active_category": category or "all",
            "masthead_date": get_masthead_date(),
        },
    )


@app.get("/source/{source_id}", response_class=HTMLResponse)
def source_detail(
    request: Request,
    source_id: str,
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    stats = get_archive_stats(db)
    source_data = get_articles_by_source(db, source_identifier=source_id, page=page, page_size=25)
    saved_ids = get_saved_article_ids(db)

    return templates.TemplateResponse(
        request=request,
        name="source_detail.html",
        context={
            "stats": stats,
            "source": source_data["source"],
            "pagination": source_data,
            "saved_ids": saved_ids,
            "masthead_date": get_masthead_date(),
        },
    )





@app.get("/archive", response_class=HTMLResponse)
def archive(
    request: Request,
    page: int = Query(default=1, ge=1),
    category: str | None = Query(default=None),
    date: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    stats = get_archive_stats(db)
    categories = get_categories(db)
    pagination = get_paginated_articles(db, page=page, page_size=25, category=category, date_str=date)
    saved_ids = get_saved_article_ids(db)

    return templates.TemplateResponse(
        request=request,
        name="archive.html",
        context={
            "stats": stats,
            "categories": categories,
            "pagination": pagination,
            "saved_ids": saved_ids,
            "active_category": category,
            "active_date": date,
            "masthead_date": get_masthead_date(),
        },
    )


@app.get("/api/articles")
def api_articles(
    category: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    mode: str = Query(default="chronological"),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    articles = get_recent_articles(db, category=category, limit=limit, mode=mode)
    
    result = []
    for art in articles:
        result.append(
            {
                "id": art.id,
                "title": art.title,
                "canonical_url": art.canonical_url,
                "published_at": art.published_at.isoformat() if art.published_at else None,
                "collected_at": art.collected_at.isoformat() if art.collected_at else None,
                "raw_summary": art.raw_summary,
                "language": art.language,
                "source": {
                    "id": art.source.id,
                    "name": art.source.name,
                    "source_family": art.source.source_family,
                    "category": art.source.category,
                    "trust_tier": art.source.trust_tier,
                    "country_code": art.source.country_code,
                }
                if art.source
                else None,
            }
        )
    return result


@app.get("/saved", response_class=HTMLResponse)
def saved_page(
    request: Request,
    status: str = Query(default="all"),
    category: str | None = Query(default=None),
    source_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    stats = get_archive_stats(db)
    categories = get_categories(db)
    sources_summary = get_sources_summary(db)
    pagination = list_saved_articles(
        db, status_filter=status, category=category, source_id=source_id, page=page, page_size=25
    )

    return templates.TemplateResponse(
        request=request,
        name="saved.html",
        context={
            "stats": stats,
            "categories": categories,
            "sources": sources_summary,
            "pagination": pagination,
            "active_status": status,
            "active_category": category,
            "active_source_id": source_id,
            "masthead_date": get_masthead_date(),
        },
    )


@app.post("/api/articles/{article_id}/save")
def api_save_article(article_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        saved_item = save_article(db, article_id)
        return {
            "status": "saved",
            "article_id": article_id,
            "saved_at": saved_item.saved_at.isoformat() if saved_item.saved_at else None,
            "is_read": saved_item.is_read,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.delete("/api/articles/{article_id}/save")
def api_unsave_article(article_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    removed = unsave_article(db, article_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Article {article_id} is not saved")
    return {"status": "unsaved", "article_id": article_id}


@app.post("/api/articles/{article_id}/read")
def api_mark_read(article_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        saved_item = mark_read(db, article_id)
        return {
            "status": "read",
            "article_id": article_id,
            "is_read": True,
            "read_at": saved_item.read_at.isoformat() if saved_item.read_at else None,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/articles/{article_id}/unread")
def api_mark_unread(article_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    saved_item = mark_unread(db, article_id)
    if not saved_item:
        raise HTTPException(status_code=404, detail=f"Article {article_id} is not in saved list")
    return {
        "status": "unread",
        "article_id": article_id,
        "is_read": False,
    }


@app.get("/api/saved")
def api_get_saved(
    status: str = Query(default="all"),
    category: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    data = list_saved_articles(db, status_filter=status, category=category, page=page, page_size=25)
    result_items = []
    for s_art in data["saved_articles"]:
        art = s_art.article
        result_items.append(
            {
                "id": s_art.id,
                "article_id": art.id,
                "title": art.title,
                "canonical_url": art.canonical_url,
                "published_at": art.published_at.isoformat() if art.published_at else None,
                "saved_at": s_art.saved_at.isoformat() if s_art.saved_at else None,
                "is_read": s_art.is_read,
                "read_at": s_art.read_at.isoformat() if s_art.read_at else None,
                "source_name": art.source.name if art.source else None,
            }
        )
    return {
        "total": data["total"],
        "page": data["page"],
        "total_pages": data["total_pages"],
        "counts": data["counts"],
        "items": result_items,
    }


