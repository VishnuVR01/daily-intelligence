"""
CLI script to process event-entity participant linking for EventClusters.

Usage:
    python scripts/link_event_entities.py [--limit LIMIT] [--event-id EVENT_ID] [--dry-run] [--reprocess]
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal
from app.models import EventCluster
from services.knowledge.event_linking import link_event_entities

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("link_event_entities")


def main():
    parser = argparse.ArgumentParser(description="Process event entity participant linking.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of EventClusters to process")
    parser.add_argument("--event-id", type=str, default=None, help="Process a specific cluster_id")
    parser.add_argument("--dry-run", action="store_true", help="Log processing results without persisting to DB")
    parser.add_argument("--reprocess", action="store_true", help="Force reprocessing even if already processed")

    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = db.query(EventCluster).order_by(EventCluster.id.asc())
        if args.event_id:
            query = query.filter(EventCluster.cluster_id == args.event_id)

        if args.limit:
            query = query.limit(args.limit)

        clusters = query.all()
        logger.info(f"Found {len(clusters)} EventClusters to process.")

        stats = {
            "processed": 0,
            "candidate_entities": 0,
            "links_created": 0,
            "links_updated": 0,
            "links_rejected": 0,
            "errors": 0,
        }

        for cluster in clusters:
            try:
                res = link_event_entities(
                    db=db,
                    event_cluster_id=cluster.cluster_id,
                    reprocess=args.reprocess,
                    dry_run=args.dry_run,
                )
                stats["processed"] += 1
                stats["candidate_entities"] += res.get("candidate_entities", 0)
                stats["links_created"] += res.get("links_created", 0)
                stats["links_updated"] += res.get("links_updated", 0)
                stats["links_rejected"] += res.get("links_rejected", 0)

            except Exception as e:
                logger.error(f"Error processing cluster_id={cluster.cluster_id}: {e}")
                stats["errors"] += 1

        logger.info(
            f"Event Linking Complete: Processed={stats['processed']}, "
            f"Candidate Entities={stats['candidate_entities']}, "
            f"Links Created={stats['links_created']}, "
            f"Links Updated={stats['links_updated']}, "
            f"Links Rejected={stats['links_rejected']}, "
            f"Errors={stats['errors']}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()
