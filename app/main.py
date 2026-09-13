from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base, engine, get_db
from app.schema_validation import validate_schema
from app.errors import register_error_handlers
import app.models  # noqa: F401
from repositories.articles import (
    get_all_countries,
    get_archive_stats,
    get_articles_by_sections,
    get_articles_by_source,
    get_categories,
    get_categories_summary,
    get_paginated_articles,
    get_recent_articles,
    get_sources_summary,
    get_todays_country_counts,
    get_todays_world_articles,
    get_top_story,
    search_articles,
)

from app.entity_metadata import (
    format_country_badges,
    get_country_info,
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

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Perform database schema validation on application startup without altering data
    validate_schema(engine, Base.metadata)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)


BASE_DIR = Path(__file__).resolve().parent.parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.globals["format_country_badges"] = format_country_badges
templates.env.globals["get_country_info"] = get_country_info
templates.env.globals["get_source_family_info"] = get_source_family_info
templates.env.globals["get_trust_tier_info"] = get_trust_tier_info
templates.env.globals["get_saved_article_ids"] = get_saved_article_ids

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
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.app_env,
    }


@app.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    stats = get_archive_stats(db)
    categories = get_categories(db)
    top_story = get_top_story(db, category=category)
    sections = get_articles_by_sections(db, category=category)
    saved_ids = get_saved_article_ids(db)

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
        },
    )


@app.get("/world", response_class=HTMLResponse)
def world(
    request: Request,
    country: str | None = Query(default=None),
    brics: bool = Query(default=False),
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    stats = get_archive_stats(db)
    categories = get_categories(db)
    all_countries = get_all_countries(db)
    country_counts = get_todays_country_counts(db)
    articles = get_todays_world_articles(
        db, country_code=country, is_brics=brics, category=category
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
            "is_brics": brics,
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
    stats = get_archive_stats(db)
    categories = get_categories(db)
    articles = get_recent_articles(db, category=category, limit=50, mode=mode)
    saved_ids = get_saved_article_ids(db)

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
        },
    )


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


@app.get("/search", response_class=HTMLResponse)
def search(
    request: Request,
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    stats = get_archive_stats(db)
    results = search_articles(db, query_str=q, page=page, page_size=25)
    saved_ids = get_saved_article_ids(db)

    return templates.TemplateResponse(
        request=request,
        name="search.html",
        context={
            "stats": stats,
            "q": q,
            "results": results,
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
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    articles = get_recent_articles(db, category=category, limit=limit)
    
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

