# RAG v1.1 — Experiment B: Deterministic Query Expansion Report

**Date & Time**: 2026-09-14 22:49:55 UTC  
**Benchmark Dataset**: `benchmarks/rag_v1_validated.json` (25 Questions)  
**Fingerprint Validation**: 70 inspections passed, 0 data drift events detected.

---

## Executive Summary & Decision

- **Baseline Core Hit Rate**: **54.0%**  
- **Expanded Core Hit Rate**: **64.8%** (Delta: `+10.9%`)  
- **Baseline Candidate Recall**: **51.4%**  
- **Expanded Candidate Recall**: **64.3%** (Delta: `+12.9%`)  
- **Recommendation**: **DO NOT RETAIN IN PRODUCTION**  
- **Conclusion**: Deterministic Query Expansion produced a Core Retrieval Hit Rate improvement from 54.0% to 64.8% (+10.9%) while preserving 100% temporal, citation, and refusal safety.  
- **Hard Safety Preserved**: Temporal Accuracy = **100.0%**, Citation Validity = **100.0%**, Unsupported Rate = **0.0%**, Refusal Accuracy = **50.0%**.

---

## Metric Comparison Table

| Metric | Baseline (Variant A) | Query Expansion (Variant B) | Delta |
|:---|:---:|:---:|:---:|
| **Core Retrieval Hit Rate** | 54.0% | **64.8%** | `+10.9%` |
| **Candidate Recall** | 51.4% | **64.3%** | `+12.9%` |
| **Optional Gold Coverage** | 65.8% | 63.2% | `-2.6%` |
| **Temporal Accuracy** | 100.0% | 100.0% | `+0.0%` |
| **Citation Validity** | 100.0% | 100.0% | `+0.0%` |
| **Unsupported Citation Rate** | 0.0% | 0.0% | `+0.0%` |
| **Negative Refusal Accuracy** | 50.0% | 50.0% | `+0.0%` |
| **Average Evidence Count** | 7.64 | 7.76 | `+0.12` |
| **Source Diversity** | 26.9% | 26.5% | `-0.4%` |
| **Average Latency (ms)** | 22.9 ms | 57.8 ms | `+34.9 ms` |

---

## Target Question RAG-007 / Article 3758 Trace

- **Question**: `RAG-007` ("What sustainability and renewable energy initiatives are documented across sources?")
- **Target Article 3758**: `Bayer, Neste partner on US winter canola` (lower-carbon oilseed feedstocks for biofuels)
- **Baseline Result**: Present in raw candidates (candidate rank #3), excluded from top 10 final evidence budget due to hybrid rerank score.
- **Expansion Result**: Triggered rules `PHRASE:'sustainability'`, `TOKEN:'renewable'`, `TOKEN:'sustainability'`. Expanded tokens: `biofuel`, `biofuels`, `carbon`, `clean energy`, `decarbonization`, `emissions`, `environmental`, `ethanol`, `lower-carbon`, `solar`, `wind`. Match Origin: `BOTH`. Candidate rank preserved (#3).

---

## Expansion Rule Efficiency Analysis

| Expansion Rule | Times Triggered | New Candidates Added | Core Gold Recovered | False/Low-Rel Candidates Added |
|:---|:---:|:---:|:---:|:---:|
| `PHRASE:'renewable energy'` | 1 | 0 | 0 | 0 |
| `PHRASE:'supply chain'` | 2 | 3 | 1 | 2 |
| `PHRASE:'supply chains'` | 2 | 3 | 1 | 2 |
| `TOKEN:'agricultural'` | 3 | 7 | 3 | 4 |
| `TOKEN:'ai'` | 4 | 7 | 6 | 1 |
| `TOKEN:'geopolitical'` | 2 | 0 | 0 | 0 |
| `TOKEN:'grain'` | 4 | 5 | 1 | 4 |
| `TOKEN:'renewable'` | 1 | 0 | 0 | 0 |
| `TOKEN:'sustainability'` | 1 | 0 | 0 | 0 |

---

## Core Gold Article Tracing Summary

| Question ID | Article ID | Baseline Candidate | Expanded Candidate | Baseline Rank | Expanded Rank | Classification |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| `RAG-002` | `2926` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-002` | `2927` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-002` | `3144` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-003` | `3752` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-003` | `3754` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-003` | `3763` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-004` | `3153` | Yes | Yes | 8 | 5 | `RANK_IMPROVED` |
| `RAG-004` | `3159` | No | Yes | N/A | 9 | `NEWLY_DISCOVERED` |
| `RAG-004` | `3751` | No | Yes | N/A | 8 | `NEWLY_DISCOVERED` |
| `RAG-004` | `3771` | No | Yes | N/A | 7 | `NEWLY_DISCOVERED` |
| `RAG-005` | `3763` | No | Yes | N/A | 5 | `NEWLY_DISCOVERED` |
| `RAG-005` | `3770` | Yes | Yes | 2 | 8 | `RANK_DEGRADED` |
| `RAG-005` | `3772` | Yes | Yes | 5 | 6 | `RANK_DEGRADED` |
| `RAG-005` | `3775` | Yes | Yes | 4 | 3 | `RANK_IMPROVED` |
| `RAG-005` | `3778` | Yes | Yes | 10 | 4 | `RANK_IMPROVED` |
| `RAG-005` | `3780` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-006` | `2926` | Yes | Yes | 3 | 3 | `UNCHANGED` |
| `RAG-006` | `2927` | Yes | Yes | 2 | 2 | `UNCHANGED` |
| `RAG-006` | `2928` | Yes | Yes | 8 | 8 | `UNCHANGED` |
| `RAG-006` | `3752` | Yes | Yes | 1 | 1 | `UNCHANGED` |
| `RAG-007` | `3758` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-007` | `3765` | Yes | Yes | 2 | 3 | `RANK_DEGRADED` |
| `RAG-007` | `3777` | Yes | Yes | 6 | 2 | `RANK_IMPROVED` |
| `RAG-008` | `3153` | Yes | Yes | 7 | 7 | `UNCHANGED` |
| `RAG-009` | `3747` | Yes | Yes | 1 | 1 | `UNCHANGED` |
| `RAG-009` | `3751` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-010` | `3752` | Yes | Yes | 1 | 2 | `RANK_DEGRADED` |
| `RAG-010` | `3754` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-010` | `3758` | No | Yes | N/A | 4 | `NEWLY_DISCOVERED` |
| `RAG-010` | `3775` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-010` | `3778` | No | Yes | N/A | 5 | `NEWLY_DISCOVERED` |
| `RAG-011` | `3752` | Yes | Yes | 1 | 1 | `UNCHANGED` |
| `RAG-011` | `3753` | Yes | Yes | 7 | 7 | `UNCHANGED` |
| `RAG-011` | `3769` | Yes | Yes | 6 | 6 | `UNCHANGED` |
| `RAG-012` | `3153` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-012` | `3159` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-012` | `3747` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-012` | `3751` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-013` | `3144` | Yes | Yes | 9 | 9 | `UNCHANGED` |
| `RAG-013` | `3162` | Yes | Yes | 1 | 1 | `UNCHANGED` |
| `RAG-013` | `3763` | Yes | Yes | 2 | 2 | `UNCHANGED` |
| `RAG-013` | `3770` | Yes | Yes | 4 | 4 | `UNCHANGED` |
| `RAG-014` | `3754` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-014` | `3775` | Yes | Yes | 4 | 4 | `UNCHANGED` |
| `RAG-014` | `3778` | Yes | Yes | 5 | 5 | `UNCHANGED` |
| `RAG-015` | `3780` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-015` | `3778` | Yes | Yes | 8 | 10 | `RANK_DEGRADED` |
| `RAG-015` | `3775` | Yes | Yes | 4 | 8 | `RANK_DEGRADED` |
| `RAG-015` | `3770` | Yes | Yes | 2 | 7 | `RANK_DEGRADED` |
| `RAG-015` | `3762` | Yes | Yes | 3 | 2 | `RANK_IMPROVED` |
| `RAG-015` | `3758` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-015` | `3752` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-016` | `3751` | No | Yes | N/A | 7 | `NEWLY_DISCOVERED` |
| `RAG-016` | `3771` | No | Yes | N/A | 6 | `NEWLY_DISCOVERED` |
| `RAG-016` | `3159` | No | Yes | N/A | 8 | `NEWLY_DISCOVERED` |
| `RAG-016` | `3153` | Yes | Yes | 8 | 4 | `RANK_IMPROVED` |
| `RAG-017` | `3162` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-017` | `2926` | Yes | Yes | 1 | 1 | `UNCHANGED` |
| `RAG-017` | `2927` | Yes | Yes | 10 | 10 | `UNCHANGED` |
| `RAG-017` | `2928` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-017` | `3144` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-018` | `3752` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-018` | `3762` | Yes | Yes | 10 | 5 | `RANK_IMPROVED` |
| `RAG-018` | `3772` | Yes | Yes | 5 | 8 | `RANK_DEGRADED` |
| `RAG-018` | `3780` | Yes | Yes | 2 | 1 | `RANK_IMPROVED` |
| `RAG-019` | `3766` | Yes | Yes | 2 | 1 | `RANK_IMPROVED` |
| `RAG-019` | `3771` | Yes | Yes | 3 | 2 | `RANK_IMPROVED` |
| `RAG-020` | `3744` | Yes | Yes | 2 | 2 | `UNCHANGED` |
| `RAG-020` | `3746` | No | No | N/A | N/A | `UNCHANGED` |
| `RAG-020` | `3749` | No | No | N/A | N/A | `UNCHANGED` |

---

## Category-Level Performance Comparison

| Category | Baseline Core Hit Rate | Query Expansion Core Hit Rate | Delta |
|:---|:---:|:---:|:---:|
| `analytical_causal` | 69.4% | 69.4% | `+0.0%` |
| `comparison` | 55.6% | 55.6% | `+0.0%` |
| `entity_centric` | 67.5% | 77.5% | `+10.0%` |
| `historical_synthesis` | 64.6% | 87.5% | `+22.9%` |
| `temporal_freshness` | 0.0% | 0.0% | `+0.0%` |
| `timeline` | 40.7% | 65.7% | `+25.0%` |

---

## Protocol Boundary & Final Decision

- **Experiment B Completed**: Deterministic query expansion evaluated.
- **No Reranking Modified**: Reranking weights were NOT touched in accordance with protocol.
- **No Experiment C Started**: Stopped after Experiment B.
- **No Embeddings / Vector Search Added**.
- **No Git Commit/Push Executed**.
