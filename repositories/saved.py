from datetime import datetime, timezone
import math
from typing import Any, Dict, Optional, Set

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import Article, SavedArticle, Source


def is_saved(db: Session, article_id: int) -> bool:
    """Check if a specific article is saved."""
    return (
        db.query(SavedArticle)
        .filter(SavedArticle.article_id == article_id)
        .first()
        is not None
    )


def get_saved_article_ids(db: Session) -> Set[int]:
    """Get a set of all saved article IDs for quick UI rendering."""
    results = db.query(SavedArticle.article_id).all()
    return {r[0] for r in results if r[0] is not None}


def save_article(db: Session, article_id: int) -> SavedArticle:
    """
    Save an article. Idempotent: duplicate save does not duplicate row.
    """
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise ValueError(f"Article with id {article_id} does not exist.")

    existing = (
        db.query(SavedArticle)
        .filter(SavedArticle.article_id == article_id)
        .first()
    )
    if existing:
        return existing

    new_saved = SavedArticle(
        article_id=article_id,
        saved_at=datetime.now(timezone.utc),
        is_read=False,
        read_at=None,
    )
    db.add(new_saved)
    db.commit()
    db.refresh(new_saved)
    return new_saved


def unsave_article(db: Session, article_id: int) -> bool:
    """Remove an article from saved list."""
    existing = (
        db.query(SavedArticle)
        .filter(SavedArticle.article_id == article_id)
        .first()
    )
    if not existing:
        return False

    db.delete(existing)
    db.commit()
    return True


def mark_read(db: Session, article_id: int) -> Optional[SavedArticle]:
    """Mark a saved article as read."""
    existing = (
        db.query(SavedArticle)
        .filter(SavedArticle.article_id == article_id)
        .first()
    )
    if not existing:
        # Auto-save if marking as read
        existing = save_article(db, article_id)

    existing.is_read = True
    existing.read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(existing)
    return existing


def mark_unread(db: Session, article_id: int) -> Optional[SavedArticle]:
    """Mark a saved article as unread."""
    existing = (
        db.query(SavedArticle)
        .filter(SavedArticle.article_id == article_id)
        .first()
    )
    if not existing:
        return None

    existing.is_read = False
    existing.read_at = None
    db.commit()
    db.refresh(existing)
    return existing


def get_saved_counts(db: Session) -> Dict[str, int]:
    """Get counts for all, unread, and read saved articles."""
    all_count = db.query(SavedArticle).count()
    unread_count = db.query(SavedArticle).filter(SavedArticle.is_read == False).count()  # noqa: E712
    read_count = db.query(SavedArticle).filter(SavedArticle.is_read == True).count()  # noqa: E712
    return {"all": all_count, "unread": unread_count, "read": read_count}


def list_saved_articles(
    db: Session,
    status_filter: str = "all",
    category: Optional[str] = None,
    source_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 25,
) -> Dict[str, Any]:
    """
    Fetch paginated saved articles with status (all, unread, read),
    category, and source filtering.
    """
    if page < 1:
        page = 1

    query = (
        db.query(SavedArticle)
        .join(SavedArticle.article)
        .options(
            joinedload(SavedArticle.article).joinedload(Article.source),
            joinedload(SavedArticle.article).joinedload(Article.countries),
        )
    )

    clean_status = (status_filter or "all").lower()
    if clean_status == "unread":
        query = query.filter(SavedArticle.is_read == False)  # noqa: E712
    elif clean_status == "read":
        query = query.filter(SavedArticle.is_read == True)  # noqa: E712

    if category and category.lower() != "all":
        query = query.join(Article.source).filter(
            func.lower(Source.category) == category.lower()
        )

    if source_id:
        query = query.filter(Article.source_id == source_id)

    total_items = query.count()
    total_pages = math.ceil(total_items / page_size) if total_items > 0 else 1

    if page > total_pages and total_pages > 0:
        page = total_pages

    offset = (page - 1) * page_size
    items = (
        query.order_by(SavedArticle.saved_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return {
        "saved_articles": items,
        "total": total_items,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "status_filter": clean_status,
        "counts": get_saved_counts(db),
        "has_prev": page > 1,
        "has_next": page < total_pages,
    }
