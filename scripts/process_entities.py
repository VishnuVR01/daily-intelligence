"""CLI script to process entity extraction and resolution for AI-reviewed articles.

Usage:
    python scripts/process_entities.py [--limit LIMIT] [--article-id ARTICLE_ID] [--dry-run] [--reprocess]
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal

from app.models import ArticleAIOutput
from services.knowledge.service import process_article_entities

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("process_entities")


def main():
    parser = argparse.ArgumentParser(description="Process entity extraction and resolution.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of articles to process")
    parser.add_argument("--article-id", type=int, default=None, help="Process a specific article ID")
    parser.add_argument("--dry-run", action="store_true", help="Log processing results without persisting to DB")
    parser.add_argument("--reprocess", action="store_true", help="Force reprocessing even if already processed")

    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = db.query(ArticleAIOutput).filter(ArticleAIOutput.is_relevant == True)
        if args.article_id:
            query = query.filter(ArticleAIOutput.article_id == args.article_id)
        
        query = query.order_by(ArticleAIOutput.article_id.asc())

        if args.limit:
            query = query.limit(args.limit)

        ai_outputs = query.all()
        logger.info(f"Found {len(ai_outputs)} AI-reviewed relevant articles to process.")

        stats = {
            "processed": 0,
            "entities_found": 0,
            "entities_created": 0,
            "aliases_created": 0,
            "mentions_created": 0,
            "errors": 0,
        }

        for ai_output in ai_outputs:
            try:
                res = process_article_entities(
                    db=db,
                    article_id=ai_output.article_id,
                    dry_run=args.dry_run,
                    reprocess=args.reprocess,
                )
                stats["processed"] += 1
                stats["entities_found"] += res.get("entities_found", 0)
                stats["entities_created"] += res.get("entities_created", 0)
                stats["aliases_created"] += res.get("aliases_created", 0)
                stats["mentions_created"] += res.get("mentions_created", 0)

            except Exception as e:
                logger.error(f"Error processing article_id={ai_output.article_id}: {e}")
                stats["errors"] += 1

        logger.info(
            f"Processing Complete: Processed={stats['processed']}, "
            f"Entities Found={stats['entities_found']}, "
            f"Entities Created={stats['entities_created']}, "
            f"Aliases Created={stats['aliases_created']}, "
            f"Mentions Created={stats['mentions_created']}, "
            f"Errors={stats['errors']}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()
