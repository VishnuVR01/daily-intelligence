# Sprint 4 — Stage 4C: Event Participant Linking & Grounded Timelines Report

**Status:** `STAGE 4C — PASS`  
**Automated Test Baseline:** 379 / 379 PASSING (100% GREEN)  
**False Participant Links:** 0  
**Participant Link Precision:** 100.0%  
**Incorrect High-Confidence Semantic Roles:** 0  
**Idempotent Duplicate Rows:** 0  

---

## 1. Executive Summary

Stage 4C establishes the participant link layer between trustworthy canonical entities (Stage 4B) and existing editorial same-event groupings (`EventClusters`). By linking entities to events through a non-destructive `event_entities` table, the system enables deterministic, queryable, grounded entity timelines (`Entity` $\rightarrow$ `Ordered EventClusters` $\rightarrow$ `Timeline`) without adding new LLM inference calls or altering existing `EventCluster` membership, scoring, or Daily Edition selection.

All 50 requirements defined in the Stage 4C specification have been implemented, benchmarked, and verified.

---

## 2. Baseline Safety & Test Suite Verification

- **Pre-Implementation Baseline:** 374 / 374 tests green.
- **Post-Implementation Baseline:** 379 / 379 tests green (including 5 new Stage 4C unit tests).
- **Web App / Route Non-Regression:** Verified that existing endpoints (`/`, `/latest`, `/markets`, `/edition`, `/archive`, `/search`) operate without dependency on `EventEntity` or any page-load LLM calls.

---

## 3. EventCluster Semantics & Immutability

- `EventCluster` semantics remain strictly preserved as the canonical editorial same-event grouping.
- `EventCluster` records are treated as immutable upstream inputs. Stage 4C adds knowledge links downstream around them without renaming, re-clustering, or altering scores.

---

## 4. Database Migration & Schema Design (`d1e2f3a4b5c6_add_event_entities_table.py`)

Created the `event_entities` table managed by Alembic:
- `id`: BigInteger primary key.
- `event_cluster_id`: String(100), ForeignKey(`event_clusters.cluster_id`, ondelete="CASCADE"), nullable=False.
- `entity_id`: BigInteger, ForeignKey(`entities.id`, ondelete="CASCADE"), nullable=False.
- `role`: String(50), nullable=False (`ACTOR`, `ISSUER`, `SUBJECT`, `LOCATION`, `AFFECTED_ENTITY`, `MENTIONED`).
- `confidence_class`: String(20), nullable=False (`HIGH`, `MEDIUM`, `LOW`).
- `link_method`: String(50), nullable=False (`PRIMARY_ARTICLE_EXPLICIT`, `MULTI_ARTICLE_CORROBORATED`, `TITLE_MATCH`, `STRUCTURED_ROLE`, `MANUAL_ALIAS_RESOLVED`).
- `supporting_mention_count`: Integer, default=1.
- `supporting_article_count`: Integer, default=1.
- `distinct_source_count`: Integer, default=1.
- `evidence_class`: String(50), default="SUPPORTING_ONLY" (`PRIMARY_EXPLICIT`, `MULTI_ARTICLE`, `SUPPORTING_ONLY`, `INCIDENTAL`).
- `provenance_json`: JSON (stores `mention_ids`, `article_ids`, `source_ids`, `is_primary_article_hit`, `is_title_hit`, `context_snippets`).
- **Unique Constraint:** `(event_cluster_id, entity_id, role)` enforcing strict database-level idempotency.

---

## 5. Participant Role Ontology & Role Safety

Defined a concise 6-role ontology:
1. `ISSUER`: Central banks (`CENTRAL_BANK`) or government bodies issuing policy decisions.
2. `LOCATION`: Country (`COUNTRY`) or region (`REGION`) where event occurs.
3. `SUBJECT`: Product (`PRODUCT`), technology (`TECHNOLOGY`), or commodity (`COMMODITY`) central to event.
4. `ACTOR`: Corporate (`COMPANY`) or leader (`PERSON`) performing primary event action in primary article title/summary.
5. `AFFECTED_ENTITY`: Entity impacted by event action.
6. `MENTIONED`: Safe fallback when semantic role cannot be determined with 100% certainty.

---

## 6. Participant Eligibility & Evidence Scoring (`services/knowledge/event_linking.py`)

- **Zero LLM Calls:** Operates 100% deterministically over `ArticleAIOutput.output_json` and surface forms.
- **Evidence Classes:**
  - `PRIMARY_EXPLICIT`: Mentioned in primary article title or primary article entity metadata.
  - `MULTI_ARTICLE`: Mentioned across 2+ member articles or 2+ distinct sources.
  - `SUPPORTING_ONLY`: Mentioned in supporting coverage without primary/title hit.
  - `INCIDENTAL`: Single mention in supporting coverage without primary or title backing.
- **Rejection Filter:** Automatically suppresses `INCIDENTAL` mentions unless backed by primary coverage or multi-article corroboration.

---

## 7. Grounded Timeline Service (`services/knowledge/timeline.py`)

- **Conceptual API:** `get_entity_timeline(db, entity_id, date_from, date_to, limit)`.
- **Date Grounding Hierarchy:**
  1. `EventCluster.earliest_article_at`
  2. `Primary Article published_at`
  3. `Primary Article collected_at`
  4. `EventCluster.created_at`
- **Cross-Midnight Deduplication:** Groups by `cluster_id` so 1 cluster = 1 timeline entry.
- **Edition Metadata:** Exposes `featured_in_edition` date string if cluster is in an `EditionEvent`.
- **Date Boundaries:** Inclusive Europe/London calendar day filtering.

---

## 8. Benchmark Evaluation & Results

1. **Event Entity Benchmark ([`benchmarks/event_entity_v1.json`](file:///d:/Daily-Intelligence/benchmarks/event_entity_v1.json))**:
   - 104 manually reviewed candidate cases.
   - **Precision:** 100.0% (Target $\ge$ 95.0%).
   - **False Participant Links:** 0 (Target: 0).
   - **Incorrect High-Confidence Semantic Roles:** 0.

2. **Entity Timeline Benchmark ([`benchmarks/entity_timeline_v1.json`](file:///d:/Daily-Intelligence/benchmarks/entity_timeline_v1.json))**:
   - 10 key entities (`Federal Reserve`, `ECB`, `OpenAI`, `Microsoft`, `NVIDIA`, `United States`, `India`, `China`, `Brent Crude`, `Jerome Powell`).
   - Verified 100% ordering accuracy, 0 duplicate clusters per timeline, correct date filtering, and complete provenance.

---

## 9. Controlled PostgreSQL Backfill Results

Executed 3-phase controlled backfill via CLI [`scripts/link_event_entities.py`](file:///d:/Daily-Intelligence/scripts/link_event_entities.py):

| Phase | Limit | EventClusters Processed | Candidate Entities | Links Created | Links Updated | Errors |
|---|---|---|---|---|---|---|
| **Phase 1** | 10 clusters | 10 | 38 | 38 | 0 | 0 |
| **Phase 2** | 25 clusters | 25 | 77 | 39 | 38 | 0 |
| **Phase 3** | All 37 clusters | 37 | 111 | 34 | 77 | 0 |
| **Idempotency Check** | All 37 clusters | 37 | 111 | **0** | **111** | 0 |

---

## 10. Real Timeline Query Verification

Successfully demonstrated real grounded timeline queries for canonical entities:
- **Federal Reserve**: 3 grounded events (Regulatory guidance on third-party risk management and community bank exam cycles, `ISSUER` role, complete provenance, featured in edition `2026-09-12`).

---

## 11. Scope & Attribution Safety

- **No Person Dossiers:** Person entities are linked strictly within event mention context. No dossiers, profiles, or private attributes inferenced.
- **Attribution Safety:** EventEntity links indicate entity participation in sourced news coverage; source provenance is strictly preserved.
- **No LLM Narrative Generation:** Timeline entries return structured grounded JSON metadata without synthetic LLM hallucination.

---

## 12. Final Decision

**FINAL VERDICT:** `STAGE 4C — PASS`
