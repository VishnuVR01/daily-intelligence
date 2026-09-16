"""
Audit script for Stage 2D Provider Feasibility:
Tests sovereign 10Y yield symbols and central bank policy rate endpoints.
"""
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def test_yahoo_symbol(symbol: str):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode('utf-8'))
                result = data.get("chart", {}).get("result", [])
                if result:
                    meta = result[0].get("meta", {})
                    quotes = [c for c in result[0].get("indicators", {}).get("quote", [{}])[0].get("close", []) if c is not None]
                    return {
                        "symbol": symbol,
                        "status": "SUCCESS",
                        "regularMarketPrice": meta.get("regularMarketPrice"),
                        "chartPreviousClose": meta.get("chartPreviousClose"),
                        "recent_closes": quotes,
                        "instrumentType": meta.get("instrumentType"),
                        "shortName": meta.get("shortName"),
                        "longName": meta.get("longName"),
                        "currency": meta.get("currency"),
                    }
    except Exception as exc:
        return {"symbol": symbol, "status": "FAILED", "error": str(exc)}
    return {"symbol": symbol, "status": "NO_DATA"}

def test_fred_series(series_id: str):
    # FRED web observation endpoint (public JSON API)
    url = f"https://fred.stlouisfed.org/graph/fredgraph.json?id={series_id}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode('utf-8'))
                obs = data.get("obs", []) if isinstance(data, dict) else []
                if obs:
                    valid_obs = [o for o in obs if o.get("v") != "."]
                    latest = valid_obs[-1] if valid_obs else None
                    prev = valid_obs[-2] if len(valid_obs) >= 2 else None
                    return {
                        "series_id": series_id,
                        "status": "SUCCESS",
                        "count": len(valid_obs),
                        "latest_date": latest.get("d") if latest else None,
                        "latest_val": latest.get("v") if latest else None,
                        "prev_date": prev.get("d") if prev else None,
                        "prev_val": prev.get("v") if prev else None,
                    }
    except Exception as exc:
        return {"series_id": series_id, "status": "FAILED", "error": str(exc)}
    return {"series_id": series_id, "status": "NO_DATA"}

def run_audit():
    print("=" * 80)
    print("STAGE 2D PROVIDER FEASIBILITY AUDIT")
    print("=" * 80)

    # 1. Sovereign Yield Candidates (Yahoo Finance)
    print("\n--- TESTING YAHOO FINANCE YIELD CANDIDATES ---")
    yahoo_yield_candidates = [
        "^TNX",       # US 10Y CBOE Treasury Yield Index
        "US10Y=X",    # US 10Y
        "^TGGB10Y.L", # UK 10Y Gilt
        "GB10Y=X",    # UK 10Y
        "^TBUND10Y.L",# German 10Y Bund
        "DE10Y=X",    # German 10Y
        "^TJGB10Y.L", # Japan 10Y JGB
        "JP10Y=X",    # Japan 10Y
        "^TIN10Y.L",  # India 10Y G-Sec
        "IN10Y=X",    # India 10Y
    ]
    yahoo_results = {}
    for sym in yahoo_yield_candidates:
        res = test_yahoo_symbol(sym)
        yahoo_results[sym] = res
        print(f"Yahoo {sym:12s}: {res.get('status')} | Price/Yield: {res.get('regularMarketPrice')} | Name: {res.get('shortName') or res.get('longName')}")

    # 2. Sovereign Yield & Central Bank Candidates (FRED / St. Louis Fed Official Data)
    print("\n--- TESTING FRED / OFFICIAL STATISTICAL SERIES ---")
    fred_candidates = {
        # Sovereign Yields
        "US_10Y_FRED": "DGS10",          # 10-Year Treasury Constant Maturity Rate
        "UK_10Y_FRED": "IRLTLT01GBM156N",# 10-Year Government Bond Yields for UK
        "DE_10Y_FRED": "IRLTLT01DEM156N",# 10-Year Government Bond Yields for Germany
        "JP_10Y_FRED": "IRLTLT01JPM156N",# 10-Year Government Bond Yields for Japan
        "IN_10Y_FRED": "INTGSB10YM",     # 10-Year Government Securities Yield for India
        
        # Central Bank Policy Rates / Ranges
        "FED_TARGET_LOWER": "DFEDTARL",  # Federal Funds Target Range - Lower Limit
        "FED_TARGET_UPPER": "DFEDTARU",  # Federal Funds Target Range - Upper Limit
        "FED_EFFECTIVE": "FEDFUNDS",     # Effective Federal Funds Rate
        "BOE_BANK_RATE": "INTDSRGBM193N",# Bank of England Bank Rate / Discount Rate
        "ECB_DEPOSIT_RATE": "ECBDFR",    # ECB Deposit Facility Rate
        "ECB_MAIN_REFI": "ECBMRR",       # ECB Main Refinancing Operations Rate
        "ECB_MARGINAL_LENDING": "ECBMLFR",# ECB Marginal Lending Facility Rate
        "BOJ_POLICY_RATE": "INTDSRJPM193N",# Bank of Japan Policy Rate
        "RBI_REPO_RATE": "INTDSRINM193N",  # RBI Discount Rate / Repo Rate
    }
    fred_results = {}
    for key, series_id in fred_candidates.items():
        res = test_fred_series(series_id)
        fred_results[key] = res
        print(f"FRED {key:20s} ({series_id:16s}): {res.get('status')} | Latest ({res.get('latest_date')}): {res.get('latest_val')}")

    audit_output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "yahoo_results": yahoo_results,
        "fred_results": fred_results,
    }

    with open("scratch/sprint_2d_provider_audit.json", "w", encoding="utf-8") as f:
        json.dumps(audit_output, f, indent=2)

    with open("scratch/sprint_2d_provider_audit.json", "w", encoding="utf-8") as f:
        json.dump(audit_output, f, indent=2)

if __name__ == "__main__":
    run_audit()
