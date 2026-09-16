import sys
import os
import logging
from unittest.mock import patch

# Ensure app can be imported
sys.path.insert(0, os.path.abspath('.'))

from app.db import SessionLocal
from services.orchestrator import run_ingestion_cycle, run_ai_cycle, run_pipeline_cycle
from services.lock import pipeline_lock

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("stage_1c_verification")

def main():
    logger.info("=== STARTING STAGE 1C CONTROLLED AUTOMATION TEST ===")

    # Test A: Ingestion Cycle
    logger.info("--- Test A: Ingestion Cycle Execution ---")
    res_a = run_ingestion_cycle()
    logger.info(f"Test A Result: {res_a}")
    assert res_a["status"] == "COMPLETED", f"Test A failed: {res_a}"

    # Test B: AI Cycle (Bounded Draining)
    logger.info("--- Test B: Bounded AI Cycle Execution ---")
    res_b = run_ai_cycle()
    logger.info(f"Test B Result: {res_b}")
    assert res_b["status"] in ("COMPLETED", "SKIPPED_OLLAMA_UNAVAILABLE"), f"Test B failed: {res_b}"
    if res_b["status"] == "COMPLETED":
        assert res_b.get("processed_count", 0) <= 10, "Test B processed more than 10 articles!"

    # Test C: Combined Pipeline Cycle
    logger.info("--- Test C: Combined Pipeline Cycle Execution ---")
    res_c = run_pipeline_cycle()
    logger.info(f"Test C Result: {res_c}")
    assert "ingestion" in res_c and "ai" in res_c, f"Test C failed: {res_c}"

    # Test D: Overlap Lock Protection
    logger.info("--- Test D: Overlap Lock Protection ---")
    db = SessionLocal()
    try:
        with pipeline_lock(db, "ingestion"):
            res_d = run_ingestion_cycle(db=db)
            logger.info(f"Test D Result (when locked): {res_d}")
            assert res_d["status"] == "SKIPPED_ALREADY_RUNNING", f"Test D failed: {res_d}"
    finally:
        db.close()

    # Test E: Ollama Offline Isolation
    logger.info("--- Test E: Ollama Offline Isolation ---")
    with patch("services.ai.client.check_health", return_value=False):
        res_e = run_pipeline_cycle()
        logger.info(f"Test E Result (Ollama mock offline): {res_e}")
        assert res_e["ingestion"]["status"] == "COMPLETED", "Ingestion failed when Ollama was offline!"
        assert res_e["ai"]["status"] == "SKIPPED_OLLAMA_UNAVAILABLE", "AI cycle did not skip when Ollama was offline!"

    logger.info("=== STAGE 1C CONTROLLED AUTOMATION TEST PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    main()
