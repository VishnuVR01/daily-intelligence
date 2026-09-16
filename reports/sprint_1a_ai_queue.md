# Sprint 1 Stage 1A — Safe AI Processing Queue Report

## Executive Summary
Sprint 1 Stage 1A introduces a deterministic, safe, local-first **AI Processing Queue** for Daily Intelligence. The AI queue completely decouples article ingestion from Ollama AI inference, ensuring that AI processing delays, timeouts, offline states, or invalid JSON parsing failures **never** impact article ingestion, corrupt raw source provenance, modify canonical URLs, delete articles, or block subsequent ingestion runs.

---

## 1. Final Queue Architecture

```
SOURCES
   ↓
INGESTION PIPELINE
   ↓
POSTGRESQL ARTICLE ARCHIVE (articles table)
   ↓
AI PROCESSING QUEUE (repositories/ai_outputs.py & repositories/ai_queue.py)
   │  - SELECT FOR UPDATE SKIP LOCKED
   │  - Transaction 1: Mark status='processing' and COMMIT
   ↓
OLLAMA INFERENCE SERVICE (services/ai/ollama.py)
   │  - HTTP call executed with NO open DB transaction
   ↓
ARTICLE AI OUTPUT PERSISTENCE (services/ai/worker.py)
   │  - Transaction 2: Store final result and COMMIT
   ↓
DAILY EDITION / HISTORICAL SEARCH / RAG v1.1
```

---

## 2. Actual State Mapping

Queue states map natively onto the existing `Article` and `ArticleAIOutput` tables without schema modifications:

| Conceptual State | `ArticleAIOutput` Column Values | Description |
|---|---|---|
| **`UNPROCESSED`** | No `ArticleAIOutput` record for `(article_id, provider, model, task, prompt_version)` | Article has been ingested into the archive but AI analysis has not been attempted. |
| **`PROCESSING`** | `status = "processing"` | Article has been safely claimed by a worker; inference in progress. |
| **`COMPLETED_RELEVANT`** | `status = "success"`, `is_relevant = True` | AI analysis completed and article passed scope classification. |
| **`COMPLETED_OUT_OF_SCOPE`** | `status = "out_of_scope"` or `is_relevant = False` | AI analysis completed; article rejected as routine/out of scope. |
| **`FAILED`** | `status` in (`"failed"`, `"invalid_json"`, `"timeout"`, `"unavailable"`) | AI analysis attempted but failed due to network error, HTTP error, timeout, or schema parsing error. |
| **`RETRYABLE`** | `status` in failed statuses & `processed_at < (now - cooldown)` OR stale `processing < (now - 15m)` | Failed or stale article eligible for deterministic retry after cooldown. |

---

## 3. Database Migration Verdict
**NO SCHEMA MIGRATION WAS REQUIRED.**
Reused existing `articles` and `article_ai_outputs` tables. Preserved 100% backward compatibility across all queries.

---

## 4. Exact Retry Behaviour Implemented
- **No Invented Attempt Counters**: As instructed by Amendment 1, no artificial attempt counter fields were introduced.
- **Timestamp Cooldown**: A `FAILED` output record becomes eligible for retry after a configurable cooldown period (`cooldown_seconds = 300` default: 5 minutes) based on `processed_at`.
- **Stale Lock Recovery**: A `PROCESSING` record whose lock has been held longer than `stale_processing_seconds = 900` (15 minutes) is automatically reclaimed.
- **Stage 1B Requirement**: Durable per-article attempt limits (`max_retries = 3`) requiring a schema migration are formally deferred to Stage 1B.

---

## 5. Concurrency & Idempotency Safeguards
- **Row-Level Locking**: Claim queries execute `SELECT ... FOR UPDATE SKIP LOCKED` on PostgreSQL to allow concurrent workers to claim disjoint article sets safely without lock contention.
- **Unique Constraint Safeguard**: The existing database unique constraint `uix_article_ai_output_provider_model_task_version` on `(article_id, provider, model, task, prompt_version)` serves as the final concurrency safeguard.
- **Race Condition Handling**: If a race condition occurs between workers attempting to insert/claim the same tuple, the worker catches `IntegrityError`, executes `db.rollback()`, treats the article as `ALREADY CLAIMED`, and continues safely.
- **Transaction Separation**: Inference calls run cleanly outside database transaction boundaries.

---

## 6. Deterministic Queue Ordering
- **FIFO Ordering**: Queue claiming strictly prioritizes articles in First-In-First-Out order:
  `Article.collected_at.asc().nullslast(), Article.id.asc()`
- Priority-based queue ranking is explicitly deferred to Stage 1B.

---

## 7. Controlled Test Backlog Results

### Queue Metrics Before & After

| Queue Metric | Before Run | After Run | Delta |
|---|---|---|---|
| **Total Articles** | 4,202 | 4,202 | 0 |
| **Unprocessed (Eligible)** | 4,133 | 4,128 | -5 |
| **Processing (In-Flight)** | 0 | 0 | 0 |
| **Completed Relevant** | 57 | 62 | +5 |
| **Completed Out of Scope** | 11 | 11 | 0 |
| **Failed** | 1 | 1 | 0 |
| **Oldest Unprocessed Timestamp** | `2026-09-12T19:59:48.769776+01:00` | `2026-09-12T19:59:48.775837+01:00` | Advanced |
| **Newest Processed Timestamp** | `2026-09-15T13:56:35.130307+01:00` | `2026-09-15T13:57:33.467529+01:00` | Updated |

---

## 8. Five Controlled Article Results

| Article ID | Source Name | Article Headline | Claim Status | Ollama Status | Final Queue State | Processing Time |
|---|---|---|---|---|---|---|
| **ID 6** | Federal Reserve | *Federal Reserve Board announces approval of application by National We...* | CLAIMED_SUCCESSFULLY | `success` | `COMPLETED_RELEVANT` | 6,894 ms |
| **ID 7** | Federal Reserve | *Federal Reserve Board issues enforcement action with SouthPoint Bancsh...* | CLAIMED_SUCCESSFULLY | `success` | `COMPLETED_RELEVANT` | 6,594 ms |
| **ID 8** | Federal Reserve | *Federal Reserve Board issues enforcement actions with former employee ...* | CLAIMED_SUCCESSFULLY | `success` | `COMPLETED_RELEVANT` | 6,258 ms |
| **ID 9** | Federal Reserve | *Minutes of the Federal Open Market Committee, July 28–29, 2026...* | CLAIMED_SUCCESSFULLY | `success` | `COMPLETED_RELEVANT` | 6,544 ms |
| **ID 10** | Federal Reserve | *Federal Reserve Board issues enforcement action with former employee o...* | CLAIMED_SUCCESSFULLY | `success` | `COMPLETED_RELEVANT` | 5,824 ms |

---

## 9. Direct Verification Audits
- **Duplicate `ArticleAIOutput` Rows Created**: **0**
- **Article Rows Modified by AI Worker**: **0**
- **Source Provenance / Metadata Corruptions**: **0**

---

## 10. Files Created & Modified

### Created Files
- [`repositories/ai_queue.py`](file:///d:/Daily-Intelligence/repositories/ai_queue.py): Queue status metrics, queue depth observability, and timestamp tracking.
- [`services/ai/worker.py`](file:///d:/Daily-Intelligence/services/ai/worker.py): `AIWorker` class and `process_next_batch` worker function with transaction isolation and failure handling.
- [`tests/test_ai_queue.py`](file:///d:/Daily-Intelligence/tests/test_ai_queue.py): 15 comprehensive unit and integration tests.
- [`scratch/run_controlled_backlog_test.py`](file:///d:/Daily-Intelligence/scratch/run_controlled_backlog_test.py): Controlled backlog execution and verification audit script.

### Modified Files
- [`repositories/ai_outputs.py`](file:///d:/Daily-Intelligence/repositories/ai_outputs.py): Added `claim_eligible_articles` with FIFO ordering, `SKIP LOCKED`, and `IntegrityError` race protection.
- [`repositories/articles.py`](file:///d:/Daily-Intelligence/repositories/articles.py): Updated `get_today_ai_context_stats` status handling for queue state accuracy.

---

## 11. Test Suite Results
- **Initial Test Count**: 160 passing tests
- **New Queue Tests Added**: 15 tests
- **Final Pytest Count**: **175 passing tests (0 failures, 0 errors)**

---

## 12. Stage 1B Backlog & Limitations
- **Durable Attempt Count Column**: Stage 1B database migration to add `attempt_count INT DEFAULT 1` to `article_ai_outputs`.
- **Priority Queue Ranking**: Source trust tier / category prioritization for queue claiming.
- **Worker Automation**: Windows Task Scheduler / daemon execution trigger.
