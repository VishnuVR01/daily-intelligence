"""
Manual One-Shot Pipeline Script (Sprint 1 Stage 1C Phase 6).
Executes a complete ingestion -> AI processing pipeline cycle using services/orchestrator.py.
"""
import argparse
import logging
import sys

from services.orchestrator import run_pipeline_cycle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def main():
    parser = argparse.ArgumentParser(description="Manual One-Shot Autonomous Pipeline Cycle")
    parser.add_argument("--batch-size", type=int, default=5, help="AI batch size (default: 5)")
    parser.add_argument("--max-batches", type=int, default=2, help="Max AI batches (default: 2)")
    args = parser.parse_args()

    print("=" * 80)
    print("MANUAL ONE-SHOT AUTONOMOUS PIPELINE CYCLE")
    print("=" * 80)
    res = run_pipeline_cycle(ai_batch_size=args.batch_size, ai_max_batches=args.max_batches)

    ing = res.get("ingestion", {})
    ai = res.get("ai_processing", {})

    print("\n[SUMMARY]")
    print(f"  Pipeline Status: {res.get('status')}")
    print(f"  Total Duration: {res.get('duration_seconds')}s")
    print(f"  Ingestion Status: {ing.get('status')} | New Articles: {ing.get('new_articles_inserted', 0)}")
    print(f"  AI Processing Status: {ai.get('status')} | Claimed: {ai.get('articles_claimed', 0)} | Relevant: {ai.get('completed_relevant', 0)}")
    print("=" * 80)


if __name__ == "__main__":
    main()
