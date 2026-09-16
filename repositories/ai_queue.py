"""
Queue repository and observability for Safe AI Processing Queue (Sprint 1 Stage 1B).
Provides comprehensive metrics on priority tiers (P0-P3), queue age, failure classification, and processing coverage.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import Article, ArticleAIOutput
from services.ai.priority import calculate_article_priority


def get_ai_queue_status(
    db: Session,
    provider: str = "ollama",
    model: str = "qwen3.5:4b",
    task: str = "article_analysis",
    prompt_version: str = "v1",
    cooldown_seconds: int = 300,
    stale_processing_seconds: int = 900,
    sample_priority_limit: int = 200,
) -> Dict[str, Any]:
    """
    Returns exact metrics on article AI processing queue status with Stage 1B priority tiers.

    Metrics:
    - total_articles: Total count of stored articles in canonical archive.
    - unprocessed: Count of articles with no ArticleAIOutput record.
    - P0_count, P1_count, P2_count, P3_count: Priority tier breakdown for unprocessed articles.
    - processing: Articles currently locked with status='processing' within active stale window.
    - stale_processing: Articles with status='processing' older than stale_processing_seconds.
    - completed_relevant: Articles with status='success' and is_relevant=True.
    - completed_out_of_scope: Articles with status='out_of_scope' or (is_relevant=False).
    - failed: Total count of failed articles.
    - non_retryable: Articles with status='invalid_json' (excluded from auto-retry).
    - retryable: Failed articles past cooldown OR stale processing.
    - eligible: Total articles eligible to be claimed right now (unprocessed + retryable).
    - oldest_unprocessed_timestamp: collected_at of the oldest unprocessed article.
    - queue_age_hours: Hours elapsed since the oldest unprocessed article was collected.
    - newest_processed_timestamp: processed_at of the newest completed/failed output.
    - ai_processing_coverage_percent: Percentage of total archive processed by AI.
    """
    now = datetime.now(timezone.utc)
    cooldown_cutoff = now - timedelta(seconds=cooldown_seconds)
    stale_cutoff = now - timedelta(seconds=stale_processing_seconds)

    total_articles = db.query(Article).count()

    # Subquery for outputs matching the specific AI configuration
    ai_subquery = (
        db.query(ArticleAIOutput)
        .filter(
            ArticleAIOutput.provider == provider,
            ArticleAIOutput.model == model,
            ArticleAIOutput.task == task,
            ArticleAIOutput.prompt_version == prompt_version,
        )
    )

    outputs = ai_subquery.all()
    output_map = {out.article_id: out for out in outputs}

    processing_count = 0
    stale_processing_count = 0
    completed_relevant_count = 0
    completed_out_of_scope_count = 0
    failed_count = 0
    non_retryable_count = 0
    retryable_count = 0

    retryable_statuses = {"failed", "timeout", "unavailable", "temporary_error"}

    for out in outputs:
        st = out.status
        proc_at = out.processed_at or out.created_at
        if proc_at and proc_at.tzinfo is None:
            proc_at = proc_at.replace(tzinfo=timezone.utc)

        if st == "processing":
            if proc_at and proc_at < stale_cutoff:
                stale_processing_count += 1
                retryable_count += 1
            else:
                processing_count += 1
        elif st == "success":
            if out.is_relevant is False:
                completed_out_of_scope_count += 1
            else:
                completed_relevant_count += 1
        elif st == "out_of_scope":
            completed_out_of_scope_count += 1
        elif st == "invalid_json":
            failed_count += 1
            non_retryable_count += 1
        elif st in retryable_statuses:
            failed_count += 1
            if proc_at and proc_at < cooldown_cutoff:
                retryable_count += 1

    # Unprocessed articles
    processed_article_ids = set(output_map.keys())
    if processed_article_ids:
        unprocessed_query = db.query(Article).filter(Article.id.not_in(processed_article_ids))
    else:
        unprocessed_query = db.query(Article)

    unprocessed_count = unprocessed_query.count()
    eligible_count = unprocessed_count + retryable_count

    # Tier breakdown sampling for unprocessed articles
    p0_count = 0
    p1_count = 0
    p2_count = 0
    p3_count = 0

    if unprocessed_count > 0:
        sample_unprocessed = (
            unprocessed_query
            .order_by(Article.collected_at.asc().nullslast(), Article.id.asc())
            .limit(sample_priority_limit)
            .all()
        )
        for art in sample_unprocessed:
            p_info = calculate_article_priority(art, now=now)
            t = p_info["priority_tier"]
            if t == "P0_CRITICAL":
                p0_count += 1
            elif t == "P1_HIGH":
                p1_count += 1
            elif t == "P2_NORMAL":
                p2_count += 1
            else:
                p3_count += 1

        # Extrapolate if total unprocessed > sample_priority_limit
        if unprocessed_count > sample_priority_limit and len(sample_unprocessed) > 0:
            scale = unprocessed_count / float(len(sample_unprocessed))
            p0_count = int(round(p0_count * scale))
            p1_count = int(round(p1_count * scale))
            p2_count = int(round(p2_count * scale))
            p3_count = unprocessed_count - (p0_count + p1_count + p2_count)

    # Oldest unprocessed article timestamp & queue age
    oldest_unprocessed = None
    queue_age_hours = 0.0
    oldest_art = unprocessed_query.order_by(Article.collected_at.asc().nullslast(), Article.id.asc()).first()
    if oldest_art:
        ts = oldest_art.collected_at or oldest_art.published_at
        if ts:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            oldest_unprocessed = ts.isoformat()
            queue_age_hours = round(max(0.0, (now - ts).total_seconds() / 3600.0), 2)

    # Newest processed output timestamp
    newest_processed = None
    newest_output = (
        ai_subquery
        .filter(ArticleAIOutput.status != "processing")
        .order_by(ArticleAIOutput.processed_at.desc().nullslast())
        .first()
    )
    if newest_output and newest_output.processed_at:
        newest_processed = newest_output.processed_at.isoformat()

    completed_total = completed_relevant_count + completed_out_of_scope_count
    coverage_percent = round((completed_total / float(total_articles) * 100.0), 2) if total_articles > 0 else 0.0

    return {
        "total_articles": total_articles,
        "unprocessed": unprocessed_count,
        "P0_CRITICAL": p0_count,
        "P1_HIGH": p1_count,
        "P2_NORMAL": p2_count,
        "P3_LOW": p3_count,
        "processing": processing_count,
        "stale_processing": stale_processing_count,
        "completed_relevant": completed_relevant_count,
        "completed_out_of_scope": completed_out_of_scope_count,
        "completed_total": completed_total,
        "failed": failed_count,
        "non_retryable": non_retryable_count,
        "retryable": retryable_count,
        "eligible": eligible_count,
        "oldest_unprocessed_timestamp": oldest_unprocessed,
        "queue_age_hours": queue_age_hours,
        "newest_processed_timestamp": newest_processed,
        "ai_processing_coverage_percent": coverage_percent,
    }


def get_freshness_sla_metrics(db: Session) -> Dict[str, Any]:
    """
    Calculates operational freshness SLA metrics for Daily Intelligence pipeline.
    Observes ingestion freshness, AI processing freshness, scheduler heartbeat, and SLA status.
    """
    import os, json
    now = datetime.now(timezone.utc)
    fresh_cutoff = now - timedelta(hours=2)

    # 1. Check Scheduler Heartbeat State
    scheduler_active = False
    last_scheduler_hb_dt = None
    hb_data = {}
    heartbeat_path = os.path.join("scratch", "scheduler_heartbeat.json")
    if os.path.exists(heartbeat_path):
        try:
            with open(heartbeat_path, "r", encoding="utf-8") as f:
                hb_data = json.load(f)
            hb_ts_str = hb_data.get("last_scheduler_heartbeat") or hb_data.get("last_heartbeat_at")
            if hb_ts_str:
                hb_dt = datetime.fromisoformat(hb_ts_str)
                if hb_dt.tzinfo is None:
                    hb_dt = hb_dt.replace(tzinfo=timezone.utc)
                last_scheduler_hb_dt = hb_dt
                if (now - hb_dt).total_seconds() <= 300:
                    scheduler_active = True
        except Exception:
            pass

    # 2. Latest Ingestion
    max_collected = db.query(func.max(Article.collected_at)).scalar()
    if max_collected and max_collected.tzinfo is None:
        max_collected = max_collected.replace(tzinfo=timezone.utc)
    
    minutes_since_ingestion = round((now - max_collected).total_seconds() / 60.0, 1) if max_collected else None

    # 3. Latest AI Processing (relevant or any output)
    latest_ai_output = (
        db.query(ArticleAIOutput)
        .filter(ArticleAIOutput.status.in_(["success", "out_of_scope"]))
        .order_by(ArticleAIOutput.processed_at.desc().nullslast())
        .first()
    )
    latest_ai_proc_at = None
    minutes_since_ai_processing = None
    if latest_ai_output and latest_ai_output.processed_at:
        proc_dt = latest_ai_output.processed_at
        if proc_dt.tzinfo is None:
            proc_dt = proc_dt.replace(tzinfo=timezone.utc)
        latest_ai_proc_at = proc_dt
        minutes_since_ai_processing = round((now - proc_dt).total_seconds() / 60.0, 1)

    # 4. Fresh vs Backlog Queue Breakdown
    unprocessed_subquery = select(ArticleAIOutput.article_id).filter(
        ArticleAIOutput.status.in_(["success", "out_of_scope", "invalid_json"])
    )
    fresh_queue_count = (
        db.query(Article)
        .filter(
            Article.id.not_in(unprocessed_subquery),
            func.coalesce(Article.collected_at, Article.published_at) >= fresh_cutoff,
        )
        .count()
    )

    backlog_queue_count = (
        db.query(Article)
        .filter(
            Article.id.not_in(unprocessed_subquery),
            func.coalesce(Article.collected_at, Article.published_at) < fresh_cutoff,
        )
        .count()
    )

    # 5. Oldest waiting article in fresh queue
    oldest_fresh = (
        db.query(Article)
        .filter(
            Article.id.not_in(unprocessed_subquery),
            func.coalesce(Article.collected_at, Article.published_at) >= fresh_cutoff,
        )
        .order_by(Article.collected_at.asc().nullslast(), Article.id.asc())
        .first()
    )
    fresh_oldest_wait_minutes = None
    if oldest_fresh:
        f_ts = oldest_fresh.collected_at or oldest_fresh.published_at or now
        if f_ts.tzinfo is None:
            f_ts = f_ts.replace(tzinfo=timezone.utc)
        fresh_oldest_wait_minutes = round(max(0.0, (now - f_ts).total_seconds() / 60.0), 1)

    # 6. SLA Status Classification (<=45m Ingestion, <=30m AI)
    ingestion_error = hb_data.get("last_ingestion_error")
    ai_error = hb_data.get("last_ai_error")

    if ingestion_error:
        ingestion_status = "FAILED"
    elif minutes_since_ingestion is None or minutes_since_ingestion > 45:
        ingestion_status = "STALE"
    else:
        ingestion_status = "HEALTHY"

    if ai_error:
        ai_status = "FAILED"
    elif minutes_since_ai_processing is None or minutes_since_ai_processing > 30:
        ai_status = "STALE"
    else:
        ai_status = "HEALTHY"

    if ingestion_status == "FAILED" or ai_status == "FAILED":
        overall_status = "ERROR"
    elif ingestion_status == "HEALTHY" and ai_status == "HEALTHY" and scheduler_active:
        overall_status = "LIVE"
    elif ingestion_status == "HEALTHY" and ai_status == "HEALTHY":
        overall_status = "FRESH"
    else:
        overall_status = "STALE"

    return {
        "latest_ingestion_at": max_collected.isoformat() if max_collected else None,
        "minutes_since_ingestion": minutes_since_ingestion,
        "latest_ai_processing_at": latest_ai_proc_at.isoformat() if latest_ai_proc_at else None,
        "minutes_since_ai_processing": minutes_since_ai_processing,
        "fresh_queue_count": fresh_queue_count,
        "backlog_queue_count": backlog_queue_count,
        "fresh_oldest_wait_minutes": fresh_oldest_wait_minutes,
        "ingestion_status": ingestion_status,
        "ai_status": ai_status,
        "overall_status": overall_status,
        "scheduler_active": scheduler_active,
        "last_scheduler_heartbeat": last_scheduler_hb_dt.isoformat() if last_scheduler_hb_dt else None,
    }

