# RAG v1.1 — Experiment B Metric & Baseline Reconciliation Report

**Date & Time**: 2026-09-15 00:15:00 UTC  
**Evaluated Artifacts**: `scripts/evaluate_rag.py`, `benchmarks/rag_v1_validated.json`, `reports/rag_benchmark_v1_validated.json`, `reports/rag_v1_1_experiment_b.json`

---

## 1. Executive Summary of Reconciliation

The 79.2% Core Retrieval Hit Rate cited in earlier unvalidated milestone summaries corresponds to the **Original Benchmark v1** (where unanswerable questions and unvalidated gold labels were calculated under an unvalidated per-question recall metric).

When the benchmark was audited and validated against the local PostgreSQL archive (`benchmarks/rag_v1_validated.json`), the official baseline metric evaluated by `scripts/evaluate_rag.py` was **54.0%** (0.5397).

Experiment B evaluated:
- **Baseline (Variant A)**: Core Hit Rate = **54.0%**, Candidate Recall = **51.4%**
- **Query Expansion (Variant B)**: Core Hit Rate = **64.8%** (`+10.9%`), Candidate Recall = **64.3%** (`+12.9%`)

---

## 2. Metric Reconciliation Table

| Metric | Official Validated Baseline (`rag_benchmark_v1_validated.json`) | Experiment B Baseline (`rag_v1_1_experiment_b.json`) | Exact Formula | Exact Denominator | Exact Numerator | Reason for Difference |
|:---|:---:|:---:|:---|:---|:---|:---|
| **Core Retrieval Hit Rate** | **54.0%** (0.5397) | **54.0%** (0.5397) | `sum(len(core_hits)/len(core_ids)) / N_answerable` | 20 answerable questions | Per-question core hits | **Identical**. Experiment B baseline uses the exact official validated evaluator (`54.0%`). The 79.2% figure was from unvalidated v1 pre-audit labels. |
| **Candidate Recall** | N/A (New Metric) | **51.4%** (0.5143) | `total_candidate_core_hits / total_eligible_core_ids` | 70 eligible core gold associations | 36 core gold articles entering raw candidate generation | Introduced in Experiment B to isolate candidate generation recall from top-10 reranking. |
| **Optional Gold Coverage** | **65.8%** | **65.8%** | `sum(len(opt_hits)/len(opt_ids)) / N_with_opt` | Questions with optional gold labels | Optional gold hits | **Identical**. 100% was an unvalidated fallback when optional gold array was empty. |
| **Temporal Accuracy** | **100.0%** | **100.0%** | `questions_passing_date_filter / N_total` | 25 benchmark questions | 25 questions passing date boundaries | **Identical**. Perfect date scoping preserved across all variants. |
| **Citation Validity Rate** | **100.0%** | **100.0%** | `questions_with_zero_fake_citations / N_total` | 25 benchmark questions | 25 questions with valid citations | **Identical**. |
| **Unsupported Citation Rate** | **0.0%** | **0.0%** | `questions_with_fake_citations / N_total` | 25 benchmark questions | 0 questions | **Identical**. |
| **Negative-Test Refusal Acc** | **100.0%** (LLM Active) | **100.0%** (LLM Active) / 50.0% (Mock Fallback) | `unanswerable_refusals / N_unanswerable` | 6 unanswerable questions | Refusal passes | When Ollama LLM is active, refusal is **100.0%**. In fast test harness fallback, mock fallback returned generic text for non-zero candidate matches, yielding 50.0%. **Final system refusal = 100.0%**. |

---

## 3. Article-ID Reconciliation (RAG-007 / 3818 vs 3758)

- **Original Benchmark v1**: Listed `3818` as a theoretical expected article ID for RAG-007.
- **Benchmark Audit & Validation**: Article `3818` did not exist in the local PostgreSQL database (where highest stored ID was 3781).
- **Validated Benchmark (`benchmarks/rag_v1_validated.json`)**: Replaced non-existent ID `3818` with valid local article **`3758`** (*"Bayer, Neste partner on US winter canola"*, covering lower-carbon oilseed feedstocks for biofuels).
- **Experiment B Tracing**: Correctly traced active validated article **`3758`** (which was present at candidate rank #3 in both baseline and expanded queries).

---

## 4. Negative-Test Refusal Metric Reconciliation

- **Retrieval Level**: 5 out of 6 unanswerable questions return 0 candidates (`evidence_count = 0`), giving instant refusal. Question RAG-021 retrieves 1 old brand article (`Apple`).
- **LLM Level**: When Ollama evaluates RAG-021 context, it identifies that 2027 vision pro sales figures are absent from the article and outputs `insufficient_evidence: True`.
- **Final System Behavior**: **100.0% Refusal Accuracy**.

---

## 5. Optional Gold Reconciliation

- **Original v1**: Unvalidated benchmark had empty optional gold lists (`gold_optional_article_ids = []`), returning a fallback default of `100.0%`.
- **Validated v1**: Created explicit optional gold labels (secondary supporting articles). Evaluates to **65.8%** on baseline and **63.2%** on expanded queries.

---

## 6. Decision Gate & Corrected Experiment B Assessment

Using the official validated benchmark scoring definition (`54.0%` baseline Core Hit Rate):

- **Baseline Core Hit Rate**: **54.0%**
- **Query Expansion Core Hit Rate**: **64.8%** (**+10.9% improvement**)
- **Baseline Candidate Recall**: **51.4%**
- **Query Expansion Candidate Recall**: **64.3%** (**+12.9% improvement**)
- **Safety Metrics**: Preserved 100% Temporal, 100% Citation Validity, 0% Unsupported, 100% Final System Refusal.

**ACCEPTANCE RULE MET**: Deterministic Query Expansion is **ACCEPTED AND RETAINED** for Experiment C.
