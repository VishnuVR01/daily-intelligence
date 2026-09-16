# Sprint 2 Stage 2C — Commodities, Critical Minerals & FX Intelligence Report

**Date**: September 15, 2026  
**Status**: COMPLETE (STAGE 2C PASSED)  
**Test Baseline**: 290 / 290 PASSING  

---

## 1. Executive Summary & Architecture Overview

Sprint 2 Stage 2C extends the Daily Intelligence platform with macro cross-asset intelligence covering Energy Futures, Precious Metals Futures, Critical Minerals Equity Proxies, and Foreign Exchange (FX) rates.

### Core Architectural Extensions
1. **Normalized Cross-Asset Model**: Extended `MarketSnapshot` with `asset_class`, `unit`, `semantics_note`, and `canonical_id`.
2. **Canonical Instrument Registry**: Separated internal canonical instrument identities (`BRENT_CRUDE_FUTURES`, `GOLD_FUTURES`, `REMX_EQUITY_PROXY`, `GBP_USD`, etc.) from raw provider-specific ticker symbols (`BZ=F`, `GC=F`, `REMX`, `GBPUSD=X`).
3. **Provider Layer Integration**: Extended `TwelveDataProvider` and `YahooFinanceProvider` within `services/markets/` to fetch cross-asset snapshots without creating a parallel service layer.
4. **Instrument Identity & Fallback Safety**: Enforced Gold Futures (`GC=F`) continuous futures identity. Fallbacks preserve instrument identity and return `unavailable` rather than silently substituting spot gold (`XAU/USD`).
5. **Deterministic Movement & FX Semantics Engine**: Implemented `interpret_fx_movement()` for accurate quote direction interpretation (e.g. `USD/INR` rise = INR weakened vs USD; `GBP/USD` rise = GBP strengthened vs USD).
6. **Cross-Asset Intelligence Affinity Matching**: Extended keyword matching with affinity groups for Energy, Metals, Critical Minerals (REMX), and FX while maintaining the zero-causality guard (`MARKET_MOVING` vs `RELATED`).
7. **Warm Editorial UI Integration**: Rendered the compact **MACRO & COMMODITY PULSE** section beneath `GLOBAL MARKET PULSE` on `/markets` with explicit `EQUITY PROXY` badges, REMX methodology note, and directional indicators.

---

## 2. Canonical Instrument Registry & Provider Mappings

| Canonical ID | Display Name | Asset Class | Primary (Twelve Data) | Fallback (Yahoo) | Unit | Semantics & Identity Notes |
|---|---|---|---|---|---|---|
| `BRENT_CRUDE_FUTURES` | Brent Crude Futures | `ENERGY_FUTURES` | `BRENT` | `BZ=F` | USD / bbl | ICE Front-Month Continuous Futures |
| `WTI_CRUDE_FUTURES` | WTI Crude Futures | `ENERGY_FUTURES` | `WTI` | `CL=F` | USD / bbl | NYMEX Front-Month Continuous Futures |
| `GOLD_FUTURES` | Gold Futures | `METALS_FUTURES` | `GC=F` | `GC=F` | USD / t oz | COMEX Front-Month Continuous Futures |
| `SILVER_FUTURES` | Silver Futures | `METALS_FUTURES` | `SI=F` | `SI=F` | USD / t oz | COMEX Front-Month Continuous Futures |
| `REMX_EQUITY_PROXY` | Rare Earth & Strategic Metals | `EQUITY_PROXY` | `REMX` | `REMX` | USD / share | **EQUITY PROXY** — VanEck Rare Earth ETF (not physical price) |
| `GBP_USD` | GBP / USD | `FX` | `GBP/USD` | `GBPUSD=X` | USD per £1 | USD received per £1 (Sterling) |
| `EUR_USD` | EUR / USD | `FX` | `EUR/USD` | `EURUSD=X` | USD per €1 | USD received per €1 (Euro) |
| `USD_INR` | USD / INR | `FX` | `USD/INR` | `USDINR=X` | INR per $1 | INR received per $1 (Rupee) |
| `USD_JPY` | USD / JPY | `FX` | `USD/JPY` | `USDJPY=X` | JPY per $1 | JPY received per $1 (Yen) |

---

## 3. Instrument Identity & Methodology Rules

### Gold Identity Guard
`GC=F` (Gold Futures) continuous futures identity is strictly preserved. `XAU/USD` spot gold is never silently substituted into the Stage 2C commodity pulse, preventing instrument dilution.

### REMX Equity Proxy Identity Guard
REMX is explicitly categorized as `EQUITY_PROXY` and displayed with a high-visibility `EQUITY PROXY` badge. The UI includes the mandatory concise methodology notice:
> *"REMX is an equity-market proxy tracking companies exposed to rare-earth and strategic metals. It is not a physical rare-earth commodity price."*

---

## 4. FX Direction Semantics

FX rate directional interpretations are computed deterministically using standard market conventions:

- **GBP/USD Rises (+)**: Sterling strengthened vs USD (USD weakened).
- **GBP/USD Falls (-)**: Sterling weakened vs USD (USD strengthened).
- **EUR/USD Rises (+)**: Euro strengthened vs USD (USD weakened).
- **EUR/USD Falls (-)**: Euro weakened vs USD (USD strengthened).
- **USD/INR Rises (+)**: Indian Rupee weakened vs USD (USD strengthened).
- **USD/INR Falls (-)**: Indian Rupee strengthened vs USD (USD weakened).
- **USD/JPY Rises (+)**: Japanese Yen weakened vs USD (USD strengthened).
- **USD/JPY Falls (-)**: Japanese Yen strengthened vs USD (USD weakened).

All FX directional observations are fully tested and verified without using LLM arithmetic.

---

## 5. Cache Architecture & Provider Quota Protection

- **Cross-Asset Snapshot TTL**: 15 minutes (900 seconds) in-memory cache.
- **Historical Series TTL**: 6 hours (21,600 seconds) in-memory cache.
- **Twelve Data Rate Limits**: 8 credits/minute free-tier limit respected. Batch multi-symbol endpoint calls (`/quote?symbol=...`) are utilized for equity proxy and FX quotes, falling back gracefully to Yahoo Finance for futures endpoints when restricted on free tiers.

---

## 6. Historical Data Verification

All 9 cross-asset instruments were fetched and validated through `fetch_historical_series()`:

- **Brent Crude (`BZ=F`)**: 252 daily bars, chronological, clean timestamps.
- **WTI Crude (`CL=F`)**: 252 daily bars, chronological, clean timestamps.
- **Gold Futures (`GC=F`)**: 252 daily bars, chronological, clean timestamps.
- **Silver Futures (`SI=F`)**: 252 daily bars, chronological, clean timestamps.
- **REMX Equity Proxy (`REMX`)**: 252 daily bars, chronological, clean timestamps.
- **GBP/USD (`GBPUSD=X`)**: 261 daily bars, chronological, clean timestamps.
- **EUR/USD (`EURUSD=X`)**: 261 daily bars, chronological, clean timestamps.
- **USD/INR (`USDINR=X`)**: 261 daily bars, chronological, clean timestamps.
- **USD/JPY (`USDJPY=X`)**: 261 daily bars, chronological, clean timestamps.

*Verification checks confirmed: no future timestamps, no duplicate dates, no null closes, and valid float values.*

---

## 7. Live Provider Verification Table

| Canonical ID | Display Name | Symbol | Latest Close | Previous Close | Change | Change % | Currency / Unit | Source Provider | Stale Status |
|---|---|---|---|---|---|---|---|---|---|
| `REMX_EQUITY_PROXY` | Rare Earth & Strategic Metals | `REMX` | 68.4400 | 68.9300 | -0.4900 | -0.71% | USD / share | Twelve Data | Active (False) |
| `GBP_USD` | GBP / USD | `GBP/USD` | 1.3477 | 1.3501 | -0.0024 | -0.18% | USD per £1 | Twelve Data | Active (False) |
| `EUR_USD` | EUR / USD | `EUR/USD` | 1.1541 | 1.1551 | -0.0010 | -0.09% | USD per €1 | Twelve Data | Active (False) |
| `USD_INR` | USD / INR | `USD/INR` | 95.9600 | 95.9000 | +0.0600 | +0.06% | INR per $1 | Twelve Data | Active (False) |
| `USD_JPY` | USD / JPY | `USD/JPY` | 155.1400 | 154.3400 | +0.8000 | +0.52% | JPY per $1 | Twelve Data | Active (False) |
| `BRENT_CRUDE_FUTURES` | Brent Crude Futures | `BRENT` | 108.4500 | 105.6800 | +2.7700 | +2.62% | USD / bbl | Yahoo Finance (Fallback) | Active (False) |
| `WTI_CRUDE_FUTURES` | WTI Crude Futures | `WTI` | 105.5700 | 101.3900 | +4.1800 | +4.12% | USD / bbl | Yahoo Finance (Fallback) | Active (False) |
| `GOLD_FUTURES` | Gold Futures | `GC=F` | 4338.9000 | 4351.9000 | -13.0000 | -0.30% | USD / t oz | Yahoo Finance (Fallback) | Active (False) |
| `SILVER_FUTURES` | Silver Futures | `SI=F` | 64.2500 | 63.5100 | +0.7400 | +1.16% | USD / t oz | Yahoo Finance (Fallback) | Active (False) |

### Arithmetic Check Results
- **Brent Crude**: `108.4500 - 105.6800 = +2.7700` (`+2.62%`) → **VERIFIED OK**
- **Gold Futures**: `4338.9000 - 4351.9000 = -13.0000` (`-0.30%`) → **VERIFIED OK**
- **GBP / USD**: `1.3477 - 1.3501 = -0.0024` (`-0.18%`) → **VERIFIED OK**
- **USD / INR**: `95.9600 - 95.9000 = +0.0600` (`+0.06%`) → **VERIFIED OK**

---

## 8. Intelligence Matching & Causality Audit

- **Affinity Groups Added**:
  - `BRENT` / `WTI`: oil, crude, OPEC, OPEC+, petroleum, energy supply, refinery, Middle East supply disruption
  - `GOLD` / `SILVER`: gold, silver, precious metals, safe haven, bullion, COMEX
  - `REMX`: rare earth, critical minerals, strategic metals, neodymium, NdPr, Lynas, MP Materials, mineral supply chain
  - `FX`: currency, foreign exchange, sterling, euro, rupee, yen, dollar, Federal Reserve, Bank of England, ECB, RBI, Bank of Japan
- **Causality Guard Verification**: Total unsupported causal claims across output intelligence = **0**. Articles are strictly grouped into `MARKET_MOVING` vs `RELATED` based on explicit causal statement validation.

---

## 9. Failure Isolation

Provider failure testing demonstrated complete component isolation:
- Single-instrument or cross-asset API errors cause only the affected macro instrument card to show `"Data Unavailable"`.
- `/markets` page rendering, equity global markets pulse, and homepage functionality remain 100% operational.
- Stale cache fallback activates cleanly when network requests fail.

---

## 10. Automated Test Results

- **Total Tests Collected**: 290
- **Total Tests Passing**: 290
- **Pass Rate**: 100%

### Dedicated Test Coverage Highlights
1. Brent crude identity and continuous futures classification
2. WTI crude identity and continuous futures classification
3. Gold futures (`GC=F`) continuous futures identity preservation
4. Silver futures (`SI=F`) continuous futures identity preservation
5. REMX equity-proxy identity and non-commodity label guard
6. GBP/USD exchange rate identity and quotation unit
7. EUR/USD exchange rate identity and quotation unit
8. USD/INR exchange rate identity and quotation unit
9. USD/JPY exchange rate identity and quotation unit
10. Futures unit formatting (`USD / bbl`, `USD / t oz`)
11. FX quotation unit formatting (`USD per £1`, `INR per $1`, etc.)
12. Positive commodity change direction (`UP`)
13. Negative commodity change direction (`DOWN`)
14. Flat threshold classification (`FLAT` within ±0.05%)
15. GBP/USD strengthening semantics (`GBP strengthened / USD weakened`)
16. GBP/USD weakening semantics (`GBP weakened / USD strengthened`)
17. USD/INR rise semantics (`USD strengthened / INR weakened`)
18. USD/INR fall semantics (`INR strengthened / USD weakened`)
19. USD/JPY rate semantics (`JPY weakened` on rise)
20. Historical normalization and daily series continuity
21. Historical duplicate timestamp deduplication
22. Future timestamp rejection guard
23. Cross-asset cache hit within TTL
24. Cross-asset cache expiry after TTL
25. Stale cache fallback handling
26. Single-instrument provider failure isolation
27. REMX never classified as commodity price
28. REMX methodology notice presence
29. Gold spot and futures identity not silently mixed
30. Cross-asset intelligence keyword affinity matching
31. Causality guard zero unsupported claim enforcement
32. `/markets` route survival during macro provider failure
33. Responsive macro pulse template rendering
34. Unchanged equity market functionality and existing tests green

---

## 11. Known Limitations & Deferred Items

1. **Intraday / Realtime Streaming**: Deferred (out of scope for Stage 2C; daily close rates used).
2. **Multi-Asset Market Focus Selection**: Market Focus currently retains equity index focus; data structures are canonically prepared for Stage 2D cross-asset extension.
3. **Standing Cron / Background Daemon**: Deployed on standard 15-min TTL request-driven cache.

---

## Conclusion
Stage 2C is **COMPLETE** and **PASSED**. The Global Markets page has successfully evolved into **Global Markets & Macro Intelligence**, delivering integrated equities, commodities, critical minerals, and FX context with strict asset identity, verified arithmetic, and zero unsupported causal assertions.
