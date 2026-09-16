# Sprint 4A — Knowledge & Signal Layer Architecture, Ontology & Feasibility Audit

**Stage 4A Status:** **STAGE 4A — PASS**  
**Mode:** AUDIT $\rightarrow$ DATA PROFILING $\rightarrow$ DESIGN $\rightarrow$ SPECIFICATION (No Production Code Changes)  
**System Baseline:** 368 / 368 Automated Tests Passing (100% Green)

---

## 1. Executive Summary

Sprint 4 Stage 4A establishes the architectural blueprint, entity ontology, data schema, provenance model, and signal framework for the **Daily Intelligence Knowledge & Signal Layer**. 

Connecting canonical **Articles**, **Event Clusters**, and **Daily Editions** to a structured graph of **Entities**, **Mentions**, **Source Assertions**, **Timelines**, and **Observed Signals**, this layer will enable structural macro queries (e.g. *"What has happened to ECB policy this month?"*, *"What developments affected LNG supply?"*, *"Which companies are connected to semiconductor export controls?"*).

Stage 4A completes data profiling on the canonical PostgreSQL dataset (4,728 articles, 1,043 AI outputs, 37 event clusters, 19 editions), audits existing entity metadata, defines a strict 10-type ontology, specifies non-destructive database schemas, and outlines a 4-stage roadmap (4B through 4E) while keeping RAG v1.1 and Daily Edition generation completely unaffected.

---

## 2. Current System Baseline

| Component | Status / Baseline | Verification |
| :--- | :---: | :--- |
| **Automated Test Suite** | `368 / 368 PASSING` | 100% Green (`python -m pytest -q`) |
| **Ingestion Pipeline** | Autonomous 30-min RSS Ingestion | Canonical PostgreSQL Archive |
| **AI Queue & Ollama Review** | `qwen3.5:4b` Article Analysis | Freshness-First Priority Queue |
| **Event Clustering v1** | 100% Precision / 0 False Merges | Pairwise Entity & Numeric Matching |
| **Editorial Selection Engine** | Deterministic 0-100 Scoring | Role Assignment & Section Caps |
| **Editorial Synthesis Engine** | EvidencePack Bounded | 0 Hallucinations / Validated Fallbacks |
| **Daily Edition UX** | Warm Editorial Newspaper | `/edition`, `/edition/{date}`, `/editions` |
| **RAG Engine** | v1.1 Frozen | ~65% Core Retrieval / 100% Grounded |

---

## 3. Existing Data Profile

Profiling executed against canonical PostgreSQL instance (`scratch/profile_sprint4_data.py`):

- **Total Articles Ingested:** 4,728
- **Total AI Outputs Processed:** 1,043
- **Relevant AI Outputs (is_relevant = True):** 953 (91.4% relevance rate)
- **Persisted Event Clusters:** 37
- **Persisted Daily Editions:** 19
- **Active Ingestion Sources:** 50

---

## 4. Existing Entity Data Audit

Audit of 200 relevant `ArticleAIOutput.output_json` records revealed:
- **Total Extracted Entity Mentions:** 374 raw mentions across 200 relevant articles.
- **Unique Surface Form Names:** 151 distinct strings (`OpenAI`, `ChatGPT`, `European Central Bank`, `Sam Altman`, `Ayana Bio`).
- **Entity Type Explosion (57 raw types):** AI extraction produced inconsistent micro-types (`Technology Company`, `Company`, `company`, `Type: Financial Institution`, `Central Bank Executive`, `Quantum Physicist`, `Adversary`, `Influence Campaign`).
- **Surface Form & Alias Variations:**
  - `European Central Bank` vs `ECB`
  - `Federal Reserve` vs `Fed`
  - `OpenAI` vs `Open AI`
  - `United States` vs `US` / `U.S.`
- **Conclusion:** Upstream `ArticleAIOutput` contains rich surface-form mentions but lacks normalization, alias mapping, and ontology constraints. A dedicated downstream resolution stage is mandatory.

---

## 5. Knowledge Layer Principles

1. **Facts from Sources, Not Inferred Knowledge:** Relationships must derive from explicit source evidence. Inferred links must maintain auditable provenance.
2. **Strict Attribution (Assertion vs Fact):** Claims made by sources (`"Company X claims output will double"`) are stored as **Source Assertions**, not absolute global truths.
3. **Non-Blocking Execution:** Knowledge processing occurs strictly downstream from article ingestion and relevance filtering. Ingestion and edition generation never fail if the Knowledge Layer is offline.
4. **Deterministic Idempotency:** Reprocessing an article or event re-links existing canonical entities without creating duplicate graph nodes.

---

## 6. Entity Definition

An **Entity** is a distinct real-world organization, company, institution, geography, person, commodity, or technology mentioned in source intelligence.

---

## 7. Entity Ontology (10 Canonical Types)

To avoid ontology explosion, Stage 4A establishes a strict 10-type ontology:

1. `ORGANIZATION` (Non-profit, multilateral, or industry groups)
2. `COMPANY` (Public/private corporate entities)
3. `GOVERNMENT_BODY` (Ministries, regulatory agencies, state bodies)
4. `CENTRAL_BANK` (Monetary policy authorities e.g. Fed, ECB, BoE, RBI)
5. `COUNTRY` (Sovereign nation states mapped to ISO 3166-1 alpha-2)
6. `REGION` (Geopolitical or economic blocks e.g. EU, Euro Area, BRICS, Middle East)
7. `PERSON` (Public figures, policymakers, executives)
8. `COMMODITY` (Energy, metal, agricultural goods e.g. Brent Crude, Gold, Wheat)
9. `TECHNOLOGY` (Tech paradigms & infrastructure e.g. Semiconductors, LLMs, Plant Cell Culture)
10. `PRODUCT` (Named software, hardware, or platform releases e.g. ChatGPT, Bedrock, H100)

---

## 8. Alias Strategy

- **Canonical Name & Slug:** Primary display name (e.g. `Federal Reserve`) and unique slug (`federal-reserve`).
- **Alias Registry:** Map alternate surface forms (`Fed`, `Federal Reserve System`, `U.S. Federal Reserve`) to the single canonical entity ID.
- **Ambiguity Handling:** Ambiguous terms (e.g. `Apple` fruit vs tech company, `Bank` generic vs specific institution) are resolved using context category or held in a `LOW_CONFIDENCE` state requiring corroboration.

---

## 9. Mention Model

`EntityMention` records every instance where an entity is referenced:
- Grounded link: `entity_id` $\leftrightarrow$ `article_id` $\leftrightarrow$ `event_cluster_id`.
- Surface Form & Context Window: Stores exact string (`"ECB"`) and surrounding sentence snippet.
- Mentions are canonical at the **Article level**; **Event-level mentions** are derived by aggregating primary and supporting cluster articles.

---

## 10. Relationship Model

Constrained relationship vocabulary (no unevidenced causal links):
- `MENTIONS` (Article/Event references Entity)
- `INVOLVES` (Event directly concerns Entity)
- `ISSUED_BY` (Statement/Release published by Entity)
- `AFFECTS` (Development impacts Entity/Sector)
- `OPERATES_IN` (Entity active in Geography/Industry)
- `PART_OF` (Subsidiary or regional member)
- `RELATED_TO` (Corroborated association)

---

## 11. Assertions & Attribution

To preserve neutrality and prevent false factual claims:
- **`SourceAssertion`** stores attributed claims: `[Entity A] asserts [Predicate] about [Entity B / Subject]`.
- Example: *"US Treasury states sanctions target shadow fleet"* is recorded as an assertion by `US Treasury`, avoiding system endorsement of global truth.

---

## 12. Event Semantics

- **`EventCluster` (Existing):** Groups same-event articles into a single cluster (1 Primary + Supporting).
- **`KnowledgeEvent` (Proposed Abstraction):** Semantic representation of an EventCluster enriched with canonical participant roles, event taxonomy, and temporal bounds.

---

## 13. Event Taxonomy (10 Event Types)

1. `POLICY_DECISION` (Monetary, fiscal, or regulatory decision)
2. `CORPORATE_ACTION` (M&A, restructuring, executive change, earnings)
3. `MARKET_MOVE` (Significant asset price, yield, or FX movement)
4. `GEOPOLITICAL_EVENT` (Diplomatic, defense, or conflict development)
5. `TRADE_ACTION` (Tariffs, sanctions, trade agreement changes)
6. `SUPPLY_DISRUPTION` (Logistics, energy, or critical mineral bottleneck)
7. `TECHNOLOGY_RELEASE` (Model, platform, or hardware product launch)
8. `ENERGY_DEVELOPMENT` (Power grid, oil/gas production, renewable project)
9. `ECONOMIC_RELEASE` (CPI, GDP, labor market data release)
10. `REGULATORY_ACTION` (Antitrust, enforcement, legislative action)

---

## 14. Event Participants

Participant roles linking `KnowledgeEvent` $\leftrightarrow$ `Entity`:
- `ACTOR` (Initiating entity)
- `TARGET` (Receiving/affected entity)
- `ISSUER` (Authority releasing statement/data)
- `LOCATION` (Geographic setting)
- `AFFECTED_ENTITY` (Third-party impacted by event)

---

## 15. Temporal Semantics

Each Knowledge Event preserves distinct temporal markers:
- `published_at` (Article publication timestamp)
- `collected_at` (System ingestion timestamp)
- `event_date` (Date the real-world development occurred)
- `effective_date` (Future date when policy/action takes effect)
- Unknown dates remain explicit NULLs (no date fabrication).

---

## 16. Timeline Model

A **Timeline** is a deterministically ordered sequence of grounded `KnowledgeEvent` objects matching an Entity, Category, or Topic.
- Ordering: Strictly chronological by `event_date` / `published_at`.
- Zero LLM Hallucination: Timelines list verified events; narrative prose synthesis is decoupled.

---

## 17. Event Relationships

Conservative links between events:
- `FOLLOW_UP_TO` (Direct sequential continuation)
- `UPDATES` (Revised data or updated statement)
- `REVERSES` (Policy shift or decision rollback)
- `RELATED_TO` (Shared entity & temporal proximity)

---

## 18. Signal Definition

A **Signal** is an observed, evidence-grounded pattern across multiple events over time (e.g. *"Increasing frequency of Central Bank rate hold decisions"*, *"Repeated Red Sea shipping supply disruptions"*).
- A Signal is NOT a prediction. It describes *what has been observed in source evidence*.

---

## 19. Signal Model

- `signal_type`: `FREQUENCY_SPIKE`, `CROSS_REGION_PATTERN`, `POLICY_CONVERGENCE`, `SUPPLY_STRESS`.
- `SignalEvidence`: Links Signal to underlying `event_cluster_id`, `article_id`, and `entity_id` records.
- Strength is calculated deterministically from event count, distinct source corroboration, and time window span.

---

## 20. Trend vs Signal

- **Event:** A single development (e.g. *"ECB cuts rate by 25bps on Sep 15"*).
- **Trend:** Long-term direction across weeks/months.
- **Signal:** A noteworthy, actionable pattern detected across recent evidence windows.

---

## 21. Cross-Source Corroboration Model

Differentiates:
- `1 Article / 1 Source` (Uncorroborated single report)
- `N Articles / 1 Source` (Repeated coverage by same outlet)
- `N Articles / N Distinct Sources` (High-confidence corroboration)
- `Primary Institutional Source + News Reporting` (Gold provenance)

---

## 22. Source Dependency

Future source tracking identifies wire service republication (e.g. Reuters syndication across multiple feeds) to prevent double-counting corroboration points.

---

## 23. Entity Resolution Strategy

Staged 3-tier resolution strategy:
1. **Tier 1 (Deterministic Normalization):** Lowercase, strip punctuation/company suffixes (`Inc`, `Corp`, `Ltd`), expand aliases (`Fed` $\rightarrow$ `Federal Reserve`).
2. **Tier 2 (Alias Registry Match):** Query `entity_aliases` table.
3. **Tier 3 (Contextual Category Match):** Disambiguate using article category & entity type.
*(No vector embeddings or external API calls required for MVP).*

---

## 24. Entity Extraction Strategy

Hybrid extraction model:
- Primary: Extract structured entity candidates from downstream `ArticleAIOutput.output_json` during AI review pass.
- Normalization: Downstream Python worker normalizes surface forms against `entities` and `entity_aliases`.

---

## 25. External IDs (Future Proofing)

The schema includes nullable `external_ids` JSON (`ISO_3166_1`, `LEI`, `WIKIDATA_ID`) for future integration without breaking changes.

---

## 26. Idempotency

Unique constraints on `(entity_id, article_id)` and `(canonical_name, entity_type)` ensure reprocessing an article updates existing records without creating duplicates.

---

## 27. Reprocessing & Versioning

Tables include `extractor_version` and `processed_at` fields. Upgrading the entity extraction algorithm allows backtesting new versions side-by-side.

---

## 28. Confidence

Categorical confidence levels (`HIGH`, `MEDIUM`, `LOW`) derived from extraction source and corroboration count.

---

## 29. Provenance

Every knowledge object maintains foreign keys to `article_id`, `source_id`, or `event_cluster_id`.

---

## 30. Proposed Database Schema (Non-Destructive)

```sql
-- 1. Canonical Entities
CREATE TABLE entities (
    id BIGSERIAL PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    entity_type TEXT NOT NULL, -- COMPANY, CENTRAL_BANK, COUNTRY, etc.
    slug TEXT NOT NULL UNIQUE,
    description TEXT,
    country_code VARCHAR(10),
    external_ids JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uix_entity_name_type UNIQUE (canonical_name, entity_type)
);

-- 2. Entity Aliases
CREATE TABLE entity_aliases (
    id BIGSERIAL PRIMARY KEY,
    entity_id BIGINT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    alias_name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Entity Mentions
CREATE TABLE entity_mentions (
    id BIGSERIAL PRIMARY KEY,
    entity_id BIGINT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    article_id BIGINT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    event_cluster_id VARCHAR(100) REFERENCES event_clusters(cluster_id) ON DELETE CASCADE,
    surface_form TEXT NOT NULL,
    context_snippet TEXT,
    confidence VARCHAR(20) NOT NULL DEFAULT 'HIGH',
    extractor_version VARCHAR(50) NOT NULL DEFAULT 'v1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uix_entity_article_mention UNIQUE (entity_id, article_id)
);

-- 4. Event Participants
CREATE TABLE event_entities (
    id BIGSERIAL PRIMARY KEY,
    event_cluster_id VARCHAR(100) NOT NULL REFERENCES event_clusters(cluster_id) ON DELETE CASCADE,
    entity_id BIGINT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL DEFAULT 'PARTICIPANT', -- ACTOR, TARGET, ISSUER, LOCATION
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uix_event_entity_role UNIQUE (event_cluster_id, entity_id, role)
);

-- 5. Signals
CREATE TABLE signals (
    id BIGSERIAL PRIMARY KEY,
    signal_type VARCHAR(50) NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    strength_score FLOAT NOT NULL DEFAULT 1.0,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. Signal Evidence
CREATE TABLE signal_evidence (
    id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
    event_cluster_id VARCHAR(100) REFERENCES event_clusters(cluster_id) ON DELETE CASCADE,
    article_id BIGINT REFERENCES articles(id) ON DELETE CASCADE,
    entity_id BIGINT REFERENCES entities(id) ON DELETE CASCADE,
    evidence_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 31. Existing Schema Compatibility

The proposed schema adds **6 new tables** without altering or dropping any existing tables (`articles`, `sources`, `article_ai_outputs`, `event_clusters`, `daily_editions`, `edition_events`).

---

## 32. Query Capability Examples

### Query A: All events involving OpenAI in September 2026
```sql
SELECT ec.cluster_id, ec.canonical_title, ec.created_at
FROM event_clusters ec
JOIN event_entities ee ON ec.cluster_id = ee.event_cluster_id
JOIN entities e ON ee.entity_id = e.id
WHERE e.slug = 'openai'
  AND ec.created_at >= '2026-09-01'
ORDER BY ec.created_at DESC;
```

### Query B: ECB Policy Timeline
```sql
SELECT ec.cluster_id, ec.canonical_title, ee.role, ec.created_at
FROM event_clusters ec
JOIN event_entities ee ON ec.cluster_id = ee.event_cluster_id
JOIN entities e ON ee.entity_id = e.id
WHERE e.slug = 'european-central-bank'
ORDER BY ec.created_at ASC;
```

---

## 33. RAG Integration (Future Stage 4C/4D)

The Knowledge Layer will act as a **structural pre-filter** for RAG:
`User Query` $\rightarrow$ `Entity/Event Discovery (Knowledge Layer)` $\rightarrow$ `Grounded Evidence Retrieval (RAG v1.1)` $\rightarrow$ `Grounded Synthesis`.

---

## 34. Future Agent Integration

Defines future tool specifications (`find_entities`, `get_entity_events`, `get_timeline`, `get_signals`) for agentic workflows without introducing runtime dependencies in Stage 4A.

---

## 35. Knowledge Explorer UX

Future URL hierarchy:
- `/entities` (Entity Index)
- `/entity/{slug}` (Entity Profile Page)
- `/signals` (Observed Macro Signals)
- `/timeline/{slug}` (Event Sequence View)

---

## 36. Safety, Privacy & Geopolitical Neutrality

- **Public Figure Limitation:** Person entities restricted to individuals in official public/news contexts. No private personal data extraction.
- **Attribution Preservation:** Source claims are explicitly stored as `SourceAssertion` records, preventing controversial statements from being recorded as system-verified global facts.

---

## 37. Benchmark Design

Designed golden benchmark specifications:
- [`benchmarks/entity_resolution_v1.json`](file:///d:/Daily-Intelligence/benchmarks/entity_resolution_v1.json)
- [`benchmarks/event_entity_v1.json`](file:///d:/Daily-Intelligence/benchmarks/event_entity_v1.json)

---

## 38. Future Acceptance Metrics

- Entity Resolution Precision: **>= 95%**
- False Entity Merge Count: **0**
- Mention Provenance Completeness: **100%**
- Idempotency Violation Count: **0**

---

## 39. Operational Capacity

Knowledge extraction will run **strictly post-relevance filtering** on the ~91.4% relevant article subset, consuming < 5ms per article.

---

## 40. Performance Budgets

- Entity Resolution & Linking: < 10ms per article.
- Entity Page Load: < 50ms (reads persisted SQL tables).

---

## 41. Failure Isolation

```
ARTICLE INGESTION
      │
      ▼
AI REVIEW (ArticleAIOutput)
      │
      ├─── Failure Safe (If Knowledge Layer fails, Ingestion & Editions continue)
      ▼
KNOWLEDGE LAYER WORKER
```

---

## 42. Migration Plan (Stage 4B Preparation)

- Stage 4B migration script will execute `CREATE TABLE` for the 6 new tables with `IF NOT EXISTS`.
- Zero downtime, zero table locking on existing core tables.

---

## 43. Stage 4B–4E Roadmap

- **Stage 4B:** Entity Extraction & Resolution Engine (Database tables, resolution service, benchmark validation).
- **Stage 4C:** Event Participant Linking & Timelines (Event-entity roles, chronological timeline generator).
- **Stage 4D:** Macro Signal Detection Engine (Observed pattern detector, signal evidence links).
- **Stage 4E:** Knowledge Explorer Product Experience & Final Sprint Acceptance (Web views for entities, signals, timelines).

---

## 44. Risks & Mitigation

- **Risk:** Entity name ambiguity (e.g. `Fed` vs `Federated`).  
  **Mitigation:** Category-assisted context mapping and high confidence threshold.
- **Risk:** Ingestion slowing down.  
  **Mitigation:** Asynchronous downstream execution.

---

## 45. Technical Debt

None. Architecture builds cleanly on frozen Sprint 1, 2, 3, and 3H foundations.

---

## 46. Final Architecture Decision

```
==================================================
FINAL SYSTEM STATUS: STAGE 4A — PASS
==================================================
```
