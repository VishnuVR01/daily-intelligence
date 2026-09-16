# RAG v1.1 — Experiment B: Corrected Deterministic Query Expansion Report

**Date & Time**: 2026-09-15 00:15:00 UTC  
**Benchmark Dataset**: `benchmarks/rag_v1_validated.json` (25 Questions)  
**Reconciliation Status**: Reconciled against official validated baseline (`rag_benchmark_v1_validated.json`).

---

## Executive Summary & Decision

- **Official Validated Baseline Core Hit Rate**: **54.0%**  
- **Expanded Core Hit Rate (Variant B)**: **64.8%** (**+10.9% improvement**)  
- **Baseline Candidate Recall**: **51.4%**  
- **Expanded Candidate Recall**: **64.3%** (**+12.9% improvement**)  
- **Decision**: **ACCEPTED & RETAINED FOR PRODUCTION**  
- **Conclusion**: Deterministic Query Expansion produced a Core Retrieval Hit Rate improvement from **54.0%** to **64.8%** (+10.9%) and a Candidate Recall improvement from **51.4%** to **64.3%** (+12.9%) while preserving 100% temporal, citation, and final system refusal safety.
- **Safety Metrics Preserved**:
  - Temporal Accuracy = **100.0%**
  - Citation Validity Rate = **100.0%**
  - Unsupported Citation Rate = **0.0%**
  - Final System Negative Refusal Accuracy = **100.0%**

---

## Metric Comparison Table (Apples-to-Apples Validated Benchmark)

| Metric | Official Validated Baseline | Query Expansion (Variant B) | Delta |
|:---|:---:|:---:|:---:|
| **Core Retrieval Hit Rate** | 54.0% | **64.8%** | **`+10.9%`** |
| **Candidate Recall** | 51.4% | **64.3%** | **`+12.9%`** |
| **Optional Gold Coverage** | 65.8% | 63.2% | `-2.6%` |
| **Temporal Accuracy** | 100.0% | **100.0%** | `+0.0%` |
| **Citation Validity Rate** | 100.0% | **100.0%** | `+0.0%` |
| **Unsupported Citation Rate** | 0.0% | **0.0%** | `+0.0%` |
| **Final System Negative Refusal Acc** | 100.0% | **100.0%** | `+0.0%` |
| **Average Evidence Count** | 7.64 | 7.76 | `+0.12` |
| **Source Diversity** | 26.9% | 26.5% | `-0.4%` |
| **Average Latency (ms)** | 22.9 ms | 57.8 ms | `+34.9 ms` |

---

## Decision Gate Approval for Experiment C

Since Deterministic Query Expansion improved Candidate Recall by **+12.9%** and Core Hit Rate by **+10.9%** without harming any safety metrics, the accepted Query Expansion configuration is approved as the starting point for **RAG v1.1 — EXPERIMENT C: QUERY-AWARE DETERMINISTIC RERANKING**.
