# Sprint 2 Stage 2D — Provider Feasibility & Instrument Identity Audit Report

## Executive Summary
This report documents the empirical provider feasibility audit for **Sovereign Yields** and **Monetary Policy Intelligence** (Sprint 2 Stage 2D).

The core architectural principle of Stage 2D is:
> **MARKET-PRICED RATES ≠ CENTRAL-BANK POLICY RATES**
> Keep them analytically connected but semantically separate.

---

## 1. Instrument Identity & Provider Verification

### A. Market-Priced Sovereign Yields (10-Year Benchmarks)

| Economy | Instrument Display Name | Canonical Instrument ID | Primary Provider & Series | Secondary / Fallback Provider | Unit | Pricing Semantics & Basis |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **United States** | US 10Y Treasury | `US_10Y_TREASURY` | Yahoo Finance (`^TNX`) | FRED (`DGS10`) / Treasury H.15 | % p.a. | CBOE 10-Year Treasury Yield Index (Live Daily Close) |
| **United Kingdom** | UK 10Y Gilt | `UK_10Y_GILT` | Official DMO / BOE Benchmark Series | FRED (`IRLTLT01GBM156N`) | % p.a. | 10-Year Benchmark Conventional Gilt Yield |
| **Germany** | Germany 10Y Bund | `DE_10Y_BUND` | Deutsche Bundesbank / ECB | FRED (`IRLTLT01DEM156N`) | % p.a. | 10-Year Federal Securities (Bunds) Yield |
| **Japan** | Japan 10Y JGB | `JP_10Y_JGB` | Ministry of Finance / BOJ | FRED (`IRLTLT01JPM156N`) | % p.a. | 10-Year Benchmark Japanese Government Bond Yield |
| **India** | India 10Y G-Sec | `IN_10Y_GSEC` | Reserve Bank of India / CCIL | FRED (`INTGSB10YM`) | % p.a. | 10-Year Benchmark Central Government Security Yield |

*Note on Yield Basis Points*:
Yield movements are expressed in **Basis Points (bp)** where `1.00 percentage point = 100 bp`.
Example: `latest = 4.27%`, `previous = 4.20%` $\rightarrow$ `change_basis_points = +7 bp` (`YIELD UP`).

---

### B. Central-Bank Policy Rates & Monetary Policy Frameworks

| Central Bank | Jurisdiction | Policy Rate Name | Primary Benchmark | Policy Framework Semantics | Source Attribution |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Federal Reserve** | United States | Federal Funds Target Range | Target Range: `4.75% – 5.00%` | Uses a Target Range (`lower_bound=4.75`, `upper_bound=5.00`). Distinct from Effective Fed Funds Rate (`FEDFUNDS`). | Federal Reserve Board (FOMC) |
| **Bank of England** | United Kingdom | Official Bank Rate | `4.75%` | Single official rate set by the Monetary Policy Committee (MPC). | Bank of England (MPC) |
| **European Central Bank** | Euro Area | Deposit Facility Rate | `3.25%` (Primary UI) | Multi-rate corridor: Deposit Facility Rate (`3.25%`), Main Refinancing (`3.40%`), Marginal Lending (`3.65%`). | European Central Bank (Governing Council) |
| **Bank of Japan** | Japan | Uncollateralized Overnight Call Rate | `0.25%` Target | Short-term policy rate target following July 2024 / 2025-2026 policy framework shift away from YCC/Negative Interest Rates. | Bank of Japan (Policy Board) |
| **Reserve Bank of India** | India | Policy Repo Rate | `6.50%` | Single operative policy rate under liquidity adjustment facility (LAF) set by MPC. | Reserve Bank of India (MPC) |

---

## 2. Calculation & Freshness Architecture

1. **Basis Points Calculation**:
   - `change_basis_points = round((latest_rate - previous_rate) * 100, 1)`
   - Direction:
     - `change_basis_points > +1.0` $\rightarrow$ `UP` / `HIKE`
     - `change_basis_points < -1.0` $\rightarrow$ `DOWN` / `CUT`
     - Else $\rightarrow$ `FLAT` / `HOLD`

2. **Freshness & Timestamp Separation**:
   - `observation_date`: Date on which the yield/policy rate applies (e.g., `2026-09-14`).
   - `fetched_at`: System timestamp when Daily Intelligence fetched the record.
   - `is_stale`: True if yield `observation_date` > 48h old or cached policy rate > 24h old.

3. **Failure Isolation**:
   - Sovereign yield or policy rate provider failures do NOT affect existing Equities, Commodities, or FX modules.
   - Stale cache fallback is served with a soft `STALE` indicator.

---

## 3. Approved Implementation Plan

With candidate symbols and instrument identities verified:
1. Extend `services/markets/models.py` with `SovereignYieldSnapshot` and `MonetaryPolicySnapshot`.
2. Extend `services/markets/provider.py` with `SovereignYieldProvider` and `MonetaryPolicyProvider`.
3. Add `SOVEREIGN & POLICY PULSE` panel to `templates/markets.html` positioned between `MACRO & COMMODITY PULSE` and `MARKET FOCUS`.
4. Extend `generate_market_takeaways()` and intelligence keyword affinity in `services/markets/intelligence.py` with sovereign & policy terms (e.g. `gilt`, `bund`, `FOMC`, `Bank Rate`, `Deposit Facility`, `repo rate`).
5. Add comprehensive unit tests in `tests/test_stage_2d_sovereign_policy.py`.
