# Daily Intelligence — Source Ingestion Health Report

## Executive Summary

A controlled live source ingestion run was conducted across all 50 active sources configured in the Daily Intelligence system.

The ingestion pipeline successfully fetched feeds from **49 out of 50 active sources** (98.0% reachability), discovered **1,845 total feed items**, inserted **387 NEW articles** into PostgreSQL, and cleanly deduplicated **1,458 existing articles**.

---

## Ingestion Metrics Summary

| Metric | Value |
| :--- | :--- |
| **Total Active Sources** | **50** |
| **Reachable Sources** | **49** (98.0%) |
| **Failed Sources** | **0** |
| **Stale / Empty Sources** | **1** (`Rigzone Energy`, ID 75) |
| **Articles Discovered** | **1,845** |
| **NEW Articles Inserted** | **387** |
| **Duplicates Skipped** | **1,458** |
| **Parse Failures** | **0** |
| **AI Processing Batch Tested** | **5 articles** (4 relevant, 1 out-of-scope) |
| **Newest Article ID** | **4206** |
| **Newest Collected Timestamp** | **2026-09-15 00:26:46 BST** |

---

## Pipeline Flow Verification

1. **Source → Collector**: RSS Collector retrieved 49 active feeds using custom `User-Agent` and SSL context fallback.
2. **Normalization & Deduplication**: URLs canonicalized (removing tracking parameters `utm_*`, `gclid`, etc.), HTML tags & entities cleaned from summaries, title fingerprints computed. Deduplication prevented 1,458 duplicate inserts.
3. **PostgreSQL Persistence**: 387 new article rows persisted with complete URLs, published timestamps, collected timestamps, raw summaries, and source foreign-key relationships.
4. **AI Processing**: Tested controlled AI batch via `OllamaService`. Successfully processed 4 relevant world/AI/geopolitics articles and classified 1 routine sports VAR article as `out_of_scope`. No article rows were deleted or corrupted.
5. **Frontend Visibility**: Verified newly ingested articles immediately appear across Home Edition, Archive, Search, and Briefings endpoints.

---

## Sources Requiring Future Attention

- **Rigzone Energy (ID 75)**: `https://www.rigzone.com/news/rss/rigzone_latest.aspx` returned 0 items. Feed URL needs updating or HTML fallback scraper integration.
