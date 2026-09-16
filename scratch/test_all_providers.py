import os
import json
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("MARKET_DATA_API_KEY", "").strip()

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def test_url(url: str, name: str):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read().decode('utf-8', errors='ignore')
            print(f"[{name}] SUCCESS | Status: {resp.status} | Length: {len(data)}")
            print("   Snippet:", repr(data[:150]))
            return True, data
    except Exception as exc:
        print(f"[{name}] FAILED | Error: {exc}")
        return False, str(exc)

def run():
    print("=" * 80)
    print("TESTING PROVIDER API ENDPOINTS FOR STAGE 2D")
    print("=" * 80)

    # 1. Twelve Data Quotes
    if api_key:
        td_symbols = "TNX,US10Y,UK10Y,DE10Y,JP10Y,IN10Y,FEDFUNDS"
        url = f"https://api.twelvedata.com/quote?symbol={td_symbols}&apikey={api_key}"
        test_url(url, "Twelve Data Yields & Rates")

    # 2. Yahoo Finance Yield Candidates
    yahoo_symbols = [
        "^TNX",       # US 10-Year Treasury Yield Index (CBOE)
        "^TYX",       # US 30-Year Treasury Yield Index
        "^FVX",       # US 5-Year Treasury Yield Index
        "^IRX",       # US 13-Week Treasury Bill Yield Index
        "^GILT",      # UK Gilt candidate
        "0P0000X97G.F",# German Bund proxy
        "DE10Y.EX",   # German Bund
        "GB10Y.L",    # UK Gilt
        "JP10Y.T",    # Japan 10Y
        "IN10Y.NS",   # India 10Y
    ]
    for sym in yahoo_symbols:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=5d"
        test_url(url, f"Yahoo {sym}")

    # 3. Bank of England Official API
    boe_url = "https://www.bankofengland.co.uk/boestat/iadb/fromshowline.asp?csv.x=yes&SeriesCode=IUDBEDR"
    test_url(boe_url, "Bank of England Official CSV")

    # 4. ECB Official API
    ecb_url = "https://sdw-wsrest.ecb.europa.eu/service/data/FM/M.U2.EUR.4F.KR.DFR_RT.LEV?lastNObservations=5"
    test_url(ecb_url, "ECB Data Portal REST API")

if __name__ == "__main__":
    run()
