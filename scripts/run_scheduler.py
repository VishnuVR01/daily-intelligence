"""
Standalone Scheduler CLI Daemon (Sprint 1 Stage 1C Phase 4 & Phase 5).
Runs autonomous background ingestion (every 30m default) and AI processing (every 10m default)
using APScheduler in a dedicated process to avoid Uvicorn reload duplicates.
"""
import argparse
import logging
import os
import sys
import time

# Ensure repository root is on sys.path for direct CLI execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from services.orchestrator import run_ai_cycle, run_ingestion_cycle, run_pipeline_cycle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("scripts.run_scheduler")


import json
import os
from datetime import datetime, timezone

def update_scheduler_heartbeat(event: str | None = None, error: str | None = None):
    """Writes a lightweight heartbeat file to scratch/scheduler_heartbeat.json."""
    try:
        os.makedirs("scratch", exist_ok=True)
        heartbeat_path = os.path.join("scratch", "scheduler_heartbeat.json")
        now_iso = datetime.now(timezone.utc).isoformat()
        
        data = {
            "scheduler_active": True,
            "pid": os.getpid(),
            "last_scheduler_heartbeat": now_iso,
            "last_heartbeat_at": now_iso,
            "last_ingestion_started": None,
            "last_ingestion_completed": None,
            "last_ai_started": None,
            "last_ai_completed": None,
            "last_ingestion_error": None,
            "last_ai_error": None,
        }
        if os.path.exists(heartbeat_path):
            try:
                with open(heartbeat_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                    if isinstance(existing, dict):
                        data.update({k: v for k, v in existing.items() if k in data})
            except Exception:
                pass
        
        data["last_scheduler_heartbeat"] = now_iso
        data["last_heartbeat_at"] = now_iso

        if event == "ingestion_start":
            data["last_ingestion_started"] = now_iso
        elif event == "ingestion_complete":
            data["last_ingestion_completed"] = now_iso
            data["last_ingestion_error"] = error
        elif event == "ai_start":
            data["last_ai_started"] = now_iso
        elif event == "ai_complete":
            data["last_ai_completed"] = now_iso
            data["last_ai_error"] = error

        with open(heartbeat_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        logger.warning(f"Error updating scheduler heartbeat: {exc}")


def scheduled_heartbeat_job():
    """Lightweight 1-minute ticker job to update last_scheduler_heartbeat timestamp continuously."""
    update_scheduler_heartbeat()


def scheduled_ingestion_job():
    """Wrapper function for scheduled ingestion cycle with exception isolation."""
    try:
        logger.info("Executing scheduled ingestion job...")
        update_scheduler_heartbeat(event="ingestion_start")
        res = run_ingestion_cycle()
        status = res.get("status")
        err = res.get("error_message") if status == "FAILED" else None
        update_scheduler_heartbeat(event="ingestion_complete", error=err)
        logger.info(f"Scheduled ingestion job result: status={status}")
    except Exception as exc:
        update_scheduler_heartbeat(event="ingestion_complete", error=str(exc))
        logger.error(f"Scheduled ingestion job encountered exception: {exc}", exc_info=True)


def scheduled_ai_job():
    """Wrapper function for scheduled AI processing job with exception isolation."""
    try:
        logger.info("Executing scheduled AI processing job...")
        update_scheduler_heartbeat(event="ai_start")
        res = run_ai_cycle()
        status = res.get("status")
        err = res.get("error_message") if status == "FAILED" else None
        update_scheduler_heartbeat(event="ai_complete", error=err)
        logger.info(f"Scheduled AI processing job result: status={status}")
    except Exception as exc:
        update_scheduler_heartbeat(event="ai_complete", error=str(exc))
        logger.error(f"Scheduled AI processing job encountered exception: {exc}", exc_info=True)


def main():
    parser = argparse.ArgumentParser(
        description="Daily Intelligence Autonomous Scheduler Daemon (Sprint 1 Stage 1C)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Execute one pipeline cycle immediately and exit",
    )
    parser.add_argument(
        "--ingestion-interval",
        type=int,
        default=None,
        help="Ingestion interval in minutes (default: from settings)",
    )
    parser.add_argument(
        "--ai-interval",
        type=int,
        default=None,
        help="AI processing interval in minutes (default: from settings)",
    )
    args = parser.parse_args()

    settings = get_settings()
    ingestion_mins = args.ingestion_interval or settings.ingestion_interval_minutes or 30
    ai_mins = args.ai_interval or settings.ai_interval_minutes or 10

    if args.once:
        logger.info("Executing one-shot pipeline cycle via scheduler CLI...")
        res = run_pipeline_cycle()
        print("\n" + "=" * 70)
        print("ONE-SHOT PIPELINE EXECUTION SUMMARY")
        print("=" * 70)
        print(f"Status:             {res.get('status')}")
        print(f"Duration:           {res.get('duration_seconds')}s")
        print(f"Ingestion Status:   {res.get('ingestion', {}).get('status')}")
        print(f"AI Processing Status: {res.get('ai_processing', {}).get('status')}")
        print("=" * 70 + "\n")
        return

    logger.info("Starting Daily Intelligence Autonomous Scheduler Daemon...")
    logger.info(f"  Ingestion Schedule: Every {ingestion_mins} minute(s)")
    logger.info(f"  AI Processing Schedule: Every {ai_mins} minute(s)")

    update_scheduler_heartbeat()

    scheduler = BlockingScheduler(timezone="UTC")

    # Heartbeat ticker every 1 minute
    scheduler.add_job(
        scheduled_heartbeat_job,
        trigger=IntervalTrigger(minutes=1),
        id="job_scheduler_heartbeat",
        name="Scheduler Heartbeat Ticker",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    now_utc = datetime.now(timezone.utc)

    # Ingestion job: runs immediately on start, then every ingestion_mins
    scheduler.add_job(
        scheduled_ingestion_job,
        trigger=IntervalTrigger(minutes=ingestion_mins),
        id="job_ingestion_cycle",
        name="Autonomous Ingestion Cycle",
        next_run_time=now_utc,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )

    # AI job: runs immediately on start, then every ai_mins
    scheduler.add_job(
        scheduled_ai_job,
        trigger=IntervalTrigger(minutes=ai_mins),
        id="job_ai_cycle",
        name="Autonomous AI Processing Cycle",
        next_run_time=now_utc + timedelta(seconds=5),
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )

    try:
        logger.info("Scheduler daemon running. Press Ctrl+C to exit cleanly.")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down scheduler daemon cleanly...")
        scheduler.shutdown(wait=False)
        logger.info("Scheduler shutdown complete.")


if __name__ == "__main__":
    main()

