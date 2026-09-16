# Sprint 2 Stage 2B — Global Markets Intelligence Page & UI Hierarchy Refinement Report

## Executive Summary

Stage 2B introduces a dedicated **Global Markets Intelligence Page** (`/markets`), uniting live market data snapshots, 1Y daily close SVG trend line charts, 52W & YTD statistical context, a deterministic exchange session status engine, market-affinity intelligence matching, strict causality evidence classification (`MARKET_MOVING` vs `RELATED`), and grounded market takeaways.

Refinement in Stage 2B reorganized the page information hierarchy into an intuitive Warm Editorial newspaper flow:
$$\text{Page Header} \longrightarrow \text{Key Takeaways} \longrightarrow \text{Global Market Pulse Grid (3}\times\text{2)} \longrightarrow \text{Market Focus (SVG Chart + 52W/YTD Stats)} \longrightarrow \text{Market Intelligence}$$

---

## 1. Architecture & Component Stack

### Architecture Overview
- **Dedicated Route**: `/markets` featuring full Warm Editorial design system.
- **Historical Data Engine** (`services/markets/historical.py`): Documented Yahoo Finance `v8/finance/chart/{symbol}?interval=1d&range=1y` provider, parsing ~252 daily close points, deduplicating dates, and storing series in a **6-Hour In-Memory Cache** (`HISTORICAL_CACHE_TTL_SECONDS = 21600`).
- **SVG Mini Chart Generator** (`generate_svg_mini_chart`): Pure Python server-rendered vector line chart with responsive `viewBox`, gradient fill (`rgba(46,89,66,0.12)` / `rgba(199,106,76,0.12)`), and dynamic green/terracotta direction styling.
- **Statistical Computations**:
  - **52W High**: `max(closes)` in 1Y daily window.
  - **52W Low**: `min(closes)` in 1Y daily window.
  - **Distance from 52W High %**: `((latest_close - high_52w) / high_52w) * 100.0`.
  - **YTD Change %**: `((latest_close - ytd_first_close) / ytd_first_close) * 100.0` (matching first valid close on/after Jan 1 of current year).
- **Session Engine** (`services/markets/sessions.py`): Timezone-aware regular trading hours state (`OPEN`, `CLOSED`, `PRE-MARKET`, `AFTER-HOURS`).
- **Intelligence Matching** (`services/markets/intelligence.py`): Deterministic market-affinity scoring and strict causality evidence classification (`MARKET_MOVING` vs `RELATED`).
- **Grounded Takeaways**: 3 compact cards (`GLOBAL SENTIMENT`, `MARKET FOCUS`, `COVERAGE NOTICE`) placed near the top.
- **Homepage Integration**: Compact market session status dot added to homepage market cards with a direct `View Global Markets →` link.

---

## 2. Page Structure & Information Architecture

The refined `/markets` page follows an intuitive, scannable order:

1. **PAGE HEADER**:
   - Title, subtitle, market data timestamp, provider attribution, TTL cache state, exchange-holiday disclaimer banner.
2. **KEY TAKEAWAYS**:
   - Compact 3-card block (`GLOBAL SENTIMENT`, `MARKET FOCUS`, `COVERAGE NOTICE`).
3. **GLOBAL MARKET PULSE**:
   - Compact 3×2 grid displaying all 6 equity indices (S&P 500, FTSE 100, NIFTY 50, Nikkei 225, STOXX Europe 600, CSI 300) with session status dots (`● OPEN`, `● CLOSED`), prices, and directional change pills. Redundant "Focus →" prompts removed to make cards clean selection shortcuts.
4. **MARKET FOCUS**:
   - Header with active market `<select>` dropdown (`United States — S&P 500`, `United Kingdom — FTSE 100`, `India — NIFTY 50`, `Japan — Nikkei 225`, `Europe — STOXX Europe 600`, `China — CSI 300`), live session badge, price, and change.
   - **1Y SVG Line Chart**: Clean vector chart displaying daily completed close trend.
   - **52-Week & YTD Metrics Grid**: 52W High, 52W Low, Distance from High %, and YTD Change %.
   - **Featured Intelligence Story**: Highest-scoring matched story with explicit grounding explanation.
5. **MARKET INTELLIGENCE**:
   - Section heading (`MARKET INTELLIGENCE`) with 4–6 article cards tagged with `★ MARKET-MOVING` or `RELATED` badges.

---

## 3. Market Session Rules & RTH Schedule

| Region | Index | Exchange | Timezone | Regular Trading Hours | Weekdays |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **United States** | S&P 500 | NYSE / NASDAQ | `America/New_York` | 09:30 - 16:00 | Mon - Fri |
| **United Kingdom**| FTSE 100 | LSE | `Europe/London` | 08:00 - 16:30 | Mon - Fri |
| **India** | NIFTY 50 | NSE / BSE | `Asia/Kolkata` | 09:15 - 15:30 | Mon - Fri |
| **Japan** | Nikkei 225 | TSE | `Asia/Tokyo` | 09:00 - 11:30 & 12:30 - 15:30 | Mon - Fri |
| **Europe** | STOXX 600 | STOXX | `Europe/Paris` | 09:00 - 17:30 | Mon - Fri |
| **China** | CSI 300 | SSE / SZSE | `Asia/Shanghai` | 09:30 - 11:30 & 13:00 - 15:00 | Mon - Fri |

---

## 4. Market-Affinity & Causality Evidence Rules

- **`MARKET_MOVING`**: Strictly assigned ONLY when title or summary text contains explicit market-moving phrases.
- **`RELATED`**: Assigned to contextual background stories providing macroeconomic or sector context.
- **Audit Result**: 10-story audit completed with **0** unsupported `MARKET_MOVING` claims.

---

## 5. Stage 2B.1 — Market Focus UX & China CSI 300 Diagnostics

### 5.1 Market Focus Dropdown & UX Enhancement
- **Header Selector**: Added a `<select name="market" id="market-focus-select">` inside the `MARKET FOCUS` section header containing all six tracked markets:
  - `United States — S&P 500` (`us`)
  - `United Kingdom — FTSE 100` (`uk`)
  - `India — NIFTY 50` (`india`)
  - `Japan — Nikkei 225` (`japan`)
  - `Europe — STOXX Europe 600` (`europe`)
  - `China — CSI 300` (`china`)
- **Progressive Enhancement**:
  - Implemented vanilla JavaScript DOM swapping for `#focus-section`, `.takeaways-panel`, and `.pulse-grid` via `fetch('/markets?market=' + slug)`.
  - Full document reload eliminated for interactive dropdown changes.
  - Updates browser URL location bar via `window.history.pushState(null, '', url)` and handles `popstate` browser back/forward navigation.
- **Progressive Fallback**: Server-rendered GET query parameter routes (`/markets?market=uk`, `/markets?market=china`) remain 100% functional with `<noscript>` submit buttons and standard form actions.
- **Uncluttered Pulse Cards**: Removed redundant `"Focus →"` prompt text from the 6 pulse grid cards, turning each card into a clean, accessible selection link.

### 5.2 China CSI 300 Historical Data Diagnostics & Root Cause
- **Instrument Identity Verification**:
  - `000300.SS` is the official, correct Yahoo Finance ticker symbol for the China CSI 300 Index.
  - `399972` is the corresponding Twelve Data symbol.
  - Live snapshot quote fetch succeeds (`4,450.04 CNY`).
- **Root Cause**:
  - Querying `query1.finance.yahoo.com/v8/finance/chart/000300.SS?interval=1d&range=1y` returns `Total Points: 1` (only the spot quote snapshot).
  - Yahoo Finance's public chart API does **not** index or serve historical daily bar series for Chinese index tickers (`000300.SS`, `399300.SZ`, `399972.SZ`).
  - US-traded ETFs such as `ASHR` or `CNYA` return historical data but are priced in USD on US exchanges and represent ETFs, not the underlying CSI 300 index in CNY. Substituting `ASHR` for `000300.SS` would break index identity.
- **Failure State Implementation**:
  - In `services/markets/historical.py`, `fetch_historical_series_yahoo` explicitly returns `None` if fewer than 2 valid daily points are returned (`if len(raw_points) < 2: return None`).
  - Current market snapshot for China CSI 300 continues working seamlessly (showing latest close, daily change, direction, close date, session status, and market intelligence stories).
  - Historical chart and 52W stats panel explicitly display:
    `"Historical series temporarily unavailable."`
  - Zero fake data, zero 0-values, and zero cross-market index substitution.

---

## 6. Files Created & Modified

### New Files Created
1. [`services/markets/historical.py`](file:///d:/Daily-Intelligence/services/markets/historical.py)
2. [`services/markets/sessions.py`](file:///d:/Daily-Intelligence/services/markets/sessions.py)
3. [`services/markets/intelligence.py`](file:///d:/Daily-Intelligence/services/markets/intelligence.py)
4. [`templates/markets.html`](file:///d:/Daily-Intelligence/templates/markets.html)
5. [`tests/test_markets_historical.py`](file:///d:/Daily-Intelligence/tests/test_markets_historical.py)
6. [`tests/test_markets_intelligence.py`](file:///d:/Daily-Intelligence/tests/test_markets_intelligence.py)

### Modified Files
1. [`services/markets/__init__.py`](file:///d:/Daily-Intelligence/services/markets/__init__.py)
2. [`services/markets/service.py`](file:///d:/Daily-Intelligence/services/markets/service.py)
3. [`app/main.py`](file:///d:/Daily-Intelligence/app/main.py)
4. [`templates/base.html`](file:///d:/Daily-Intelligence/templates/base.html)
5. [`templates/index.html`](file:///d:/Daily-Intelligence/templates/index.html)
6. [`static/css/main.css`](file:///d:/Daily-Intelligence/static/css/main.css)

---

## 7. Final Test Suite Results

- **Command**: `python -m pytest -q`
- **Total Tests**: **285** (246 Stage 2A baseline + 23 Stage 2B intelligence tests + 9 Stage 2B historical tests + 7 Stage 2B.1 UX/China tests)
- **Passed**: **285 (100% Green)**
- **Failed**: **0**

---

## 8. Stage 2C Provider Feasibility Notes (REPORT ONLY)

Below is the technical feasibility evaluation for candidate Stage 2C market categories (Energy, Precious Metals, Critical Minerals, and FX pairs).

### Feasibility Table

| Category | Benchmark Instrument | Candidate Provider | Provider Symbol | Free Tier Availability | Latest Sample Price / Rate | Previous Close / Rate | 1Y History Availability | Currency / Unit | Trading / Session Semantics | API Cost | Reliability Concerns |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **ENERGY** | Brent Crude | Yahoo / Twelve Data | `BZ=F` (Yahoo) / `BRENT` (Twelve) | **Yes** | 108.45 | 67.44 | **252 points** | `USD / bbl` | ICE Futures 23h continuous (Sun-Fri 18:00–17:00 EST) | Free | Futures roll-over gaps on front-month contracts. |
| **ENERGY** | WTI Crude | Yahoo / Twelve Data | `CL=F` (Yahoo) / `WTI` (Twelve) | **Yes** | 105.69 | 63.30 | **252 points** | `USD / bbl` | NYMEX 23h continuous (Sun-Fri 18:00–17:00 EST) | Free | High intraday volatility; front-month settlement roll dates. |
| **PRECIOUS METALS** | Gold | Yahoo / Twelve Data | `GC=F` (Yahoo) / `XAU/USD` (Twelve) | **Yes** | 4,348.60 | 3,719.00 | **252 points** | `USD / t oz` | COMEX 23h continuous (Sun-Fri 18:00–17:00 EST) | Free | Highly reliable spot/futures data feeds. |
| **PRECIOUS METALS** | Silver | Yahoo / Twelve Data | `SI=F` (Yahoo) / `XAG/USD` (Twelve) | **Yes** | 64.36 | 42.52 | **252 points** | `USD / t oz` | COMEX 23h continuous (Sun-Fri 18:00–17:00 EST) | Free | High variance during thin liquidity windows. |
| **CRITICAL MINERALS** | Rare-Earth Benchmark (VanEck ETF) | Yahoo / Twelve Data | `REMX` (Yahoo) / `REMX` (Twelve) | **Yes** | 68.36 | 60.95 | **252 points** | `USD` | NYSE Arca RTH (09:30–16:00 EST) | Free | Direct NdPr Oxide spot contracts require paid proprietary metal feeds (Fastmarkets/Platts). `REMX` ETF acts as an open, defensible miner/basket proxy. |
| **CRITICAL MINERALS** | Rare-Earth Producer (Lynas Ltd) | Yahoo / Twelve Data | `LYC.AX` (Yahoo) / `LYC` (Twelve) | **Yes** | 13.83 | 14.30 | **255 points** | `AUD` | ASX RTH (10:00–16:00 AEST) | Free | Single corporate producer price rather than pure commodity index. |
| **FX** | GBP / USD | Yahoo / Twelve Data | `GBPUSD=X` (Yahoo) / `GBP/USD` (Twelve) | **Yes** | 1.3479 | 1.3553 | **260 points** | `USD per GBP` | 24/5 Global Interbank FX (Sun 17:00–Fri 17:00 EST) | Free | Highly reliable interbank mid-rate series. |
| **FX** | EUR / USD | Yahoo / Twelve Data | `EURUSD=X` (Yahoo) / `EUR/USD` (Twelve) | **Yes** | 1.1546 | 1.1726 | **260 points** | `USD per EUR` | 24/5 Global Interbank FX | Free | Benchmark liquid pair. |
| **FX** | USD / INR | Yahoo / Twelve Data | `USDINR=X` (Yahoo) / `USD/INR` (Twelve) | **Yes** | 95.85 | 88.28 | **260 points** | `INR per USD` | 24/5 Interbank FX | Free | RBI onshore vs offshore NDF rate differentials during market close. |
| **FX** | USD / JPY | Yahoo / Twelve Data | `USDJPY=X` (Yahoo) / `USD/JPY` (Twelve) | **Yes** | 155.07 | 147.67 | **260 points** | `JPY per USD` | 24/5 Interbank FX | Free | High intervention volatility around BOJ policy dates. |

#### Notes on Commodity Modeling:
1. **Crude Oil**: Brent (`BZ=F`) and WTI (`CL=F`) represent the two global benchmarks. A third generic "Crude Oil" item must **not** be created.
2. **Rare Earths**: NdPr Oxide spot contracts are not available on open public ticker endpoints without proprietary licensing. `REMX` (VanEck Rare Earth/Strategic Metals ETF) or `LYC.AX` (Lynas Rare Earths) provides a credible, defensible benchmark proxy for public intelligence tracking.

---

### STAGE 2B.1 ACCEPTANCE RESULT
### **STAGE 2B.1: PASS**
