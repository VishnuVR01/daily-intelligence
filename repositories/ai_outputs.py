"""
AI outputs repository for managing ArticleAIOutput records and safe article claiming.
Supports Safe AI Processing Queue (Sprint 1 Stage 1A).
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.models import Article, ArticleAIOutput, Source

from services.ai.priority import calculate_article_priority

logger = logging.getLogger("repositories.ai_outputs")


def get_articles_for_ai_processing(
    db: Session,
    limit: Optional[int] = 10,
    unprocessed_only: bool = True,
    today_only: bool = False,
    article_id: Optional[int] = None,
    provider: str = "ollama",
    model: str = "qwen3.5:4b",
    task: str = "article_analysis",
    prompt_version: str = "v1",
) -> List[Article]:
    """
    Fetches articles to process with AI according to specified filters.
    FIFO ordering by default (Article.collected_at.asc().nullslast(), Article.id.asc()).
    """
    query = db.query(Article)

    if article_id:
        query = query.filter(Article.id == article_id)

    if today_only:
        today = datetime.now(timezone.utc).date()
        query = query.filter(func.date(Article.published_at) == today)

    if unprocessed_only:
        subquery = select(ArticleAIOutput.article_id).filter(
            ArticleAIOutput.provider == provider,
            ArticleAIOutput.model == model,
            ArticleAIOutput.task == task,
            ArticleAIOutput.prompt_version == prompt_version,
        )
        query = query.filter(Article.id.not_in(subquery))

    query = query.order_by(Article.collected_at.asc().nullslast(), Article.id.asc())

    if limit:
        query = query.limit(limit)

    return query.all()


def claim_eligible_articles(
    db: Session,
    batch_size: int = 5,
    provider: str = "ollama",
    model: str = "qwen3.5:4b",
    task: str = "article_analysis",
    prompt_version: str = "v1",
    cooldown_seconds: int = 300,
    stale_processing_seconds: int = 900,
) -> List[Article]:
    """
    Safely claims eligible articles for AI processing prioritized by effective priority score DESC,
    with FIFO collected_at ASC, id ASC tie-breakers.

    Eligible articles:
    1. UNPROCESSED: Have no ArticleAIOutput record for (provider, model, task, prompt_version).
    2. RETRYABLE FAILED: Have status in ('failed', 'timeout', 'unavailable', 'temporary_error') and
       processed_at < (now - cooldown_seconds). Non-retryable errors ('invalid_json') are excluded.
    3. STALE PROCESSING: Have status == 'processing' and processed_at < (now - stale_processing_seconds).

    Uses PostgreSQL SELECT ... FOR UPDATE SKIP LOCKED where available.
    Safely handles IntegrityError race conditions if two workers attempt to claim the same article.
    Updates claimed records to status='processing' and commits the transaction.
    """
    now = datetime.now(timezone.utc)
    cooldown_cutoff = now - timedelta(seconds=cooldown_seconds)
    stale_cutoff = now - timedelta(seconds=stale_processing_seconds)

    # Retryable statuses exclude non-retryable invalid_json
    retryable_statuses = ["failed", "timeout", "unavailable", "temporary_error"]

    # Subquery for completed or non-retryable articles
    # Completed = success or out_of_scope
    # Non-retryable = invalid_json
    # Active processing = processing and processed_at >= stale_cutoff
    # Active cooldown = retryable status and processed_at >= cooldown_cutoff
    blocking_subquery = select(ArticleAIOutput.article_id).filter(
        ArticleAIOutput.provider == provider,
        ArticleAIOutput.model == model,
        ArticleAIOutput.task == task,
        ArticleAIOutput.prompt_version == prompt_version,
        (
            (ArticleAIOutput.status.in_(["success", "out_of_scope", "invalid_json"]))
            | ((ArticleAIOutput.status == "processing") & (ArticleAIOutput.processed_at >= stale_cutoff))
            | ((ArticleAIOutput.status.in_(retryable_statuses)) & (ArticleAIOutput.processed_at >= cooldown_cutoff))
        ),
    )

    query = db.query(Article)
    eligible_query = query.filter(Article.id.not_in(blocking_subquery))

    # Apply row-level locking with SKIP LOCKED on PostgreSQL dialects
    try:
        bind = db.get_bind()
        if bind and bind.dialect.name == "postgresql":
            eligible_query = eligible_query.with_for_update(skip_locked=True)
    except Exception:
        pass

    fresh_cutoff = now - timedelta(hours=2)

    fresh_query = eligible_query.filter(
        func.coalesce(Article.collected_at, Article.published_at) >= fresh_cutoff
    )
    backlog_query = eligible_query.filter(
        func.coalesce(Article.collected_at, Article.published_at) < fresh_cutoff
    )

    fresh_raw = fresh_query.limit(batch_size * 5).all()
    backlog_raw = backlog_query.limit(batch_size * 5).all()

    # Score FRESH lane candidates: sort by (-base_score, col_ts, id)
    fresh_scored = []
    for art in fresh_raw:
        p_info = calculate_article_priority(art, now=now)
        col_ts = art.collected_at or art.published_at or now
        if col_ts.tzinfo is None:
            col_ts = col_ts.replace(tzinfo=timezone.utc)
        fresh_scored.append((p_info["base_score"], col_ts, art.id, art, p_info))
    fresh_scored.sort(key=lambda x: (-x[0], x[1], x[2]))

    # Score BACKLOG lane candidates: sort by (-effective_score, col_ts, id)
    backlog_scored = []
    for art in backlog_raw:
        p_info = calculate_article_priority(art, now=now)
        col_ts = art.collected_at or art.published_at or now
        if col_ts.tzinfo is None:
            col_ts = col_ts.replace(tzinfo=timezone.utc)
        backlog_scored.append((p_info["effective_score"], col_ts, art.id, art, p_info))
    backlog_scored.sort(key=lambda x: (-x[0], x[1], x[2]))

    # Target allocation: 70% fresh, 30% backlog
    import math
    target_fresh_count = math.ceil(batch_size * 0.7)
    target_backlog_count = batch_size - target_fresh_count

    actual_fresh_avail = len(fresh_scored)
    actual_backlog_avail = len(backlog_scored)

    if actual_fresh_avail < target_fresh_count:
        target_backlog_count += (target_fresh_count - actual_fresh_avail)
        target_fresh_count = actual_fresh_avail

    if actual_backlog_avail < target_backlog_count:
        target_fresh_count += (target_backlog_count - actual_backlog_avail)
        target_backlog_count = actual_backlog_avail

    ordered_candidates = [x[3] for x in fresh_scored[:target_fresh_count]] + [x[3] for x in backlog_scored[:target_backlog_count]]

    if len(ordered_candidates) < batch_size:
        already_added = {a.id for a in ordered_candidates}
        for _, _, _, art, _ in fresh_scored + backlog_scored:
            if art.id not in already_added:
                ordered_candidates.append(art)
                already_added.add(art.id)
                if len(ordered_candidates) >= batch_size:
                    break

    claimed_articles: List[Article] = []

    for art in ordered_candidates:
        if len(claimed_articles) >= batch_size:
            break

        # Check existing output record for this article
        existing_output = (
            db.query(ArticleAIOutput)
            .filter(
                ArticleAIOutput.article_id == art.id,
                ArticleAIOutput.provider == provider,
                ArticleAIOutput.model == model,
                ArticleAIOutput.task == task,
                ArticleAIOutput.prompt_version == prompt_version,
            )
            .first()
        )

        if existing_output:
            # Verify record is indeed retryable / stale before updating
            st = existing_output.status
            proc_at = existing_output.processed_at or existing_output.created_at
            if proc_at and proc_at.tzinfo is None:
                proc_at = proc_at.replace(tzinfo=timezone.utc)

            is_stale_proc = (st == "processing" and proc_at < stale_cutoff)
            is_failed_cooldown = (st in retryable_statuses and proc_at < cooldown_cutoff)

            if not (is_stale_proc or is_failed_cooldown):
                continue

            existing_output.status = "processing"
            existing_output.processed_at = now
            existing_output.error_message = None
            try:
                db.flush()
                claimed_articles.append(art)
            except IntegrityError:
                db.rollback()
                logger.warning(f"Race condition updating claim for article ID {art.id}; skipping.")
                continue
        else:
            # Create new processing record
            new_output = ArticleAIOutput(
                article_id=art.id,
                provider=provider,
                model=model,
                task=task,
                prompt_version=prompt_version,
                status="processing",
                processed_at=now,
                created_at=now,
            )
            db.add(new_output)
            try:
                db.flush()
                claimed_articles.append(art)
            except (IntegrityError, DBAPIError) as exc:
                db.rollback()
                logger.warning(f"Race condition inserting claim for article ID {art.id}: {exc.__class__.__name__}; skipping.")
                continue

    # Commit claimed articles transaction so status='processing' is persisted before Ollama call
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"Error committing claimed batch transaction: {exc}")
        return []

    return claimed_articles


def save_ai_output(
    db: Session,
    article_id: int,
    provider: str,
    model: str,
    task: str,
    prompt_version: str,
    result: Any,  # OllamaAnalysisResult
    force: bool = False,
) -> ArticleAIOutput:
    """
    Saves or updates an ArticleAIOutput record idempotently.
    Updates existing 'processing' or completed record with the final Ollama output.
    Safely handles IntegrityError if concurrent creation occurs.
    """
    existing = (
        db.query(ArticleAIOutput)
        .filter(
            ArticleAIOutput.article_id == article_id,
            ArticleAIOutput.provider == provider,
            ArticleAIOutput.model == model,
            ArticleAIOutput.task == task,
            ArticleAIOutput.prompt_version == prompt_version,
        )
        .first()
    )

    # If completed output exists and force=False and status is already final (success/out_of_scope), return existing
    if existing and not force and existing.status in ("success", "out_of_scope"):
        return existing

    output_obj = existing or ArticleAIOutput(
        article_id=article_id,
        provider=provider,
        model=model,
        task=task,
        prompt_version=prompt_version,
    )

    output_obj.status = result.status
    output_obj.processing_ms = getattr(result, "processing_ms", 0)
    output_obj.error_message = getattr(result, "error_message", None)
    output_obj.processed_at = datetime.now(timezone.utc)

    raw_output = getattr(result, "raw_output", None)
    analysis = getattr(result, "analysis", None)

    if raw_output:
        output_obj.output_json = raw_output

    if analysis:
        output_obj.summary = analysis.summary
        output_obj.primary_category = analysis.primary_category
        output_obj.is_relevant = analysis.is_relevant
        output_obj.rejection_reason = analysis.rejection_reason
        output_obj.importance_score = analysis.importance_score
        output_obj.relevance_score = analysis.relevance_score
    elif raw_output:
        output_obj.summary = raw_output.get("summary")
        output_obj.primary_category = raw_output.get("primary_category")
        output_obj.is_relevant = raw_output.get("is_relevant")
        output_obj.rejection_reason = raw_output.get("rejection_reason")
        output_obj.importance_score = raw_output.get("importance_score")
        output_obj.relevance_score = raw_output.get("relevance_score")

    if not existing:
        db.add(output_obj)

    try:
        db.commit()
        db.refresh(output_obj)
    except IntegrityError:
        db.rollback()
        # Fetch again in case another worker saved it simultaneously
        existing = (
            db.query(ArticleAIOutput)
            .filter(
                ArticleAIOutput.article_id == article_id,
                ArticleAIOutput.provider == provider,
                ArticleAIOutput.model == model,
                ArticleAIOutput.task == task,
                ArticleAIOutput.prompt_version == prompt_version,
            )
            .first()
        )
        if existing:
            return existing
        raise

    return output_obj
