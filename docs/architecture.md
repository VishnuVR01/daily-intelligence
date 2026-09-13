# Architecture

## Phase 1 — deterministic foundation

```text
RSS / official feeds
        ↓
Python ingestion
        ↓
normalisation
        ↓
deduplication
        ↓
PostgreSQL
        ↓
daily edition builder
        ↓
FastAPI web archive
```

## Phase 2 — local AI

```text
PostgreSQL articles
        ↓
Ollama
        ↓
classification
summarisation
importance scoring
        ↓
stored AI outputs
```

## Phase 3 — hybrid intelligence

Use OpenRouter selectively for difficult synthesis or higher-value analysis while
keeping high-volume processing local.

## Phase 4 — research system

Add embeddings, semantic retrieval, RAG, specialist agents, alerts and team workflows.
