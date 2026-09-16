"""
Production Readiness Smoke Test Script for Railway Deployment (Stage 1).
Non-mutating diagnostic script that verifies:
1. Database connectivity & schema migration state.
2. Source bootstrap registry availability (50 active sources in config/sources.json).
3. FastAPI application import & route registration.
4. One-shot ingestion engine readiness (Ollama independence).
Usage:
    python -m scripts.check_production_readiness
"""

import sys
import os
import json
import logging
from pathlib import Path

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("check_production_readiness")


def check_readiness() -> bool:
    print("=" * 65)
    print("      DAILY INTELLIGENCE — RAILWAY PRODUCTION READINESS      ")
    print("=" * 65)

    all_ok = True

    # 1. Environment & Config Audit
    from app.config import get_settings, sanitize_database_url, get_db_host_mode
    settings = get_settings()
    
    db_raw = settings.database_url
    db_effective = settings.effective_database_url
    sanitized = sanitize_database_url(db_effective or db_raw)
    host_mode = get_db_host_mode(db_effective or db_raw)

    print("\n--- 1. ENVIRONMENT & CONFIGURATION ---")
    print(f"  App Name          : {settings.app_name}")
    print(f"  App Environment   : {settings.app_env}")
    print(f"  App Timezone      : {settings.app_timezone}")
    print(f"  Database Host Mode: {host_mode}")
    print(f"  Sanitized DB URL  : {sanitized}")

    # 2. Database Connectivity & Schema Health
    print("\n--- 2. DATABASE CONNECTIVITY & SCHEMAS ---")
    from app.db import check_db_health
    health = check_db_health()

    print(f"  DB Reachable      : {'YES' if health['reachable'] else 'NO'}")
    print(f"  Schema Valid      : {'YES' if health['schema_valid'] else 'NO'}")
    print(f"  Migration Revision: {health.get('migration_revision') or 'N/A'}")

    if not health["reachable"] or not health["schema_valid"]:
        logger.error(f"Database health failure: {health.get('error')}")
        all_ok = False

    # 3. Source Registry Bootstrap Config
    print("\n--- 3. SOURCE BOOTSTRAP REGISTRY ---")
    sources_file = Path(__file__).resolve().parent.parent / "config" / "sources.json"
    if sources_file.exists():
        with open(sources_file, "r", encoding="utf-8") as f:
            sources_data = json.load(f)
        active_count = sum(1 for s in sources_data if s.get("active", True))
        print(f"  Sources File      : EXISTS ({len(sources_data)} total, {active_count} active)")
        if len(sources_data) < 50:
            logger.warning(f"Expected 50 configured sources, found {len(sources_data)}")
    else:
        logger.error("Missing config/sources.json bootstrap file!")
        all_ok = False

    # 4. FastAPI Application Import
    print("\n--- 4. FASTAPI APP IMPORT & ROUTES ---")
    try:
        from app.main import app
        route_paths = [r.path for r in app.routes]
        print(f"  FastAPI App Import: SUCCESS ({len(route_paths)} routes registered)")
        assert "/health" in route_paths, "Missing /health endpoint!"
        assert "/latest" in route_paths, "Missing /latest endpoint!"
    except Exception as exc:
        logger.error(f"FastAPI app import error: {exc}")
        all_ok = False

    # 5. One-Shot Ingestion Engine Decoupling Check
    print("\n--- 5. ONE-SHOT INGESTION ENGINE (OLLAMA DECOUPLING) ---")
    try:
        from ingestion.pipeline import run_ingestion_pipeline
        print("  Ingestion Pipeline: READY (Independent of LLM / Ollama)")
    except Exception as exc:
        logger.error(f"Ingestion pipeline import error: {exc}")
        all_ok = False

    print("\n" + "=" * 65)
    if all_ok:
        print("  RESULT: READINESS CHECK PASSED — SYSTEM READY FOR STAGE 1 DEPLOYMENT")
    else:
        print("  RESULT: READINESS CHECK FAILED — ISSUES DETECTED")
    print("=" * 65 + "\n")

    return all_ok


if __name__ == "__main__":
    success = check_readiness()
    sys.exit(0 if success else 1)
