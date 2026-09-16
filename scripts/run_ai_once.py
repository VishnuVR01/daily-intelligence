"""
Manual One-Shot AI Processing Script (Sprint 1 Stage 1C Phase 6).
Executes a single bounded AI processing cycle using services/orchestrator.py and prints structured output.
"""
import argparse
import logging
import sys

from services.orchestrator import run_ai_cycle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def main():
    parser = argparse.ArgumentParser(description="Manual One-Shot AI Processing Cycle")
    parser.add_argument("--batch-size", type=int, default=5, help="Articles per batch (default: 5)")
    parser.add_argument("--max-batches", type=int, default=2, help="Max batches per cycle (default: 2)")
    args = parser.parse_args()

    print("=" * 80)
    print("MANUAL ONE-SHOT AI PROCESSING CYCLE")
    print("=" * 80)
    res = run_ai_cycle(batch_size=args.batch_size, max_batches=args.max_batches)

    print("\n[CYCLE METRICS]")
    print(f"  Status: {res.get('status')}")
    print(f"  Started At: {res.get('started_at')}")
    print(f"  Finished At: {res.get('finished_at')}")
    print(f"  Duration: {res.get('duration_seconds')}s")
    print(f"  Articles Claimed: {res.get('articles_claimed')}")
    print(f"  Processed Success: {res.get('processed_success')}")
    print(f"  Completed Relevant: {res.get('completed_relevant')}")
    print(f"  Completed Out of Scope: {res.get('completed_out_of_scope')}")
    print(f"  Failed: {res.get('failed')}")

    if res.get("article_results"):
        print("\nEXECUTED ARTICLE DETAILS:")
        for idx, art in enumerate(res["article_results"], 1):
            print(f"  [{idx}] ID {art['article_id']} | Tier: {art.get('priority_tier')} | Score: {art.get('effective_score')} | State: {art.get('final_queue_state')} | Time: {art.get('processing_time_ms')}ms")
            print(f"      Title: {art.get('title')[:60]}...")
    print("=" * 80)


if __name__ == "__main__":
    main()
