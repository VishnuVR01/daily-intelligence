# RAG Benchmark v1 — Baseline Evaluation Report

**Timestamp (UTC)**: 2026-09-14T23:23:33.981802+00:00  
**Total Duration**: 1.13s  
**Overall Baseline Score**: **81.21 / 100**

## Executive Summary

| Metric | Value | Target / Ideal |
| :--- | :---: | :---: |
| **Questions Tested** | `25` | 25 |
| **Successful Executions** | `25` | 25 |
| **Failed Executions** | `0` | 0 |
| **Retrieval Hit Rate** | `64.8%` | 100.0% |
| **Temporal Accuracy** | `100.0%` | 100.0% |
| **Citation Validity Rate** | `100.0%` | 100.0% |
| **Unsupported Citation Rate** | `0.0%` | 0.0% |
| **Negative-Test Refusal Acc** | `50.0%` | 100.0% |
| **Average Evidence Count** | `7.76` | 3–10 |
| **Source Diversity** | `0.265` | > 0.5 |
| **Execution Success Rate** | `100.0%` | 100.0% |

## Category Performance

| Category | Total | Avg Evidence | Hit Rate | Citation Valid % | Refusal Acc % |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `analytical_causal` | 3 | 10.0 | 69.4% | 100.0% | N/A |
| `comparison` | 3 | 10.0 | 55.6% | 100.0% | N/A |
| `entity_centric` | 4 | 10.0 | 77.5% | 100.0% | N/A |
| `historical_synthesis` | 4 | 10.0 | 87.5% | 100.0% | N/A |
| `insufficient_evidence` | 5 | 4.8 | 0.0% | 100.0% | 40.0% |
| `temporal_freshness` | 3 | 0.0 | 0.0% | 100.0% | 100.0% |
| `timeline` | 3 | 10.0 | 65.7% | 100.0% | N/A |

## Five Strongest Questions

- **RAG-001** (temporal_freshness): *"What happened in AI today?"*
  - Hit Rate: 100.0%, Evidence Count: 0, Citation Validity: True
- **RAG-004** (historical_synthesis): *"What major AI developments are present in the archive?"*
  - Hit Rate: 100.0%, Evidence Count: 10, Citation Validity: True
- **RAG-006** (historical_synthesis): *"Summarize the geopolitical diplomatic developments involving Ukraine and Russia in the archive."*
  - Hit Rate: 100.0%, Evidence Count: 10, Citation Validity: True
- **RAG-008** (entity_centric): *"What does the archive contain about OpenAI or Anthropic?"*
  - Hit Rate: 100.0%, Evidence Count: 10, Citation Validity: True
- **RAG-011** (entity_centric): *"What developments involve Bunge and ADM?"*
  - Hit Rate: 100.0%, Evidence Count: 10, Citation Validity: True

## Five Weakest Questions

- **RAG-003** (temporal_freshness): *"What supply-chain developments happened this week?"*
  - Hit Rate: 0.0%, Evidence Count: 0, Temporal Pass: True, Refusal Pass: True
- **RAG-012** (comparison): *"Compare the AI technology developments and autonomous vehicle announcements in the archive."*
  - Hit Rate: 0.0%, Evidence Count: 10, Temporal Pass: True, Refusal Pass: True
- **RAG-021** (insufficient_evidence): *"What are the latest commercial sales figures for Apple Vision Pro 2 in Europe?"*
  - Hit Rate: 100.0%, Evidence Count: 10, Temporal Pass: True, Refusal Pass: False
- **RAG-023** (insufficient_evidence): *"What was the outcome of the 2026 FIFA World Cup final in North America?"*
  - Hit Rate: 100.0%, Evidence Count: 10, Temporal Pass: True, Refusal Pass: False
- **RAG-024** (insufficient_evidence): *"What specific earnings guidance did Microsoft release for Q4 2026?"*
  - Hit Rate: 100.0%, Evidence Count: 4, Temporal Pass: True, Refusal Pass: False

## Observed Failure Patterns

1. **Keyword Over-Filtering on Temporal Phrases**: Questions with phrase `today` return 0 evidence when no articles were collected/published on today's specific date.
2. **Fallback Summary Citation Mapping**: When Ollama is offline or un-invoked, fallback summary mode formats citations using all context records.
3. **Cross-Language Query Matching**: Queries in English for Finnish news (`Yle News`) rely on PostgreSQL tsvector translation or title matching.

## Manual-Review Queue

The following subjective quality dimensions are queued for manual evaluation in v1:
- Answer Completeness
- Analytical Synthesis Quality
- Evidence Relevance Precision
