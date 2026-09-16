import sys
import json
from datetime import datetime, timezone
sys.path.insert(0, '.')

from app.db import SessionLocal
from app.models import Article, ArticleAIOutput
from services.orchestrator import run_ingestion_cycle, run_ai_cycle
from repositories.ai_queue import get_freshness_sla_metrics, get_ai_queue_status

def execute_recovery():
    db = SessionLocal()
    print("=" * 80)
    print("STAGE 2C.2 CONTROLLED RECOVERY EXECUTION")
    print("=" * 80)

    # 1. Pre-Recovery Metrics
    pre_sla = get_freshness_sla_metrics(db)
    print("\n--- PRE-RECOVERY SLA METRICS ---")
    print(json.dumps(pre_sla, indent=2))

    # 2. Run Controlled Ingestion Cycle
    print("\n--- EXECUTING CONTROLLED INGESTION CYCLE ---")
    ingestion_start = datetime.now(timezone.utc)
    ing_res = run_ingestion_cycle(db=db)
    ingestion_duration = (datetime.now(timezone.utc) - ingestion_start).total_seconds()
    print(f"Ingestion Result (Duration: {ingestion_duration:.2f}s):")
    print(json.dumps(ing_res, indent=2))

    # 3. Post-Ingestion Fresh Queue Inspection
    post_ing_sla = get_freshness_sla_metrics(db)
    print("\n--- POST-INGESTION SLA METRICS ---")
    print(f"Fresh Queue Count:   {post_ing_sla['fresh_queue_count']}")
    print(f"Backlog Queue Count: {post_ing_sla['backlog_queue_count']}")
    print(f"Ingestion Status:    {post_ing_sla['ingestion_status']}")
    print(f"Minutes Since Ingestion: {post_ing_sla['minutes_since_ingestion']} min")

    # 4. Run Controlled AI Cycle
    print("\n--- EXECUTING CONTROLLED AI PROCESSING CYCLE ---")
    ai_start = datetime.now(timezone.utc)
    ai_res = run_ai_cycle(db=db)
    ai_duration = (datetime.now(timezone.utc) - ai_start).total_seconds()
    print(f"AI Cycle Result (Duration: {ai_duration:.2f}s):")
    print(json.dumps(ai_res, indent=2))

    # 5. Post-AI SLA Metrics
    post_ai_sla = get_freshness_sla_metrics(db)
    print("\n--- FINAL POST-RECOVERY SLA METRICS ---")
    print(json.dumps(post_ai_sla, indent=2))

    db.close()

if __name__ == "__main__":
    execute_recovery()
