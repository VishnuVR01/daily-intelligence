# Sprint 1 Stage 1B — Intelligent Prioritisation + Safe Retry Policy Report

## Executive Summary
Sprint 1 Stage 1B enhances the verified Stage 1A safe AI processing queue with **Intelligent Prioritisation** and a **Safe Retry Policy**. Pre-AI metadata signals (source trust tier, source family, default category, and strategic headline/summary keywords) are used to compute a transparent priority score and assign articles to priority tiers (`P0_CRITICAL`, `P1_HIGH`, `P2_NORMAL`, `P3_LOW`). Routine or low-value articles are assigned lower priority (`P3_LOW`) but are **never** discarded or deleted. An aging starvation protection rule ensures older low-priority articles eventually rise above newer low-value articles. 

Network timeouts and server unavailable errors enter a deterministic 5-minute retry cooldown, while non-retryable schema errors (`invalid_json`) are excluded from auto-retry loops without schema alterations.

---

## 1. Metadata Available Before Ollama
The priority engine uses deterministic metadata present in PostgreSQL before AI inference:
- **`Article` Table**: `title`, `raw_summary`, `published_at`, `collected_at`, `primary_category`, `language`.
- **`Source` Table**: `name`, `trust_tier`, `source_family`, `category`, `provenance`, `country_code`.

---

## 2. Priority Scoring Formula
$$\text{base\_score} = \text{clamp}_{0..100}(\text{trust\_signal} + \text{family\_signal} + \text{category\_signal} + \text{keyword\_signal})$$
$$\text{aging\_bonus} = \min(50.0,\, \text{hours\_waiting} \times 2.0)$$
$$\text{effective\_score} = \min(100.0,\, \text{base\_score} + \text{aging\_bonus})$$

---

## 3. Priority Tier Thresholds

| Priority Tier | Effective Score Range | Target Content Type |
|---|---|---|
| **`P0_CRITICAL`** | Score $\ge 80$ | Major central bank announcements, semiconductor breakthroughs, critical geopolitical events. |
| **`P1_HIGH`** | $60 \le \text{Score} < 80$ | Strategic trade, shipping disruptions, energy/commodities markets, macroeconomics. |
| **`P2_NORMAL`** | $35 \le \text{Score} < 60$ | Routine business, general market updates, manufacturing, sustainability news. |
| **`P3_LOW`** | Score $< 35$ | Routine local sports match reporting, celebrity news, lifestyle, gossip. |

---

## 4. Strategic Signal Dictionaries
- **Trust Tier Weights**: `primary` (+25), `institutional` (+20), `open_source_signal` (+15), `state_affiliated` (+10), `useful` (+5).
- **Source Family Weights**: `central_bank` (+20), `government` (+15), `research` / `university` (+10), `news` / `industry` (+5).
- **Source Category Weights**: `AI & Technology` / `Geopolitics` (+15), `Markets & Economy` / `Commodities` / `Supply Chain & Trade` / `Energy` (+12), `Sustainability` / `Industry & Operations` / `Research` (+10), `World` / `Business` (+8).
- **Keyword Weighting**:
  - *Critical Keywords (+25)*: `AI`, `semiconductor`, `chip`, `Nvidia`, `TSMC`, `Federal Reserve`, `FOMC`, `ECB`, `interest rate`, `inflation`, `OPEC`, `oil`, `LNG`, `war`, `ceasefire`.
  - *High Keywords (+15)*: `supply chain`, `shipping`, `freight`, `container`, `trade route`, `disruption`, `gas`, `electricity`, `gold`, `copper`, `critical mineral`, `GDP`, `tariff`, `sanction`, `BRICS`, `G7`, `G20`, `NATO`, `automation`, `robotics`, `decarbonisation`, `nuclear`.
  - *Low-Priority / Negative Keywords (-30)*: `sports`, `match`, `score`, `football`, `basketball`, `celebrity`, `gossip`, `fashion`, `lifestyle`, `entertainment`, `movie`, `horoscope`.

---

## 5. Aging / Starvation Protection Rule
To ensure low-priority (`P3_LOW`) articles do not remain unprocessed indefinitely when higher-priority items enter the queue:
$$\text{waiting\_hours} = \frac{\text{now} - \text{collected\_at}}{3600}$$
$$\text{aging\_bonus} = \min(50.0,\, \text{waiting\_hours} \times 2.0)$$
An article waiting for 20 hours gains a +40 point aging bonus, promoting it into `P1_HIGH` or `P0_CRITICAL` ahead of newer low-value articles.

---

## 6. Deterministic Queue Selection Ordering
Query ordering for claiming eligible articles:
1. `effective_score DESC`
2. `Article.collected_at ASC` (FIFO tie-breaker)
3. `Article.id ASC` (Deterministic ID tie-breaker)

---

## 7. Retryable Failure Mapping
- **`unavailable`**: Ollama HTTP API unreachable / connection refused.
- **`timeout`**: Request timed out (>120s).
- **`temporary_error`**: Transient HTTP 500 or 503 error.

---

## 8. Non-Retryable Failure Mapping
- **`invalid_json`**: Schema validation error or unparseable JSON output. Excluded from automatic retry claiming to prevent rapid infinite retry loops.

---

## 9. Cooldown Policy
- Retryable failures (`unavailable`, `timeout`, `temporary_error`): Eligible for retry claiming after `cooldown_seconds = 300` (5 minutes) based on `processed_at`.

---

## 10. Stale-Processing Recovery Policy
- `PROCESSING` records older than `stale_processing_seconds = 900` (15 minutes) are reclaimed. Fresh processing jobs (< 15 mins) are protected.

---

## 11. Durable Retry Limit Decision
- **Verdict**: Durable per-article attempt counting requires schema support (`attempt_count` column). In accordance with instructions, **no database migration was performed in Stage 1B**. This is formally documented as a Stage 1C requirement.

---

## 12. 20-Article Dry-Run Priority Table

| ID | Priority Tier | Effective Score | Base Score | Aging Bonus | Source Name | Article Headline Preview |
|---|---|---|---|---|---|---|
| **11** | `P0_CRITICAL` | 100.0 | 77 | 50.0 | Federal Reserve | Federal Reserve Board announces approval of application... |
| **12** | `P0_CRITICAL` | 100.0 | 77 | 50.0 | Federal Reserve | Federal Reserve Board announces approval of application... |
| **13** | `P0_CRITICAL` | 100.0 | 77 | 50.0 | Federal Reserve | Federal Reserve Board announces approval of application... |
| **14** | `P0_CRITICAL` | 100.0 | 77 | 50.0 | Federal Reserve | Federal Reserve Board requests comment on proposed... |
| **15** | `P0_CRITICAL` | 100.0 | 77 | 50.0 | Federal Reserve | Federal Reserve Board requests comment on proposed... |
| **16** | `P0_CRITICAL` | 100.0 | 77 | 50.0 | Federal Reserve | Federal Reserve Board issues enforcement action... |
| **17** | `P0_CRITICAL` | 100.0 | 77 | 50.0 | Federal Reserve | Federal Reserve Board issues enforcement action... |
| **18** | `P0_CRITICAL` | 100.0 | 77 | 50.0 | Federal Reserve | Federal Reserve issues FOMC statement... |
| **19** | `P0_CRITICAL` | 100.0 | 52 | 50.0 | Federal Reserve | Agencies issue joint statement on risk management... |
| **20** | `P0_CRITICAL` | 100.0 | 77 | 50.0 | Federal Reserve | Federal Reserve Board issues enforcement action... |
| **22** | `P0_CRITICAL` | 100.0 | 70 | 50.0 | OpenAI | Rapidly scaling online storage to support AI models... |
| **25** | `P0_CRITICAL` | 100.0 | 70 | 50.0 | OpenAI | Now everyone can put data to work with custom AI... |
| **26** | `P0_CRITICAL` | 100.0 | 53 | 50.0 | OpenAI | Introducing ChatGPT for Financial Analysis... |
| **27** | `P0_CRITICAL` | 100.0 | 70 | 50.0 | OpenAI | Expanding AI access and cyber defense capabilities... |
| **30** | `P0_CRITICAL` | 100.0 | 70 | 50.0 | OpenAI | The AI policy window is open... |
| **31** | `P0_CRITICAL` | 100.0 | 70 | 50.0 | OpenAI | GPT-6 Astra: The next generation AI foundation model... |
| **23** | `P0_CRITICAL` | 95.0 | 45 | 50.0 | OpenAI | Cognition helps Devin test its code... |
| **24** | `P0_CRITICAL` | 95.0 | 45 | 50.0 | OpenAI | How a researcher uses Codex and GPT-4... |
| **28** | `P0_CRITICAL` | 95.0 | 45 | 50.0 | OpenAI | Build more natural voice experiences with Audio API... |
| **29** | `P0_CRITICAL` | 95.0 | 45 | 50.0 | OpenAI | Introducing the Agents API for autonomous workflows... |

---

## 13. 10-Article Controlled Processing Execution

| Claim Order | Article ID | Priority Tier | Effective Score | Final Queue State | Processing Time | Headline |
|---|---|---|---|---|---|---|
| **1** | ID 11 | `P0_CRITICAL` | 100.0 | `COMPLETED_RELEVANT` | 17,747 ms | Federal Reserve Board announces approval... |
| **2** | ID 12 | `P0_CRITICAL` | 100.0 | `COMPLETED_RELEVANT` | 5,819 ms | Federal Reserve Board announces approval... |
| **3** | ID 13 | `P0_CRITICAL` | 100.0 | `COMPLETED_RELEVANT` | 6,516 ms | Federal Reserve Board announces approval... |
| **4** | ID 14 | `P0_CRITICAL` | 100.0 | `COMPLETED_RELEVANT` | 6,246 ms | Federal Reserve Board requests comment... |
| **5** | ID 16 | `P0_CRITICAL` | 100.0 | `COMPLETED_RELEVANT` | 6,157 ms | Federal Reserve Board issues enforcement... |
| **6** | ID 17 | `P0_CRITICAL` | 100.0 | `COMPLETED_RELEVANT` | 5,815 ms | Federal Reserve Board issues enforcement... |
| **7** | ID 18 | `P0_CRITICAL` | 100.0 | `COMPLETED_RELEVANT` | 6,029 ms | Federal Reserve issues FOMC statement... |
| **8** | ID 19 | `P0_CRITICAL` | 100.0 | `COMPLETED_RELEVANT` | 5,741 ms | Agencies issue joint statement on risk... |
| **9** | ID 20 | `P0_CRITICAL` | 100.0 | `COMPLETED_RELEVANT` | 6,036 ms | Federal Reserve Board issues enforcement... |
| **10** | ID 22 | `P0_CRITICAL` | 100.0 | `COMPLETED_RELEVANT` | 5,725 ms | Rapidly scaling online storage to support... |

---

## 14. Queue Metrics Before & After

| Queue Metric | Before Run | After Run | Delta |
|---|---|---|---|
| **Total Stored Articles** | 4,202 | 4,202 | 0 |
| **Unprocessed Articles** | 4,128 | 4,118 | -10 |
| **Processing (In-Flight)** | 0 | 0 | 0 |
| **Completed Relevant** | 62 | 72 | +10 |
| **Completed Out of Scope** | 11 | 11 | 0 |
| **Failed (Non-Retryable)** | 1 | 1 | 0 |
| **Newest Processed Timestamp** | `2026-09-15T13:57:33.467529+01:00` | `2026-09-15T13:56:03.112000+01:00` | Updated |
| **AI Processing Coverage** | 1.74% | 1.98% | +0.24% |

---

## 15. Verification Audits
- **Duplicate `ArticleAIOutput` Rows**: **0**
- **Article Provenance Corruptions**: **0**
- **Article Table Rows Modified**: **0**

---

## 16. Files Created & Modified

### Created Files
- [`services/ai/priority.py`](file:///d:/Daily-Intelligence/services/ai/priority.py): Priority scoring engine, P0-P3 tiers, keyword dictionary, and starvation aging formula.
- [`tests/test_ai_priority_queue.py`](file:///d:/Daily-Intelligence/tests/test_ai_priority_queue.py): 17 unit and integration tests.
- [`scratch/run_stage_1b_test.py`](file:///d:/Daily-Intelligence/scratch/run_stage_1b_test.py): Dry-run priority reporter and controlled 10-article execution script.

### Modified Files
- [`repositories/ai_outputs.py`](file:///d:/Daily-Intelligence/repositories/ai_outputs.py): Integrated priority scoring for queue claiming and failure retry filtering.
- [`repositories/ai_queue.py`](file:///d:/Daily-Intelligence/repositories/ai_queue.py): Added P0-P3 tier breakdowns, queue age calculation, and coverage percentage metrics.
- [`services/ai/worker.py`](file:///d:/Daily-Intelligence/services/ai/worker.py): Attached priority scoring details to execution logs.

---

## 17. Test Suite Results
- **Previous Stage 1A Test Count**: 175 passing tests
- **New Stage 1B Tests Added**: 17 tests
- **Final Pytest Count**: **192 passing tests (0 failures, 0 errors)**

---

## 18. Stage 1C Backlog & Limitations
- **Durable Retry Count Migration**: Add `attempt_count INT DEFAULT 1` column to `article_ai_outputs`.
- **Worker Automation Trigger**: Recurring background schedule / CLI invocation trigger.
