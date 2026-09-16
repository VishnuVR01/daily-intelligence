import asyncio
import sys
sys.path.insert(0, '.')
from services.markets.service import get_market_service

async def main():
    service = get_market_service()
    print("Fetching live macro & commodity cross-asset snapshots...")
    snaps, is_stale = await service.get_macro_commodities(force_refresh=True)
    print(f"Total snapshots returned: {len(snaps)} (stale: {is_stale})\n")
    print(f"{'Canonical ID':<22} | {'Display Name':<32} | {'Symbol':<10} | {'Latest':<10} | {'Previous':<10} | {'Change':<8} | {'Change %':<9} | {'Unit':<15} | {'Source':<20}")
    print("-" * 150)
    for s in snaps:
        print(f"{s.canonical_id or s.symbol:<22} | {s.display_name:<32} | {s.symbol:<10} | {s.latest_close:<10.4f} | {s.previous_close:<10.4f} | {s.change_value:<8.4f} | {s.change_percent:<8.2f}% | {s.unit or s.currency:<15} | {s.source:<20}")
    
    print("\n--- Manual Arithmetic Verification ---")
    for check_id in ["BRENT_CRUDE_FUTURES", "GOLD_FUTURES", "GBP_USD", "USD_INR"]:
        match = next((s for s in snaps if s.canonical_id == check_id), None)
        if match:
            expected_change = match.latest_close - match.previous_close
            expected_pct = (expected_change / match.previous_close) * 100 if match.previous_close else 0
            diff_val = abs(match.change_value - expected_change)
            diff_pct = abs(match.change_percent - expected_pct)
            status = "OK" if diff_val < 0.0001 and diff_pct < 0.01 else "DISCREPANCY"
            print(f"[{status}] {match.display_name} ({match.symbol}): latest={match.latest_close:.6f}, prev={match.previous_close:.6f}, calc_change={match.change_value:.6f}, exp_change={expected_change:.6f}, calc_pct={match.change_percent:.4f}%, exp_pct={expected_pct:.4f}%")

if __name__ == "__main__":
    asyncio.run(main())
