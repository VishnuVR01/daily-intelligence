"""
CLI script to execute Stage 4D pattern detection and signal generation.

Usage:
    python scripts/generate_signals.py [--window WINDOW_DAYS] [--limit LIMIT] [--dry-run] [--reprocess]
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal
from services.knowledge.signals import detect_and_generate_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("generate_signals")


def main():
    parser = argparse.ArgumentParser(description="Generate deterministic knowledge signals.")
    parser.add_argument("--window", type=int, default=7, help="Observation window in days (default: 7)")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of qualified signals to generate")
    parser.add_argument("--dry-run", action="store_true", help="Log processing results without persisting to DB")
    parser.add_argument("--reprocess", action="store_true", help="Force reprocessing even if active signals exist")

    args = parser.parse_args()

    db = SessionLocal()
    try:
        logger.info(f"Executing Signal Engine for {args.window}-day window (limit={args.limit}, dry_run={args.dry_run})...")
        res = detect_and_generate_signals(
            db=db,
            window_days=args.window,
            reprocess=args.reprocess,
            dry_run=args.dry_run,
            limit=args.limit,
        )

        logger.info(
            f"Signal Generation Complete: Status={res['status']}, "
            f"Events Evaluated={res.get('events_evaluated', 0)}, "
            f"Candidates Collected={res.get('candidates_collected', 0)}, "
            f"Candidates Qualified={res.get('candidates_qualified', 0)}, "
            f"Signals Created={res.get('signals_created', 0)}, "
            f"Signals Updated={res.get('signals_updated', 0)}, "
            f"Signals Expired={res.get('signals_expired', 0)}, "
            f"Evidence Created={res.get('evidence_created', 0)}"
        )

        for s in res.get("signals", []):
            logger.info(f"  Signal #{s['signal_id']}: [{s['signal_type']}] '{s['title']}' (events={s['event_count']}, fp={s['fingerprint'][:16]}...)")

    finally:
        db.close()


if __name__ == "__main__":
    main()
