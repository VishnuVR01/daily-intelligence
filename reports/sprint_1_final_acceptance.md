# Sprint 1 — Autonomous Pipeline Acceptance

## Stage 1A
Safe AI Queue

PASS

## Stage 1B
Prioritisation & Retry

PASS

## Stage 1C
Autonomous Orchestration

PASS

## Stage 1D
Source Health & Soak Test

PASS

---

## Detailed Acceptance Metrics & Operational Audit

### Source Infrastructure
- **Sources Configured**: 50
- **Sources Healthy**: 43 (86.0%)
- **Sources Problematic**: 0 Failed, 3 Stale (>7 days old content), 4 Empty (0 items returned)
- **Rigzone Repair Status**: REPAIRED (ID 75, `https://www.rigzone.com/news/rss/rigzone_latest.aspx` ingesting 20 fresh energy articles per fetch via updated `User-Agent: Mozilla/5.0`)

### Database & Article Archive
- **Articles Currently Archived**: 4,458 permanent canonical articles
- **Schema Migrations**: 0 (Strict constraint maintained across all Sprint 1 stages)

### AI Queue Breakdown
- **Unprocessed Articles**: 4,324
- **Processing Articles**: 0 (0 stuck in processing state)
- **Completed Relevant Articles**: 122
- **Completed Out-of-Scope (OOS) Articles**: 11
- **Failed / Retryable Articles**: 1 (cooldown active, zero permanent discard)
- **Processing Coverage**: 3.01% (134 / 4,458 total articles)

### Pipeline Performance & Throughput Audit
- **Ingestion Throughput**: ~3,600 articles checked per hour (Inserting ~5-15 new articles / hour depending on RSS publisher velocity)
- **AI Throughput**: 60 articles processed per hour (`AI_BATCH_SIZE=5`, `AI_MAX_BATCHES_PER_CYCLE=2`, 10-minute cycle interval)
- **Backlog Trend**: STABLE / DECREASING (AI processing capacity of 60 art/hr comfortably exceeds typical RSS publisher new article velocity of 5-15 new art/hr)
- **Backlog Growth Risk**: NO RISK (AI throughput > Ingestion new article insertion rate)

### Invariants Verification Audit (9 / 9 Passed)
- **Duplicate Canonical Article Insertion**: 0 (Enforced by UNIQUE constraint on `canonical_url`)
- **Duplicate ArticleAIOutput Rows**: 0 (Enforced by UNIQUE constraint on `article_id` + composite keys)
- **Article Provenance Corruption**: 0 (Zero modification of `source_id`, `canonical_url`, or `title`)
- **Source Provenance Corruption**: 0 (Zero mutation of configured source metadata)
- **Overlapping Same-Job Execution**: 0 (Guarded by PostgreSQL `pg_try_advisory_lock` keys 1001 & 1002)
- **Stuck PROCESSING Records**: 0 (Automated 15-minute stale-processing claim recovery)
- **Unexpected Scheduler Termination**: 0 (APScheduler running with `coalesce=True`, `max_instances=1`)
- **Unhandled Worker Exceptions**: 0 (Per-article try/except boundary protection)
- **Database Integrity Violations**: 0

### Operational Resilience Status
- **Scheduler Status**: PASS (`scripts/run_scheduler.py` isolated from Uvicorn reload)
- **Overlap Protection Status**: PASS (Advisory locks 1001/1002 return `SKIPPED_ALREADY_RUNNING`)
- **Ollama Recovery Status**: PASS (Offline status returns `SKIPPED_OLLAMA_UNAVAILABLE`; auto-resumes processing without manual database repair when online)

### Test Suite Execution Result
- **Final Pytest Result**: 227 / 227 tests PASSED (100% green pass rate)

---

## Known Limitations & Boundaries
1. **Ollama Local Hardware Bound**: AI inference speed is bound by local GPU/CPU running `qwen3.5:4b`. Bounded cycle draining (10 articles per 10m cycle) ensures system stability.
2. **Pre-AI Priority Scoring**: Priority tiers (P0-P3) operate on pre-AI metadata (title, summary, source trust tier) prior to full LLM processing.
3. **SQLite Fallback Lock Scope**: On PostgreSQL environments, true session-level advisory locks operate at the database connection level. On local SQLite environments, `pipeline_locks` table fallback provides table-level transaction locking.

---

## Sprint 1 Definition of Done Checklist

| Definition of Done Criterion | Result | Status |
| :--- | :---: | :---: |
| PASS — ingestion runs independently | Verified | **PASS** |
| PASS — AI worker runs independently | Verified | **PASS** |
| PASS — queue prioritisation works | Verified | **PASS** |
| PASS — failures are isolated | Verified | **PASS** |
| PASS — retries/cooldowns behave safely | Verified | **PASS** |
| PASS — overlapping jobs are prevented | Verified | **PASS** |
| PASS — articles are never lost due to AI failure | Verified | **PASS** |
| PASS — duplicate AI outputs remain zero | Verified | **PASS** |
| PASS — provenance remains intact | Verified | **PASS** |
| PASS — source health is observable | Verified | **PASS** |
| PASS — scheduler survives controlled multi-cycle execution | Verified | **PASS** |
| PASS — Ollama recovery requires no manual database repair | Verified | **PASS** |
| PASS — full test suite passes (227/227) | Verified | **PASS** |

**SPRINT 1 STATUS: COMPLETE**
