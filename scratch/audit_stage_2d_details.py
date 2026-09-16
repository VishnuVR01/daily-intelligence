"""
Detailed audit script testing FRED CSV endpoints and alternative market data symbols for Stage 2D.
"""
import urllib.request
import json
import csv
import io
from datetime import datetime, timezone

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_fred_csv(series_id: str):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                content = resp.read().decode('utf-8')
                reader = csv.reader(io.StringIO(content))
                header = next(reader, None)
                rows = [r for r in reader if len(r) == 2 and r[1] != "." and r[1] != ""]
                if rows:
                    latest = rows[-1]
                    prev = rows[-2] if len(rows) >= 2 else None
                    return {
                        "series_id": series_id,
                        "status": "SUCCESS",
                        "total_rows": len(rows),
                        "latest_date": latest[0],
                        "latest_value": float(latest[1]),
                        "prev_date": prev[0] if prev else None,
                        "prev_value": float(prev[1]) if prev else None,
                    }
    except Exception as exc:
        return {"series_id": series_id, "status": "FAILED", "error": str(exc)}
    return {"series_id": series_id, "status": "NO_DATA"}

def test_yahoo_symbol(symbol: str):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=10d"
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
                        "shortName": meta.get("shortName") or meta.get("longName") or symbol,
                        "regularMarketPrice": meta.get("regularMarketPrice"),
                        "chartPreviousClose": meta.get("chartPreviousClose"),
                        "closes": quotes,
                    }
    except Exception as exc:
        return {"symbol": symbol, "status": "FAILED", "error": str(exc)}
    return {"symbol": symbol, "status": "NO_DATA"}

def run_detailed_audit():
    print("=" * 80)
    print("STAGE 2D DETAILED PROVIDER AUDIT (FRED CSV & YAHOO SYMBOLS)")
    print("=" * 80)

    # 1. Test FRED Series via CSV Endpoint
    fred_series_to_test = {
        # Sovereign Yields
        "US_10Y_DGS10": "DGS10",                    # 10-Year Treasury Constant Maturity Rate
        "UK_10Y_IRLTLT01GBM156N": "IRLTLT01GBM156N",# UK 10-Year Govt Bond Yield
        "DE_10Y_IRLTLT01DEM156N": "IRLTLT01DEM156N",# Germany 10-Year Govt Bond Yield
        "JP_10Y_IRLTLT01JPM156N": "IRLTLT01JPM156N",# Japan 10-Year Govt Bond Yield
        "IN_10Y_INTGSB10YM": "INTGSB10YM",         # India 10-Year Govt Securities Yield
        
        # Central Bank Policy Rates
        "FED_TARGET_LOWER_DFEDTARL": "DFEDTARL",    # Fed Funds Target Range Lower
        "FED_TARGET_UPPER_DFEDTARU": "DFEDTARU",    # Fed Funds Target Range Upper
        "FED_EFFECTIVE_FEDFUNDS": "FEDFUNDS",       # Effective Fed Funds Rate
        "BOE_BANK_RATE_INTDSRGBM193N": "INTDSRGBM193N", # BoE Discount/Bank Rate
        "ECB_DEPOSIT_ECBDFR": "ECBDFR",            # ECB Deposit Facility Rate
        "ECB_REFI_ECBMRR": "ECBMRR",              # ECB Main Refinancing Operations Rate
        "ECB_MARGINAL_ECBMLFR": "ECBMLFR",         # ECB Marginal Lending Facility Rate
        "BOJ_POLICY_INTDSRJPM193N": "INTDSRJPM193N", # Bank of Japan Policy Rate
        "RBI_REPO_INTDSRINM193N": "INTDSRINM193N",   # RBI Repo/Discount Rate
    }

    print("\n--- FRED CSV ENDPOINTS AUDIT ---")
    fred_results = {}
    for name, s_id in fred_series_to_test.items():
        res = fetch_fred_csv(s_id)
        fred_results[name] = res
        print(f"FRED {name:30s} ({s_id:18s}): {res.get('status')} | Date: {res.get('latest_date')} | Val: {res.get('latest_value')} | Prev: {res.get('prev_value')}")

    # 2. Test Yahoo Finance Candidates
    yahoo_symbols_to_test = [
        "^TNX",       # US 10-Year Treasury Yield Index (CBOE)
        "^TYX",       # US 30-Year Treasury Yield Index
        "^FVX",       # US 5-Year Treasury Yield Index
        "^IRX",       # US 13-Week Treasury Bill Yield Index
        "0P0000X97G.F", # German Bund ETF / Yield proxy candidate
        "^GILT",      # UK Gilt candidate
        "BUND",       # Bund candidate
    ]
    print("\n--- YAHOO FINANCE SYMBOLS AUDIT ---")
    yahoo_results = {}
    for sym in yahoo_symbols_to_test:
        res = test_yahoo_symbol(sym)
        yahoo_results[sym] = res
        print(f"Yahoo {sym:15s}: {res.get('status')} | Name: {res.get('shortName')} | Price: {res.get('regularMarketPrice')}")

    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fred_results": fred_results,
        "yahoo_results": yahoo_results,
    }

    with open("scratch/sprint_2d_detailed_audit.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

if __name__ == "__main__":
    run_detailed_audit()
