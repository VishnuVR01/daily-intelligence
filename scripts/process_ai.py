import argparse
import logging
import sys
import time
from typing import List

from app.config import get_settings
from app.db import SessionLocal
from repositories.ai_outputs import get_articles_for_ai_processing, save_ai_output
from services.ai.ollama import OllamaService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scripts.process_ai")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Daily Intelligence AI Batch Processor (Ollama Phase 1)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of articles to process (e.g. 10)",
    )
    parser.add_argument(
        "--today",
        action="store_true",
        help="Filter to today's published articles",
    )
    parser.add_argument(
        "--article-id",
        type=int,
        default=None,
        help="Target a specific article ID for processing",
    )
    parser.add_argument(
        "--unprocessed",
        action="store_true",
        help="Process only articles that have no AI outputs yet",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override Ollama model name (default: from settings)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reprocessing even if AI output exists",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    settings = get_settings()

    target_model = args.model or settings.ollama_model or "qwen3.5:4b"
    provider = "ollama"
    task = "article_analysis"
    prompt_version = settings.ai_prompt_version or "v1"

    # Safety check: if no specific targeting flag was passed, default to safe 10 unprocessed
    if not (args.limit or args.today or args.article_id or args.unprocessed or args.force):
        logger.info("No explicit arguments passed. Applying safe default: --limit 10 --unprocessed")
        args.limit = 10
        args.unprocessed = True

    ollama_svc = OllamaService(
        base_url=settings.ollama_base_url,
        model=target_model,
        timeout_seconds=settings.ollama_timeout_seconds,
        prompt_version=prompt_version,
    )

    logger.info(f"Checking Ollama status on {ollama_svc.base_url} for model '{target_model}'...")
    if not ollama_svc.check_health():
        logger.error(f"Ollama API service is not reachable at {ollama_svc.base_url}. Exiting safely.")
        sys.exit(1)

    db = SessionLocal()
    try:
        articles = get_articles_for_ai_processing(
            db=db,
            limit=args.limit,
            unprocessed_only=not args.force if args.unprocessed else not args.force,
            today_only=args.today,
            article_id=args.article_id,
            provider=provider,
            model=target_model,
            task=task,
            prompt_version=prompt_version,
        )

        if not articles:
            logger.info("No matching articles found for AI processing.")
            return

        logger.info(f"Starting AI processing for {len(articles)} article(s) using model '{target_model}'...")
        print("=" * 110, flush=True)
        print(f"{'ID':<6} {'SOURCE':<24} {'HEADLINE':<38} {'CATEGORY':<20} {'IMP':<5} {'REL':<5} {'MS':<6} {'STATUS'}", flush=True)
        print("-" * 110, flush=True)

        attempted = 0
        successful = 0
        failed = 0
        skipped = 0
        total_ms = 0

        for article in articles:
            attempted += 1
            article_dict = {
                "id": article.id,
                "title": article.title,
                "raw_summary": article.raw_summary,
                "extracted_text": article.extracted_text,
                "published_at": article.published_at.isoformat() if article.published_at else None,
                "collected_at": article.collected_at.isoformat() if article.collected_at else None,
                "source_name": article.source.name if article.source else "Unknown",
                "source_family": article.source.source_family if article.source else "news",
            }

            result = ollama_svc.analyze_article(article_dict, model_override=target_model)
            total_ms += result.processing_ms

            # Save result to database idempotently
            save_ai_output(
                db=db,
                article_id=article.id,
                provider=provider,
                model=target_model,
                task=task,
                prompt_version=prompt_version,
                result=result,
                force=args.force,
            )

            if result.status == "success":
                successful += 1
                cat = result.analysis.primary_category if result.analysis else "N/A"
                imp = result.analysis.importance_score if result.analysis else 0
                rel = result.analysis.relevance_score if result.analysis else 0
            else:
                failed += 1
                cat = "N/A"
                imp = 0
                rel = 0

            source_name = (article.source.name if article.source else "Unknown")[:22]
            headline_sub = article.title[:36]
            print(f"{article.id:<6} {source_name:<24} {headline_sub:<38} {cat:<20} {imp:<5} {rel:<5} {result.processing_ms:<6} {result.status}", flush=True)

        print("=" * 110)
        avg_ms = int(total_ms / attempted) if attempted > 0 else 0
        print("\n========================================")
        print("         AI PROCESSING SUMMARY          ")
        print("========================================")
        print(f"Attempted:                {attempted}")
        print(f"Successful:               {successful}")
        print(f"Failed:                   {failed}")
        print(f"Skipped:                  {skipped}")
        print(f"Average processing time:  {avg_ms} ms ({avg_ms/1000:.2f} s)")
        print("========================================\n")

    finally:
        db.close()


if __name__ == "__main__":
    main()
