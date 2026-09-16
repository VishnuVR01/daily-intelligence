# Sprint 2 Stage 2C — Pre-Implementation Data Feasibility Audit

## Executive Summary

This report delivers the empirical data feasibility audit for candidate **Stage 2C Market Categories** (Energy, Precious Metals, Critical Minerals, and FX Pairs). 

Every instrument was tested against both existing application providers:
1. **Twelve Data API** (Primary live provider, evaluated for endpoint availability, currency units, and free-tier 8 credit/min rate limits).
2. **Yahoo Finance Chart API** (`v8/finance/chart/{symbol}?interval=1d&range=1y` fallback provider, evaluated for live quotes, metadata, and 1Y daily close historical series).

---

## 1. Live Provider Verification & Instrument Semantics

### 1.1 Energy (Brent Crude & WTI Crude)
- **Brent Crude (`BZ=F`)**:
  - **Twelve Data**: FAILED (Restricted on free tier / 429 credit cap).
  - **Yahoo Finance**: **SUCCESS** (`BZ=F`). Live: `$108.32 USD`, Prev: `$67.44 USD`, Change: `+$40.88 (+60.62%)`, Date: `2026-09-15`.
  - **Semantics**: **ICE Brent Crude Futures (Front-Month Continuous Contract)**. Priced in `USD per barrel` (`USD / bbl`). Trading hours: ICE 23h continuous (Sun 18:00 – Fri 17:00 EST).
  - **Historical Series**: **252 valid daily points** (2025-09-15 to 2026-09-15). 0 nulls, 0 duplicate dates, 0 future timestamps.
- **WTI Crude (`CL=F`)**:
  - **Twelve Data**: FAILED (Restricted on free tier / 429 credit cap).
  - **Yahoo Finance**: **SUCCESS** (`CL=F`). Live: `$105.50 USD`, Prev: `$63.30 USD`, Change: `+$42.20 (+66.67%)`, Date: `2026-09-15`.
  - **Semantics**: **NYMEX Light Sweet Crude Oil Futures (Front-Month Continuous Contract)**. Priced in `USD per barrel` (`USD / bbl`). Trading hours: NYMEX 23h continuous (Sun 18:00 – Fri 17:00 EST).
  - **Historical Series**: **252 valid daily points** (2025-09-15 to 2026-09-15). 0 nulls, 0 duplicate dates.

*Notice*: Neither instrument represents physical spot crude oil. Both represent front-month exchange continuous futures contracts and must be labelled as **Futures Contracts**.

---

### 1.2 Precious Metals (Gold & Silver)
- **Gold (`GC=F` / `XAU/USD`)**:
  - **Twelve Data**: **SUCCESS** (`XAU/USD`). Live: `$4,301.60 USD`, Prev: `$4,298.35 USD`.
  - **Yahoo Finance**: **SUCCESS** (`GC=F`). Live: `$4,343.20 USD`, Prev: `$3,719.00 USD`, Change: `+$624.20 (+16.78%)`, Date: `2026-09-15`.
  - **Semantics**: **COMEX Gold Futures (Front-Month Continuous)** (`GC=F`) / Spot Gold (`XAU/USD`). Priced in `USD per troy ounce` (`USD / t oz`). Trading hours: COMEX 23h continuous.
  - **Historical Series**: **252 valid daily points** (2025-09-15 to 2026-09-15).
- **Silver (`SI=F` / `XAG/USD`)**:
  - **Twelve Data**: FAILED (`XAG/USD` restricted to Grow/Venture tier).
  - **Yahoo Finance**: **SUCCESS** (`SI=F`). Live: `$64.32 USD`, Prev: `$42.52 USD`, Change: `+$21.80 (+51.28%)`, Date: `2026-09-15`.
  - **Semantics**: **COMEX Silver Futures (Front-Month Continuous)**. Priced in `USD per troy ounce` (`USD / t oz`). Trading hours: COMEX 23h continuous.
  - **Historical Series**: **252 valid daily points** (2025-09-15 to 2026-09-15).

---

### 1.3 Critical Minerals & Rare Earths Benchmark Evaluation
- **Access to Raw Spot Benchmark (NdPr Oxide)**:
  - **Result**: Neither Twelve Data nor Yahoo Finance provides an open spot commodity price feed for Neodymium-Praseodymium (NdPr) Oxide or raw rare earth elements. NdPr spot contracts are published exclusively by proprietary Asian Metal / Fastmarkets OTC index providers behind institutional paywalls.
  - **Falsification Guard**: invent/displaying a universal "Rare Earths Commodity Price" is methodologically invalid.
- **Candidate Instrument A — `REMX` (VanEck Rare Earth and Strategic Metals ETF)**:
  - **Twelve Data**: **SUCCESS** (`REMX`). Live: `$68.42 USD`, Prev: `$68.93 USD`.
  - **Yahoo Finance**: **SUCCESS** (`REMX`). Live: `$68.39 USD`, Prev: `$60.95 USD`, Change: `+$7.44 (+12.21%)`, Date: `2026-09-15`.
  - **Semantics**: **Global Market-Cap Weighted Equity ETF Proxy** tracking major rare-earth & strategic metal producers (MP Materials, Lynas, Albemarle, etc.). Priced in `USD per share`. Trading hours: NYSE Arca RTH (09:30–16:00 EST).
  - **Historical Series**: **252 valid daily points** (2025-09-15 to 2026-09-15).
- **Candidate Instrument B — `LYC.AX` (Lynas Rare Earths Ltd)**:
  - **Twelve Data**: FAILED (Australian ASX exchange restricted on free tier).
  - **Yahoo Finance**: **SUCCESS** (`LYC.AX`). Live: `$13.83 AUD`, Prev: `$14.30 AUD`, Change: `-$0.47 (-3.29%)`, Date: `2026-09-15`.
  - **Semantics**: Single corporate equity stock traded on ASX. Priced in `AUD per share`.
  - **Historical Series**: **255 valid daily points** (2025-09-15 to 2026-09-15).

#### **Rare Earths Recommendation**:
**Methodologically Strongest Choice: REMX (VanEck Rare Earth and Strategic Metals ETF)**.
`REMX` provides a diversified global index of rare earth producers, eliminating single-company corporate operational risk present in `LYC.AX`. The UI must explicitly label this instrument as:
`"Rare Earth & Strategic Metals Equity Proxy"`
and classify its asset type as `EQUITY PROXY` (not `COMMODITY`).

---

### 1.4 FX Pairs (Foreign Exchange)
- **GBP/USD (`GBPUSD=X`)**:
  - **Twelve Data & Yahoo**: **SUCCESS**. Live: `1.3477 USD`, Prev: `1.3553 USD`, Change: `-0.0076 (-0.56%)`, Date: `2026-09-15`.
  - **Semantics**: Base = `GBP` (£1), Quote = `USD` ($). **US Dollars received per 1 British Pound Sterling** (`USD per £1`).
  - **Historical Series**: **260 valid daily points** (2025-09-14 to 2026-09-15). 24/5 Interbank FX market.
- **EUR/USD (`EURUSD=X`)**:
  - **Twelve Data & Yahoo**: **SUCCESS**. Live: `1.1543 USD`, Prev: `1.1726 USD`, Change: `-0.0183 (-1.56%)`, Date: `2026-09-15`.
  - **Semantics**: Base = `EUR` (€1), Quote = `USD` ($). **US Dollars received per 1 Euro** (`USD per €1`).
  - **Historical Series**: **260 valid daily points** (2025-09-14 to 2026-09-15).
- **USD/INR (`USDINR=X`)**:
  - **Twelve Data & Yahoo**: **SUCCESS**. Live: `95.849 INR`, Prev: `88.2773 INR`, Change: `+7.5717 (+8.58%)`, Date: `2026-09-15`.
  - **Semantics**: Base = `USD` ($1), Quote = `INR` (₹). **Indian Rupees received per 1 US Dollar** (`INR per $1`).
  - **Historical Series**: **260 valid daily points** (2025-09-14 to 2026-09-15).
- **USD/JPY (`USDJPY=X`)**:
  - **Twelve Data & Yahoo**: **SUCCESS**. Live: `155.125 JPY`, Prev: `147.666 JPY`, Change: `+7.459 (+5.05%)`, Date: `2026-09-15`.
  - **Semantics**: Base = `USD` ($1), Quote = `JPY` (¥). **Japanese Yen received per 1 US Dollar** (`JPY per $1`).
  - **Historical Series**: **260 valid daily points** (2025-09-14 to 2026-09-15).

---

## 2. Evidence-Based Provider Feasibility Table

| Instrument | Asset Type | Provider | Symbol | Live | Previous | 1Y History | Unit | Semantics | Decision |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Brent Crude** | Futures Contract | Yahoo Finance (Primary) / Twelve Data (Fallback) | `BZ=F` / `BRENT` | 108.32 | 67.44 | **252 points** | `USD / bbl` | ICE Front-Month Continuous Futures | **ACCEPT WITH CAVEAT** |
| **WTI Crude** | Futures Contract | Yahoo Finance (Primary) / Twelve Data (Fallback) | `CL=F` / `WTI` | 105.50 | 63.30 | **252 points** | `USD / bbl` | NYMEX Front-Month Continuous Futures | **ACCEPT WITH CAVEAT** |
| **Gold** | Commodity / Futures | Twelve Data (Primary) / Yahoo Finance (Fallback) | `XAU/USD` / `GC=F` | 4,343.20 | 3,719.00 | **252 points** | `USD / t oz` | COMEX Front-Month Continuous / Spot Gold | **ACCEPT** |
| **Silver** | Futures Contract | Yahoo Finance (Primary) / Twelve Data (Fallback) | `SI=F` / `XAG/USD` | 64.32 | 42.52 | **252 points** | `USD / t oz` | COMEX Front-Month Continuous Futures | **ACCEPT WITH CAVEAT** |
| **Rare Earths Equity Proxy** | Equity ETF | Twelve Data (Primary) / Yahoo Finance (Fallback) | `REMX` | 68.39 | 60.95 | **252 points** | `USD / share` | VanEck Rare Earth & Strategic Metals Mining Index ETF | **ACCEPT WITH CAVEAT** |
| **Lynas Rare Earths** | Single Corporate Equity | Yahoo Finance | `LYC.AX` | 13.83 | 14.30 | **255 points** | `AUD / share` | Single ASX Listed Mining Company Stock | **REJECT** (Inferior to diversified ETF `REMX`) |
| **GBP / USD** | FX Spot Pair | Twelve Data (Primary) / Yahoo Finance (Fallback) | `GBP/USD` / `GBPUSD=X` | 1.3477 | 1.3553 | **260 points** | `USD per £1` | 24/5 Interbank FX Rate ($ per £1) | **ACCEPT** |
| **EUR / USD** | FX Spot Pair | Twelve Data (Primary) / Yahoo Finance (Fallback) | `EUR/USD` / `EURUSD=X` | 1.1543 | 1.1726 | **260 points** | `USD per €1` | 24/5 Interbank FX Rate ($ per €1) | **ACCEPT** |
| **USD / INR** | FX Spot Pair | Twelve Data (Primary) / Yahoo Finance (Fallback) | `USD/INR` / `USDINR=X` | 95.85 | 88.28 | **260 points** | `INR per $1` | 24/5 Interbank FX Rate (₹ per $1) | **ACCEPT** |
| **USD / JPY** | FX Spot Pair | Twelve Data (Primary) / Yahoo Finance (Fallback) | `USD/JPY` / `USDJPY=X` | 155.13 | 147.67 | **260 points** | `JPY per $1` | 24/5 Interbank FX Rate (¥ per $1) | **ACCEPT** |

---

## 3. Provider Limitations & Key Diagnostic Findings

1. **Twelve Data Free-Tier Rate Limits**:
   - Twelve Data imposes a strict limit of **8 API credits per minute** on the free tier.
   - Querying commodities (`BRENT`, `WTI`, `XAG/USD`) or international stocks (`LYC.AX`) returns `429 Rate Limit` or `Upgrade to Grow plan required`.
   - **Resolution**: Yahoo Finance chart API (`query1.finance.yahoo.com/v8/finance/chart/{symbol}`) serves as a reliable primary or fallback provider with 0 rate limit restrictions for all 10 instruments.

2. **Instrument Identity & Labelling Accuracy**:
   - Futures data (`BZ=F`, `CL=F`, `GC=F`, `SI=F`) must be explicitly identified as **Continuous Futures** rather than physical spot commodities.
   - `REMX` must be explicitly presented as **"Rare Earth & Strategic Metals Equity Proxy"** to prevent misleading users into believing it represents a spot rare-earth metal price.

---

## 4. Recommended Production Basket for Stage 2C

When Stage 2C implementation is approved, the recommended production basket consists of **9 instruments** across 4 distinct asset classes:

### **ENERGY**
1. **Brent Crude**: Display Name: `Brent Crude Futures` | Twelve Symbol: `BRENT` | Yahoo Symbol: `BZ=F` | Unit: `USD / bbl`
2. **WTI Crude**: Display Name: `WTI Crude Futures` | Twelve Symbol: `WTI` | Yahoo Symbol: `CL=F` | Unit: `USD / bbl`

### **PRECIOUS METALS**
3. **Gold**: Display Name: `Gold (Spot / COMEX)` | Twelve Symbol: `XAU/USD` | Yahoo Symbol: `GC=F` | Unit: `USD / t oz`
4. **Silver**: Display Name: `Silver Futures` | Twelve Symbol: `XAG/USD` | Yahoo Symbol: `SI=F` | Unit: `USD / t oz`

### **CRITICAL MINERALS**
5. **Rare Earths**: Display Name: `Rare Earth & Strategic Metals (Proxy)` | Twelve Symbol: `REMX` | Yahoo Symbol: `REMX` | Unit: `USD / share` | Category: `EQUITY PROXY`

### **FX PAIRS**
6. **GBP/USD**: Display Name: `GBP / USD` | Twelve Symbol: `GBP/USD` | Yahoo Symbol: `GBPUSD=X` | Unit: `USD per £1`
7. **EUR/USD**: Display Name: `EUR / USD` | Twelve Symbol: `EUR/USD` | Yahoo Symbol: `EURUSD=X` | Unit: `USD per €1`
8. **USD/INR**: Display Name: `USD / INR` | Twelve Symbol: `USD/INR` | Yahoo Symbol: `USDINR=X` | Unit: `INR per $1`
9. **USD/JPY**: Display Name: `USD / JPY` | Twelve Symbol: `USD/JPY` | Yahoo Symbol: `USDJPY=X` | Unit: `JPY per $1`

---

### PRE-IMPLEMENTATION AUDIT RESULT
### **AUDIT COMPLETE — READY FOR USER REVIEW**
