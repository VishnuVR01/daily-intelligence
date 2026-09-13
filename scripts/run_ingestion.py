import logging
import sys

from app.db import SessionLocal
from app.models import Base
from ingestion.pipeline import run_ingestion_pipeline

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("scripts.run_ingestion")


def main() -> None:
    from app.db import engine

    Base.metadata.create_all(bind=engine)
    logger.info("Starting ingestion script...")
    session = SessionLocal()
    try:
        summary = run_ingestion_pipeline(session)

        print("\n" + "=" * 70)
        print("                        PER-SOURCE REPORT                        ")
        print("=" * 70)
        print(
            f"{'SOURCE':<32} {'TYPE':<6} {'FETCHED':>8} {'NEW':>6} {'DUPLICATES':>11}  {'STATUS'}"
        )
        print("-" * 70)
        for res in summary.source_results:
            print(
                f"{res.source_name:<32} {res.source_type:<6} {res.fetched:>8} {res.new:>6} {res.duplicates:>11}  {res.status}"
            )
        print("=" * 70)

        print("\n" + "=" * 40)
        print("     INGESTION PIPELINE SUMMARY     ")
        print("=" * 40)
        print(f"Active sources processed: {summary.active_sources_processed}")
        print(f"Inactive sources skipped: {summary.inactive_sources_skipped}")
        print(f"Unsupported sources     : {summary.unsupported_sources}")
        print(f"Healthy feeds           : {summary.healthy_feeds}")
        print(f"Empty feeds             : {summary.empty_feeds}")
        print(f"Failed feeds            : {summary.failed_feeds}")
        print(f"Articles fetched        : {summary.articles_fetched}")
        print(f"New articles            : {summary.new_articles}")
        print(f"Duplicates skipped      : {summary.duplicates_skipped}")
        print("=" * 40 + "\n")
    finally:
        session.close()


if __name__ == "__main__":
    main()
