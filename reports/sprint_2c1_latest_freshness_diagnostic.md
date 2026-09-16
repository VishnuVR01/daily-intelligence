# Sprint 2 Stage 2C.1 — Latest Briefings Freshness Diagnostic Report

**Diagnostic Date**: September 15, 2026  
**Diagnostic Time**: 20:51:33 Europe/London (19:51:33 UTC)  
**Status**: DIAGNOSTIC COMPLETE — NO CODE FIXES APPLIED (STRICT STOP ENFORCED)  

---

## 1. Executive Diagnostic Summary

A freshness audit was performed to determine why `/latest` ("Latest Briefings") shows its newest visible article as **15:00 BST (US EIA)**, creating an apparent ~5h45m freshness gap at 20:45 BST.

### Proven Root Causes
1. **Primary Root Cause (Ingestion Gap)**: The standalone background scheduler daemon (`scripts/run_scheduler.py`) was not running in the background. The last ingestion cycle completed at **14:21:44 BST**. No new articles have entered PostgreSQL in the last **6.5 hours**.
2. **Secondary Root Cause (AI Backlog & FIFO Queue Priority)**: 3,453 unprocessed articles exist in the backlog. `claim_eligible_articles` prioritizes FIFO (`collected_at ASC`) with an aging bonus (`+2 pts/hour` up to `+50 pts`). As a result, the active AI worker processes historical backlog articles from days ago, leaving all 23 articles collected at 14:19–14:21 BST in an `UNPROCESSED` state.
3. **Test Data Contamination**: 60 test/fixture articles (e.g. Article ID 4463 `"Test Title"`, Source `"Dedupe Test Source"`) are present in the production/canonical PostgreSQL database because unit tests (e.g., `tests/test_stage_1d.py`) instantiated `SessionLocal()` directly and committed records to the canonical DB instead of using an isolated test DB session.

---

## 2. Database Freshness Audit

- **Current Local Timestamp**: `2026-09-15 20:51:33 BST` (`2026-09-15 19:51:33 UTC`)
- **MAX(Article.collected_at)**: `2026-09-15 14:21:44 BST` (`2026-09-15 13:21:44 UTC`)
- **MAX(Article.published_at)**: `2026-09-15 15:00:00 BST` (`2026-09-15 14:00:00 UTC`)
- **Minutes Since Last Collection**: **389.8 minutes** (~6 hours 29 minutes)

### Collection Activity Breakdown
- **Collected in last 30 minutes**: 0
- **Collected in last 1 hour**: 0
- **Collected in last 2 hours**: 0
- **Collected in last 4 hours**: 0
- **Collected since 15:00 BST**: 0

### Newest 10 Articles in PostgreSQL (by `collected_at`)

| Article ID | Source Name | Title | Published (London) | Collected (London) |
|---|---|---|---|---|
| `4493` | TASS World | Clean Arctic volunteers collect 235 tons of waste in Yakutia's 3 districts | 2026-09-15 14:19:25 | 2026-09-15 14:21:44 |
| `4489` | TASS World | Lavrov says Iran settlement progress should be preserved | N/A | 2026-09-15 14:19:41 |
| `4488` | TASS World | EU's purchases of Russian pipeline gas, LNG up in July | N/A | 2026-09-15 14:19:41 |
| `4487` | TASS World | Russia second-largest supplier of LNG to EU by value after US in July | 2026-09-15 14:16:31 | 2026-09-15 14:19:41 |
| `4486` | Rigzone Energy | Shell Acquires PJM Gas Power Plant | 2026-09-15 14:00:01 | 2026-09-15 14:19:38 |
| `4485` | Rigzone Energy | IEA Says Ukraine Strikes Degrade Russian Oil Refining Capacity | 2026-09-15 14:00:01 | 2026-09-15 14:19:38 |
| `4483` | Rigzone Energy | TotalEnergies Plans $10B in Angola Oil Investments | 2026-09-15 14:00:01 | 2026-09-15 14:19:38 |
| `4484` | Rigzone Energy | Oil Posts Biggest Weekly Gain Since July | 2026-09-15 14:00:01 | 2026-09-15 14:19:38 |
| `4482` | Rigzone Energy | Harvester Energy Bags New Malaysian PSC | 2026-09-15 14:00:01 | 2026-09-15 14:19:38 |
| `4481` | Rigzone Energy | Trump Demands Russian Refineries Be Spared | 2026-09-15 14:00:01 | 2026-09-15 14:19:38 |

---

## 3. Source Ingestion & AI Queue Audit

### Source Ingestion Status
- **Status**: **INACTIVE / STOPPED**
- **Last Ingestion Run**: `2026-09-15 14:21:44 BST`
- **Cause**: The background daemon `scripts/run_scheduler.py` is not running in the active workspace execution environment.

### AI Queue Breakdown (Articles Collected Since 15:00 BST)
- **Total Articles**: 0
- **UNPROCESSED**: 0
- **PROCESSING**: 0
- **COMPLETED_RELEVANT**: 0
- **COMPLETED_OUT_OF_SCOPE**: 0
- **FAILED / RETRYABLE**: 0

### Total Database Queue State
- **Total Stored Articles**: 4,486
- **Total AI Outputs**: 1,033
- **Unprocessed Backlog**: 3,453 articles
- **Articles Collected at ~14:20 BST Status**: All 23 articles (IDs 4471–4493) remain `UNPROCESSED`.

### AI Worker Status
- **AI Worker Status**: **ACTIVE** (Processed Output ID 1031 for Article 974 at `20:40:53 BST`).
- **Processing Target**: Currently processing historical backlog from days ago due to `collected_at ASC` FIFO ordering and `+2.0 pts/hour` starvation aging bonus.

---

## 4. End-to-End Trace of 5 Newest Articles in PostgreSQL

| Article ID | Title | Source | Published (London) | Collected (London) | AI State | Relevant | Eligible for `/latest` | Returned by `/latest` | Exclusion / Ranking Reason |
|---|---|---|---|---|---|---|---|---|---|
| `4437` | Corpus Christi LNG expansion makes facility the second-largest in the United States | US EIA | 2026-09-15 15:00:00 | 2026-09-15 14:13:11 | `UNPROCESSED` | `None` | `True` | `True` | Included (Ranked #1 due to `published_at` 15:00:00 BST) |
| `4466` | Grab to buy Singapore-based Atome Financial for $1.49bn | Nikkei Asia | N/A | 2026-09-15 14:19:33 | `UNPROCESSED` | `None` | `True` | `True` | Included |
| `4493` | Clean Arctic volunteers collect 235 tons of waste in Yakutia | TASS World | 2026-09-15 14:19:25 | 2026-09-15 14:21:44 | `UNPROCESSED` | `None` | `True` | `True` | Included |
| `4463` | Test Title | Dedupe Test Source | N/A | 2026-09-15 14:19:12 | `UNPROCESSED` | `None` | `True` | `True` | Included (Test fixture contamination) |
| `4487` | Russia second-largest supplier of LNG to EU by value after US in July | TASS World | 2026-09-15 14:16:31 | 2026-09-15 14:19:41 | `UNPROCESSED` | `None` | `True` | `True` | Included |

---

## 5. `/latest` Query & Mode Comparison

- **Query Semantics**: `get_recent_articles()` queries `Article` with `_valid_published_filter()`, ordered by `coalesce(published_at, collected_at).desc()`.
- **Curated Only**: Defaults to `False` on `/latest`, so unprocessed articles appear on `/latest`.
- **Editorial Balanced Mode**: `apply_editorial_diversity(raw_articles, max_per_source=2, max_items=50)`.
- **Pure Chronological Mode**: `raw_articles[:50]`.

### Comparison Result
- **Newest Article in Editorial Balanced**: ID `4437` (`2026-09-15 15:00:00 BST`)
- **Newest Article in Pure Chronological**: ID `4437` (`2026-09-15 15:00:00 BST`)

*Conclusion: Both modes return the exact same newest article. The 15:00 timestamp is not an artifact of source diversity filtering or query logic, but reflects the true maximum timestamp in PostgreSQL.*

---

## 6. Freshness Metrics Summary

1. **INGESTION FRESHNESS**: **389.8 minutes** (~6h 29m) (`current_time - MAX(collected_at)`)
2. **SOURCE FRESHNESS**: **351.5 minutes** (~5h 51m) (`current_time - MAX(published_at)`)
3. **AI FRESHNESS**: **10.7 minutes** (`current_time - MAX(processed_at)` for relevant articles)
4. **BRIEFING FRESHNESS**: **351.5 minutes** (~5h 51m) (`current_time - newest article on /latest`)

---

## 7. Test / Fixture Contamination Findings

- **Count**: 60 test/fixture articles found in production/canonical database.
- **Example Fixtures**:
  - Article ID `4463`: `"Test Title"`, Source `"Dedupe Test Source"` (Collected 2026-09-15 14:19:12 BST)
  - Source: `"Dedupe Test Source Stage1D"`
- **Root Cause**: Unit tests (such as `tests/test_stage_1d.py`) instantiated `SessionLocal()` directly to perform database assertions instead of using the isolated SQLite test fixture `test_db_session` or an isolated transaction rollback wrapper.

---

## 8. Root Cause Classification Matrix

| Category | Classification | Status | Empirical Evidence |
|---|---|---|---|
| **A** | Source Quiet Period | Partial | Feeds have updated externally, but local ingestion hasn't fetched them. |
| **B** | Ingestion Scheduler Not Running | **PRIMARY** | Daemon `scripts/run_scheduler.py` is stopped; 0 ingestion cycles in last 6.5h. |
| **C** | Ingestion Failure | Excluded | Ingestion code functions when executed; process simply wasn't running. |
| **D** | AI Backlog & Priority Ordering | **SECONDARY** | 3,453 backlog articles; aging bonus + FIFO causes worker to process old backlog first. |
| **E** | AI Worker Not Running | Excluded | AI worker IS running and processing output every 10 mins. |
| **F** | AI Failure | Excluded | AI worker outputs status `success`. |
| **G** | Relevance Filter Effect | Excluded | `/latest` does not filter out unprocessed articles (`curated_only=False`). |
| **H** | Editorial Ranking Effect | Excluded | Both Chronological and Balanced modes yield ID 4437. |
| **I** | `/latest` Query Bug | Excluded | Query correctly orders by `coalesce(published_at, collected_at).desc()`. |
| **J** | Timezone Bug | Excluded | Timestamps cleanly handle UTC/BST conversion. |
| **K** | Cache / UI Staleness | Excluded | Route fetches fresh DB state on every request. |
| **L** | Test Data Contamination | **CONFIRMED** | 60 test articles created by unit tests using `SessionLocal()` exist in production DB. |

---

## 9. Recommended Future Fixes (DO NOT IMPLEMENT YET)

1. **Start Ingestion Scheduler Daemon**: Run `python scripts/run_scheduler.py` in the background (or launch ingestion as an autonomous background process).
2. **Prioritize Fresh Articles in AI Queue**: Adjust `claim_eligible_articles` priority scoring to add a **Recency Boost** for newly collected articles (e.g. collected in the last 2 hours) so fresh articles jump ahead of 3,000+ historical backlog items.
3. **Isolate Unit Tests from Production DB**: Enforce that all tests in `tests/` use `test_db_session` or an isolated test database, preventing `SessionLocal()` calls from committing test fixtures (`"Test Title"`, `"Dedupe Test Source"`) to the production database. Clean up extant test fixture records from canonical DB.
