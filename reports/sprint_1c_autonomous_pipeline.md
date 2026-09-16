# Sprint 1 — Stage 1C: Autonomous Ingestion & AI Orchestration Report

## 1. Executive Summary
Stage 1C completes Sprint 1 of the Daily Intelligence platform by establishing an autonomous, decoupled orchestration system for continuous RSS source ingestion and PostgreSQL-backed priority AI article processing. Building on Stage 1A (Safe AI Processing Queue) and Stage 1B (Intelligent Prioritisation & Safe Retry Policy), Stage 1C introduces a lightweight, robust orchestrator and background scheduler without schema migrations, third-party broker dependencies (Celery/Redis/RabbitMQ/Kafka), or risk of task starvation or deadlock.

## 2. Orchestration Architecture
The orchestration system consists of three main layers:
- **Orchestrator Service (`services/orchestrator.py`)**: Defines decoupled cycle runners (`run_ingestion_cycle`, `run_ai_cycle`, `run_pipeline_cycle`) that encapsulate transaction control and error boundaries.
- **Overlap Protection (`services/lock.py`)**: Implements `pipeline_lock` context manager using PostgreSQL `pg_try_advisory_lock` (with SQLite fallback table `pipeline_locks`) to guarantee single-instance execution per task type across CLI runs or scheduled cycles.
- **Scheduler Daemon (`scripts/run_scheduler.py`)**: Operates as a standalone CLI background daemon using `APScheduler` (IntervalTrigger), isolated from Uvicorn web server processes to prevent duplicate execution during code reloads.

```
+-----------------------------------------------------------------------------------+
|                            APScheduler Daemon (run_scheduler.py)                  |
|                                                                                   |
|    +-----------------------------+               +---------------------------+    |
|    | Ingestion Job (Every 30m)   |               | AI Processing Job (10m)   |    |
|    +--------------+--------------+               +-------------+-------------+    |
+-------------------|--------------------------------------------|------------------+
                    |                                            |
                    v                                            v
     +------------------------------+            +-------------------------------+
     |  pg_try_advisory_lock(1001)  |            |  pg_try_advisory_lock(1002)   |
     +--------------+---------------+            +---------------+---------------+
                    | (Acquired)                                 | (Acquired)
                    v                                            v
     +------------------------------+            +-------------------------------+
     |  ingestion.pipeline          |            |  services.ai.worker           |
     |  - Fetch RSS Feeds           |            |  - Bounded Batch (5 articles)  |
     |  - Insert New Articles       |            |  - Max 2 batches per cycle    |
     |  - DB Commit                 |            |  - Priority Queue (P0..P3)    |
     +--------------+---------------+            +---------------+---------------+
                    |                                            |
                    v                                            v
        [ PostgreSQL Articles ]                      [ PostgreSQL AI Outputs ]
```

## 3. Ingestion Isolation & Safety
Ingestion and AI processing operate completely independently:
- **Zero Cross-Failure Impact**: Ollama local inference downtime or network connection timeouts do NOT impact or stall article ingestion.
- **Canonical Deduplication**: Ingestion continues inserting new canonical URL articles into the database regardless of AI processing state.
- **Strict Provenance Integrity**: Ingestion never alters AI outputs, and AI processing never modifies original article source URLs, HTML content, or timestamps.

## 4. AI Queue Draining Strategy
To prevent resource exhaustion and keep inference latency predictable, Stage 1C enforces bounded queue draining per cycle:
- `AI_BATCH_SIZE = 5` (articles claimed per worker iteration via `FOR UPDATE SKIP LOCKED`).
- `AI_MAX_BATCHES_PER_CYCLE = 2` (maximum iterations per scheduled AI cycle, capping max processing at 10 articles per 10-minute cycle).
- If additional unprocessed articles remain after max batches, they wait safely in PostgreSQL for the next cycle without loss or starvation.

## 5. Schedule Configuration & APScheduler Integration
Settings are centrally configured in `app/config.py` and configurable via `.env`:
- `INGESTION_INTERVAL_MINUTES` = 30
- `AI_INTERVAL_MINUTES` = 10
- `AI_BATCH_SIZE` = 5
- `AI_MAX_BATCHES_PER_CYCLE` = 2

`scripts/run_scheduler.py` initializes `APScheduler` with `coalesce=True` and `max_instances=1`, preventing job backlog buildup if cycles take longer than expected.

## 6. Concurrent Execution Protection (Advisory Lock Strategy)
To prevent race conditions across multi-worker or concurrent CLI executions:
- `pg_try_advisory_lock(1001)` guards `ingestion` execution.
- `pg_try_advisory_lock(1002)` guards `ai_processing` execution.
- If a lock cannot be acquired immediately, the runner returns `{"status": "SKIPPED_ALREADY_RUNNING"}` without erroring or blocking.
- Locks auto-release upon transaction/session close and feature a 600-second stale lock fallback mechanism.

## 7. Ollama Offline / Failure Resilience
- Before attempting batch claim and inference, `run_ai_cycle()` checks `services.ai.client.check_health()`.
- If Ollama is offline or unresponsive, `run_ai_cycle()` immediately logs a warning and returns `{"status": "SKIPPED_OLLAMA_UNAVAILABLE"}`.
- Unprocessed articles remain safely queued in PostgreSQL.

## 8. Manual Command Line Controls
Stage 1C provides explicit, developer-friendly one-shot CLI commands:
- `python scripts/run_ingestion_once.py`: Manually triggers a single ingestion cycle.
- `python scripts/run_ai_once.py`: Manually triggers a single bounded AI cycle.
- `python scripts/run_pipeline_once.py`: Executes ingestion followed by AI cycle sequentially.
- `python scripts/run_scheduler.py --once`: Executes all scheduled jobs once and exits.

## 9. Stage 1C Verification & Test Results
- **Unit & Integration Suite**: 20 new comprehensive tests added in `tests/test_ai_orchestration.py`.
- **Full Test Suite**: 212 total tests passing green (100% pass rate).
- **Controlled Automation Verification**: Tests A through E passed successfully:
  - Test A: Single Ingestion Cycle executed clean.
  - Test B: AI Cycle bounded at max 10 articles (2 batches of 5).
  - Test C: Pipeline Cycle combined execution validated.
  - Test D: Overlap lock returned `SKIPPED_ALREADY_RUNNING` under lock contention.
  - Test E: Ollama mock offline resulted in ingestion `COMPLETED` and AI `SKIPPED_OLLAMA_UNAVAILABLE`.

## 10. Complete Sprint 1 Summary (Stages 1A + 1B + 1C)
- **Stage 1A**: Established safe PostgreSQL queue with `FOR UPDATE SKIP LOCKED`, unique constraint idempotency, short claim transactions, and zero provenance mutation.
- **Stage 1B**: Introduced deterministic pre-AI priority scoring (P0-P3), priority aging to prevent starvation, safe cooldown retries for transient errors, and stale processing claim recovery.
- **Stage 1C**: Added autonomous orchestration, advisory overlap locking, configurable bounded draining, APScheduler daemon, manual CLI controls, and 212 verified tests.

## 11. Verification Matrix
| Verification Requirement | Test / Mechanism | Status |
| :--- | :--- | :--- |
| Ingestion / AI Decoupling | `test_ai_orchestration.py` & Test E | PASSED |
| Overlap Protection | Advisory lock + Test D | PASSED |
| Bounded AI Draining | Max 10 articles/cycle + Test B | PASSED |
| Ollama Downtime Isolation | Health check skip + Test E | PASSED |
| Zero Provenance Mutation | Immutable article archive | PASSED |
| Zero Migration Constraint | 0 DB schema changes | PASSED |

## 12. Security & Data Integrity Assessment
- No raw user inputs are executed or passed to SQL dynamically.
- Advisory lock keys (1001, 1002) are isolated within the application namespace.
- No database migrations or column modifications were performed during Sprint 1.

## 13. Known Limitations & Architectural Boundaries
- Priority scoring operates on pre-AI metadata (title, summary, source importance) prior to full Ollama LLM execution.
- Maximum AI processing throughput is bounded by hardware capacity running local Ollama inference (`qwen3.5:4b`).

## 14. Future Recommendations (Sprint 2 Prep)
- Stage 1 autonomous pipeline is complete, verified, and ready for production continuous operation.
- Future work (Sprint 2) can focus on enhanced RAG retrieval, multi-modal ingestion, or advanced editorial UI features.
