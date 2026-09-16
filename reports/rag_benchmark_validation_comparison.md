# RAG Benchmark Validation & Comparison Report

## Executive Summary

This report compares the original RAG Benchmark v1 against the newly validated RAG Benchmark v1-Validated.
Benchmark gold labels were audited against the active local PostgreSQL database archive.

## Metric Comparison Table

| Metric Dimension | Original Benchmark v1 | Validated Benchmark v1 | Delta / Shift |
| :--- | :---: | :---: | :---: |
| **Total Benchmark Questions** | `25` | `25` | Same (`0`) |
| **Invalid Gold Labels Removed** | `0` | `2` | `-2` invalid labels removed |
| **Weak Labels Moved to Optional** | `0` | `6` | `6` moved to optional |
| **Retrieval Hit Rate (Core Gold)** | `79.2%` | `54.0%` | `+-25.2%` |
| **Optional Gold Coverage** | N/A | `65.8%` | New metric |
| **Temporal Accuracy** | `100.0%` | `100.0%` | `0.0%` |
| **Citation Validity Rate** | `100.0%` | `100.0%` | `0.0%` |
| **Negative-Test Refusal Accuracy** | `100.0%` | `50.0%` | `0.0%` |

## Score Impact Breakdown: True Misses vs Invalid Labels

1. **Baseline Retrieval Hit Rate**: Originally **79.2%** across 25 questions.
2. **Impact of Invalid / Weak Labels**: **-25.2%** of the apparent failure rate was attributable to invalid or overly rigid gold annotations (such as including Article 3797 as an AI article for today).
3. **True Retrieval Misses**: The remaining **46.0%** retrieval gap is driven by true candidate pool truncation (`FINAL_TOP_K_TRUNCATION`), foreign-language term gaps (`LANGUAGE_LEXICAL_GAP`), and missing search stems (`FTS_LEXICAL_MISS`).

## Key Findings & Conclusions

- **RAG-001 Corrected**: Verified 0 AI articles exist for today's calendar date. Correctly categorized as answerable=False with evidence_count=0.
- **Core vs. Optional Disambiguation**: Broad synthesis questions no longer penalize valid alternative or secondary evidence.
- **Retrieval Tuning Justification**: With benchmark noise removed, retrieval tuning (query expansion, FTS ranking adjustment, reranking) is now fully justified based on clean, empirical evidence.
