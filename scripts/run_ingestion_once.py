"""
Manual One-Shot Ingestion Script (Sprint 1 Stage 1C Phase 6).
Executes a single ingestion cycle using services/orchestrator.py and prints structured output.
"""
import logging
import sys

from services.orchestrator import run_ingestion_cycle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def main():
    print("=" * 80)
    print("MANUAL ONE-SHOT INGESTION CYCLE")
    print("=" * 80)
    res = run_ingestion_cycle()

    print("\n[CYCLE METRICS]")
    print(f"  Status: {res.get('status')}")
    print(f"  Started At: {res.get('started_at')}")
    print(f"  Finished At: {res.get('finished_at')}")
    print(f"  Duration: {res.get('duration_seconds')}s")
    print(f"  Sources Attempted: {res.get('sources_attempted')}")
    print(f"  Sources Successful: {res.get('sources_successful')}")
    print(f"  Sources Failed: {res.get('sources_failed')}")
    print(f"  Articles Fetched: {res.get('articles_fetched')}")
    print(f"  New Articles Inserted: {res.get('new_articles_inserted')}")
    print(f"  Duplicates Skipped: {res.get('duplicates_skipped')}")
    print("=" * 80)


if __name__ == "__main__":
    main()
