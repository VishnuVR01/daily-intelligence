"""
Orchestration Service for Autonomous Ingestion & AI Processing Pipeline (Sprint 1 Stage 1C).
Decouples ingestion from AI processing and provides bounded execution cycles,
overlap protection, structured logging, and complete failure isolation.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from ingestion.pipeline import run_ingestion_pipeline
from repositories.ai_queue import get_ai_queue_status
from services.ai.ollama import OllamaService
from services.ai.worker import process_next_batch
from services.lock import pipeline_lock

logger = logging.getLogger("services.orchestrator")


def run_ingestion_cycle(db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Executes a single autonomous source ingestion cycle.
    Protected against concurrent overlapping execution by pipeline_lock.
    Reuses canonical ingestion pipeline (ingestion/pipeline.py).
    """
    start_time = time.time()
    started_at = datetime.now(timezone.utc)
    close_db_on_exit = False

    if db is None:
        db = SessionLocal()
        close_db_on_exit = True

    try:
        with pipeline_lock(db, "ingestion_cycle") as acquired:
            if not acquired:
                logger.info("Ingestion cycle skipped: Another ingestion cycle is ALREADY_RUNNING.")
                return {
                    "status": "SKIPPED_ALREADY_RUNNING",
                    "started_at": started_at.isoformat(),
                    "message": "Another ingestion cycle is active",
                }

            logger.info("Starting autonomous ingestion cycle...")
            summary = run_ingestion_pipeline(db)

            finished_at = datetime.now(timezone.utc)
            duration_s = round(time.time() - start_time, 2)

            res_dict = {
                "status": "COMPLETED",
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "duration_seconds": duration_s,
                "sources_attempted": summary.active_sources_processed,
                "sources_successful": summary.healthy_feeds + summary.empty_feeds,
                "sources_failed": summary.failed_feeds,
                "articles_fetched": summary.articles_fetched,
                "new_articles_inserted": summary.new_articles,
                "duplicates_skipped": summary.duplicates_skipped,
                "summary_details": summary.to_dict(),
            }

            logger.info(
                f"Ingestion cycle completed in {duration_s}s | "
                f"Fetched: {summary.articles_fetched} | New: {summary.new_articles} | Duplicates: {summary.duplicates_skipped}"
            )
            return res_dict

    except Exception as exc:
        logger.error(f"Ingestion cycle failed with unexpected error: {exc}", exc_info=True)
        return {
            "status": "FAILED",
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error_message": str(exc),
        }
    finally:
        if close_db_on_exit and db:
            db.close()


def run_ai_cycle(
    db: Optional[Session] = None,
    batch_size: Optional[int] = None,
    max_batches: Optional[int] = None,
    ollama_service: Optional[OllamaService] = None,
) -> Dict[str, Any]:
    """
    Executes a bounded AI queue draining cycle using Stage 1B priority ordering.
    Protected against concurrent execution by pipeline_lock.
    Completely isolated from ingestion: Ollama being offline returns SKIPPED_OLLAMA_UNAVAILABLE.
    """
    start_time = time.time()
    started_at = datetime.now(timezone.utc)
    settings = get_settings()

    effective_batch_size = batch_size or settings.ai_batch_size or 5
    effective_max_batches = max_batches or settings.ai_max_batches_per_cycle or 2

    close_db_on_exit = False
    if db is None:
        db = SessionLocal()
        close_db_on_exit = True

    try:
        with pipeline_lock(db, "ai_cycle") as acquired:
            if not acquired:
                logger.info("AI cycle skipped: Another AI processing cycle is ALREADY_RUNNING.")
                return {
                    "status": "SKIPPED_ALREADY_RUNNING",
                    "started_at": started_at.isoformat(),
                    "message": "Another AI cycle is active",
                }

            logger.info(f"Starting AI processing cycle (batch_size={effective_batch_size}, max_batches={effective_max_batches})...")
            
            svc = ollama_service or OllamaService(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
                timeout_seconds=settings.ollama_timeout_seconds,
            )

            # Check Ollama health before attempting queue processing
            if not svc.check_health():
                logger.warning("Ollama API is currently unreachable. AI processing cycle skipped safely.")
                before_status = get_ai_queue_status(db)
                return {
                    "status": "SKIPPED_OLLAMA_UNAVAILABLE",
                    "started_at": started_at.isoformat(),
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "message": "Ollama service unavailable",
                    "queue_status": before_status,
                }

            before_status = get_ai_queue_status(db)
            total_claimed = 0
            total_processed_success = 0
            total_relevant = 0
            total_out_of_scope = 0
            total_failed = 0
            all_article_results = []

            for b_idx in range(effective_max_batches):
                batch_res = process_next_batch(
                    db=db,
                    batch_size=effective_batch_size,
                    ollama_service=svc,
                )

                claimed = batch_res.get("claimed_count", 0)
                if claimed == 0:
                    logger.info(f"Queue empty or no eligible articles at batch {b_idx + 1}; ending AI cycle early.")
                    break

                total_claimed += claimed
                total_processed_success += batch_res.get("processed_success", 0)
                total_relevant += batch_res.get("relevant_count", 0)
                total_out_of_scope += batch_res.get("out_of_scope_count", 0)
                total_failed += batch_res.get("failed_count", 0)
                all_article_results.extend(batch_res.get("article_results", []))

            after_status = get_ai_queue_status(db)
            finished_at = datetime.now(timezone.utc)
            duration_s = round(time.time() - start_time, 2)

            res_dict = {
                "status": "COMPLETED",
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "duration_seconds": duration_s,
                "batches_executed": min(effective_max_batches, (total_claimed + effective_batch_size - 1) // effective_batch_size if total_claimed > 0 else 0),
                "articles_claimed": total_claimed,
                "processed_success": total_processed_success,
                "completed_relevant": total_relevant,
                "completed_out_of_scope": total_out_of_scope,
                "failed": total_failed,
                "before_queue_status": before_status,
                "after_queue_status": after_status,
                "article_results": all_article_results,
            }

            logger.info(
                f"AI cycle completed in {duration_s}s | "
                f"Claimed: {total_claimed} | Relevant: {total_relevant} | Out of scope: {total_out_of_scope} | Failed: {total_failed}"
            )
            return res_dict

    except Exception as exc:
        logger.error(f"AI cycle failed with unexpected error: {exc}", exc_info=True)
        return {
            "status": "FAILED",
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error_message": str(exc),
        }
    finally:
        if close_db_on_exit and db:
            db.close()


def run_pipeline_cycle(
    db: Optional[Session] = None,
    ai_batch_size: Optional[int] = None,
    ai_max_batches: Optional[int] = None,
    ollama_service: Optional[OllamaService] = None,
) -> Dict[str, Any]:
    """
    Executes a complete pipeline cycle (Ingestion + AI processing sequentially).
    Protected against concurrent execution by pipeline_lock.
    """
    start_time = time.time()
    started_at = datetime.now(timezone.utc)

    close_db_on_exit = False
    if db is None:
        db = SessionLocal()
        close_db_on_exit = True

    try:
        with pipeline_lock(db, "pipeline_cycle") as acquired:
            if not acquired:
                logger.info("Pipeline cycle skipped: Another pipeline cycle is ALREADY_RUNNING.")
                return {
                    "status": "SKIPPED_ALREADY_RUNNING",
                    "started_at": started_at.isoformat(),
                    "message": "Another pipeline cycle is active",
                }

            logger.info("Starting complete autonomous pipeline cycle (Ingestion -> AI Processing)...")

            # 1. Run Ingestion Cycle (does not fail AI if no new articles)
            ingestion_res = run_ingestion_cycle(db=db)

            # 2. Run AI Processing Cycle (does not fail if Ollama offline)
            ai_res = run_ai_cycle(
                db=db,
                batch_size=ai_batch_size,
                max_batches=ai_max_batches,
                ollama_service=ollama_service,
            )

            finished_at = datetime.now(timezone.utc)
            duration_s = round(time.time() - start_time, 2)

            return {
                "status": "COMPLETED",
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "duration_seconds": duration_s,
                "ingestion": ingestion_res,
                "ai_processing": ai_res,
            }

    finally:
        if close_db_on_exit and db:
            db.close()
