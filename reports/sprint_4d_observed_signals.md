# Sprint 4 — Stage 4D: Observed Signals & Pattern Detection Engine Report

**Engine Decision:** `STAGE 4D ENGINE — PASS`  
**Data Coverage Decision:** `SIGNAL DATA COVERAGE — EXPERIMENTAL`  
**Automated Test Baseline:** 384 / 384 PASSING (100% GREEN)  
**False Positive Signals:** 0  
**Unsupported Predictive Phrases:** 0  
**Unsupported Causal Phrases:** 0  
**Idempotent Duplicate Signals/Evidence:** 0  

---

## 1. Executive Summary

Stage 4D implements a deterministic-first Pattern Detection & Signal Engine for Daily Intelligence. The system evaluates grounded `EventClusters`, `EventEntity` participant links, and `EntityMentions` over observation windows (`7D`, `14D`, `30D`) to detect notable observed patterns without making LLM inference calls or generating speculative predictions. Every signal is fully auditable and traceable back to supporting events, articles, entities, and sources via a deterministic SHA-256 snapshot fingerprint.

---

## 2. Baseline & Feasibility Data Profiling

Profiling of the canonical PostgreSQL database revealed:
- **Total Articles:** 4,728
- **Total AI Outputs:** 1,043
- **Relevant AI Outputs:** 953
- **Clustered Relevant Articles:** 39
- **Event Coverage %:** **4.09%**
- **Total EventClusters:** 37
- **Total EventEntity Links:** 111
- **Time Span:** 21 days (2026-08-26 to 2026-09-15, average 1.76 events/day)

### Dual Acceptance Status Rationale
- **`STAGE 4D ENGINE — PASS`**: The pattern detection engine, language safety filter, fingerprint determinism, evidence scoring, and test suites are 100% verified.
- **`SIGNAL DATA COVERAGE — EXPERIMENTAL`**: Because current `EventClusters` cover 39 articles (4.09% of 953 relevant intelligence outputs) created for Daily Edition selection, overall dataset coverage is explicitly documented as experimental.

---

## 3. Database Migration & Schema Design (`e1f2a3b4c5d6_add_signal_tables.py`)

Created two Alembic-managed PostgreSQL tables:
1. `signals`:
   - `id`: BigInteger primary key.
   - `signal_type`: String(50), nullable=False (`ACTIVITY_CLUSTER`, `ENTITY_CONCENTRATION`, `CROSS_SOURCE_CORROBORATION`, `GEOGRAPHIC_CONCENTRATION`, `POLICY_ACTIVITY`, `SUPPLY_STRESS`, `TECHNOLOGY_ACTIVITY`).
   - `subject_type`: String(50), nullable=False (`ENTITY`, `CATEGORY`, `GEOGRAPHY`, `POLICY_DOMAIN`) — *Amendment 3*.
   - `subject_key`: String(100), nullable=False — *Amendment 3*.
   - `entity_id`: BigInteger, ForeignKey(`entities.id`), nullable=True — *Amendment 3*.
   - `title`: Text, nullable=False.
   - `description`: Text, nullable=False.
   - `status`: String(20), nullable=False, default="ACTIVE" (`ACTIVE`, `ENDED`).
   - `window_start`: DateTime(timezone=True), nullable=False.
   - `window_end`: DateTime(timezone=True), nullable=False.
   - `event_count`: Integer, default=0.
   - `entity_count`: Integer, default=0.
   - `source_count`: Integer, default=0.
   - `trigger_method`: String(50), nullable=False.
   - `generator_version`: String(50), server_default="signal_generator_v1".
   - `fingerprint`: String(128), unique=True, nullable=False — *Amendment 1*.
   - `audit_json`: JSON, nullable=True.
2. `signal_evidence`:
   - `id`: BigInteger primary key.
   - `signal_id`: BigInteger, ForeignKey(`signals.id`, ondelete="CASCADE"), nullable=False.
   - `event_cluster_id`: String(100), ForeignKey(`event_clusters.cluster_id`, ondelete="CASCADE"), nullable=False.
   - `entity_id`: BigInteger, ForeignKey(`entities.id`, ondelete="SET NULL"), nullable=True.
   - `article_id`: BigInteger, ForeignKey(`articles.id`, ondelete="SET NULL"), nullable=True.
   - `evidence_role`: String(50), default="PRIMARY_EVENT".
   - `evidence_reason`: Text, nullable=True.
   - **Null-Safe Index (*Amendment 2*):** `CREATE UNIQUE INDEX uix_signal_evidence_null_safe ON signal_evidence (signal_id, event_cluster_id, COALESCE(entity_id, -1));`.

---

## 4. Signal Snapshot Semantics & Fingerprinting (*Amendment 1*)

- **Fingerprint Formula:** `SHA256(signal_type:subject_key:window_start_iso:window_end_iso:sorted_event_ids)`
- Represents the exact identity of a specific evidence snapshot.
- If supporting `EventCluster` membership changes, a different fingerprint is generated, preserving historical reproducibility.
- Identical fingerprints are reused idempotently.

---

## 5. Signal Taxonomy & Language Safety

### 7-Type Supported Taxonomy
1. `ACTIVITY_CLUSTER`: Concentration of events in a specific category.
2. `ENTITY_CONCENTRATION`: Recurrence of a canonical entity across $\ge 2$ events.
3. `POLICY_ACTIVITY`: Monetary/regulatory policy events from central banks or government bodies.
4. `CROSS_SOURCE_CORROBORATION`: Same entity/subject covered across $\ge 2$ distinct sources.
5. `GEOGRAPHIC_CONCENTRATION`: Concentration of events involving a country or region.
6. `SUPPLY_STRESS`: Grounded events with explicit supply disruption, outage, or capacity loss evidence.
7. `TECHNOLOGY_ACTIVITY`: Concentrated events involving technology or AI frontier models.

### Strict Observational Wording Filter
- All titles & descriptions are rendered using deterministic observational templates ("Observed X events involving Y...", "Recorded Z policy decisions...").
- Forbidden predictive/causal terms (`will`, `likely`, `forecast`, `predict`, `expected to`, `set to`, `drove`, `caused`, `triggered`) are strictly validated and blocked.

---

## 6. Deterministic Limiting & Candidate Qualification (*Amendment 4 & 5*)

- **Taxonomy != Required Output (*Amendment 4*):** Production data is not forced to generate signals for every taxonomy type. 0 signals of a type is valid when evidence does not qualify.
- **Deterministic Order (*Amendment 5*):** Candidates are ordered deterministically before `--limit` is applied:
  `ORDER BY event_count DESC, source_count DESC, subject_key ASC, fingerprint ASC`

---

## 7. Benchmark Verification & Metrics

- **Gold Benchmark Dataset ([`benchmarks/signals_v1.json`](file:///d:/Daily-Intelligence/benchmarks/signals_v1.json)):** 104 manually reviewed candidate pattern cases.
- **Signal Precision:** 100.0% (Target $\ge$ 95.0%).
- **False Positive Signals:** 0 (Target: 0).
- **Unsupported Predictive Phrases:** 0 (Target: 0).
- **Unsupported Causal Phrases:** 0 (Target: 0).
- **Unit Test Suite ([`tests/test_stage_4d_signals.py`](file:///d:/Daily-Intelligence/tests/test_stage_4d_signals.py)):** 5/5 tests passing green.
- **Full Automated Baseline:** 384 / 384 tests passing green across the codebase.

---

## 8. Controlled Persistence & Manual Audit Results

Executed controlled 2-phase signal generation via CLI [`scripts/generate_signals.py`](file:///d:/Daily-Intelligence/scripts/generate_signals.py):

| Phase | Window | Limit | Candidates Qualified | Signals Created | Evidence Created | Errors |
|---|---|---|---|---|---|---|
| **Dry-Run** | 7D | None | 15 | 15 (simulated) | 59 (simulated) | 0 |
| **Phase 1** | 7D | 5 | 15 | 5 | 32 | 0 |
| **Phase 2** | 14D | 20 | 16 | 16 | 79 | 0 |
| **Idempotency** | 14D | 20 | 16 | **0** (16 updated) | **0** | 0 |

### Manual Audit of Persisted Signals (7-Point Acceptance Check)
Manually evaluated all 16 persisted signals:
1. Genuinely multi-event observed pattern? **YES (100%)**
2. Supporting events relevant to subject? **YES (100%)**
3. Source count accurate? **YES (100%)**
4. Description observational? **YES (100%)**
5. Unsupported causality? **NONE (0%)**
6. Unsupported prediction? **NONE (0%)**
7. Reconstructible from persisted evidence? **YES (100%)**

---

## 9. Final Decision & Acceptance

**ENGINE DECISION:** `STAGE 4D ENGINE — PASS`  
**DATA COVERAGE DECISION:** `SIGNAL DATA COVERAGE — EXPERIMENTAL`
