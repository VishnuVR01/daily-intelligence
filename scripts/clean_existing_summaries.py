import logging
import sys

from app.db import SessionLocal, engine
from app.models import Article, Base
from ingestion.normalize import clean_summary_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def clean_existing_summaries() -> dict[str, int]:
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    scanned_count = 0
    updated_count = 0

    try:
        articles = session.query(Article).all()
        scanned_count = len(articles)
        logger.info(f"Scanning {scanned_count} articles for summary text cleaning...")

        for article in articles:
            if not article.raw_summary:
                continue

            cleaned = clean_summary_text(article.raw_summary)

            if article.raw_summary != cleaned:
                article.raw_summary = cleaned
                updated_count += 1

        session.commit()
        logger.info(f"Cleanup complete. Scanned: {scanned_count} | Updated: {updated_count}")

    except Exception as exc:
        session.rollback()
        logger.error(f"Error during summary cleanup: {exc}")
        raise
    finally:
        session.close()

    return {"scanned": scanned_count, "updated": updated_count}


def main() -> None:
    summary = clean_existing_summaries()
    print("\n" + "=" * 40)
    print("    EXISTING SUMMARY CLEANUP REPORT    ")
    print("=" * 40)
    print(f"Articles scanned: {summary['scanned']}")
    print(f"Articles updated: {summary['updated']}")
    print("=" * 40 + "\n")


if __name__ == "__main__":
    main()
