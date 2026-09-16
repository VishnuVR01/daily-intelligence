"""
AI Worker Service for Safe AI Processing Queue (Sprint 1 Stage 1A).
Decouples article ingestion from Ollama AI processing.
Performs deterministic claiming, transaction isolation, failure isolation, and safe persistence.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models import Article, ArticleAIOutput
from repositories.ai_outputs import claim_eligible_articles, save_ai_output
from repositories.ai_queue import get_ai_queue_status
from services.ai.ollama import OllamaAnalysisResult, OllamaService
from services.ai.priority import calculate_article_priority

logger = logging.getLogger("services.ai.worker")


class AIWorker:
    def __init__(
        self,
        ollama_service: Optional[OllamaService] = None,
        provider: str = "ollama",
        model: str = "qwen3.5:4b",
        task: str = "article_analysis",
        prompt_version: str = "v1",
        cooldown_seconds: int = 300,
        stale_processing_seconds: int = 900,
    ):
        self.provider = provider
        self.model = model
        self.task = task
        self.prompt_version = prompt_version
        self.cooldown_seconds = cooldown_seconds
        self.stale_processing_seconds = stale_processing_seconds
        self.ollama_service = ollama_service or OllamaService(
            model=model, prompt_version=prompt_version
        )

    def process_article(self, db: Session, article: Article) -> ArticleAIOutput:
        """
        Processes a single claimed article using OllamaService with total failure isolation.
        No database transaction is open during the Ollama HTTP inference call.
        Persists the final output in a clean transaction.
        """
        src_name = article.source.name if article.source else "Unknown Source"
        src_family = article.source.source_family if article.source else "news"

        art_data = {
            "id": article.id,
            "title": article.title,
            "source_name": src_name,
            "source_family": src_family,
            "published_at": article.published_at.isoformat() if article.published_at else None,
            "collected_at": article.collected_at.isoformat() if article.collected_at else None,
            "raw_summary": article.raw_summary,
            "extracted_text": article.extracted_text,
        }

        # Ollama HTTP call outside open DB transaction
        try:
            res = self.ollama_service.analyze_article(art_data)
        except Exception as exc:
            logger.error(f"Unexpected exception processing article ID {article.id}: {exc}", exc_info=True)
            res = OllamaAnalysisResult(
                status="failed",
                error_message=f"Unexpected worker error: {exc.__class__.__name__} - {str(exc)}",
            )

        # Persist result idempotently in DB
        saved_output = save_ai_output(
            db=db,
            article_id=article.id,
            provider=self.provider,
            model=self.model,
            task=self.task,
            prompt_version=self.prompt_version,
            result=res,
            force=True,
        )

        return saved_output

    def run_batch(self, db: Session, batch_size: int = 5) -> Dict[str, Any]:
        """
        Executes a controlled worker batch processing run.

        Step 1: Claim up to `batch_size` eligible articles (Transaction 1).
        Step 2: Process each article independently outside open DB transactions.
        Step 3: Save output per article (Transaction 2).
        Step 4: Return execution report with queue state counts.
        """
        start_time = time.time()
        before_status = get_ai_queue_status(
            db=db,
            provider=self.provider,
            model=self.model,
            task=self.task,
            prompt_version=self.prompt_version,
            cooldown_seconds=self.cooldown_seconds,
            stale_processing_seconds=self.stale_processing_seconds,
        )

        claimed_articles = claim_eligible_articles(
            db=db,
            batch_size=batch_size,
            provider=self.provider,
            model=self.model,
            task=self.task,
            prompt_version=self.prompt_version,
            cooldown_seconds=self.cooldown_seconds,
            stale_processing_seconds=self.stale_processing_seconds,
        )

        results_detail: List[Dict[str, Any]] = []
        processed_success = 0
        relevant_count = 0
        out_of_scope_count = 0
        failed_count = 0

        for art in claimed_articles:
            output = self.process_article(db, art)

            st = output.status
            is_rel = output.is_relevant

            if st == "success" and is_rel:
                processed_success += 1
                relevant_count += 1
                final_state = "COMPLETED_RELEVANT"
            elif st == "out_of_scope" or (st == "success" and is_rel is False):
                processed_success += 1
                out_of_scope_count += 1
                final_state = "COMPLETED_OUT_OF_SCOPE"
            else:
                failed_count += 1
                final_state = "FAILED"

            src_name = art.source.name if art.source else "Unknown Source"
            col_at = art.collected_at.isoformat() if art.collected_at else None

            p_info = calculate_article_priority(art)

            results_detail.append({
                "article_id": art.id,
                "source": src_name,
                "title": art.title,
                "collected_at": col_at,
                "priority_tier": p_info["priority_tier"],
                "base_score": p_info["base_score"],
                "aging_bonus": p_info["aging_bonus"],
                "effective_score": p_info["effective_score"],
                "reasons": p_info["reasons"],
                "claim_status": "CLAIMED_SUCCESSFULLY",
                "ollama_result": st,
                "final_queue_state": final_state,
                "processing_time_ms": output.processing_ms or 0,
                "error_message": output.error_message,
            })

        after_status = get_ai_queue_status(
            db=db,
            provider=self.provider,
            model=self.model,
            task=self.task,
            prompt_version=self.prompt_version,
            cooldown_seconds=self.cooldown_seconds,
            stale_processing_seconds=self.stale_processing_seconds,
        )

        elapsed_ms = int((time.time() - start_time) * 1000)

        return {
            "claimed_count": len(claimed_articles),
            "processed_success": processed_success,
            "relevant_count": relevant_count,
            "out_of_scope_count": out_of_scope_count,
            "failed_count": failed_count,
            "batch_duration_ms": elapsed_ms,
            "before_queue_status": before_status,
            "after_queue_status": after_status,
            "article_results": results_detail,
        }


def process_next_batch(
    db: Session,
    batch_size: int = 5,
    cooldown_seconds: int = 300,
    stale_processing_seconds: int = 900,
    ollama_service: Optional[OllamaService] = None,
    provider: str = "ollama",
    model: str = "qwen3.5:4b",
    task: str = "article_analysis",
    prompt_version: str = "v1",
) -> Dict[str, Any]:
    """
    Convenience function for processing the next batch of eligible articles in the queue.
    """
    worker = AIWorker(
        ollama_service=ollama_service,
        provider=provider,
        model=model,
        task=task,
        prompt_version=prompt_version,
        cooldown_seconds=cooldown_seconds,
        stale_processing_seconds=stale_processing_seconds,
    )
    return worker.run_batch(db=db, batch_size=batch_size)
