import sys
import os
sys.path.insert(0, os.path.abspath("."))
import asyncio
from services.markets.service import get_market_service

async def run_live_verification():
    service = get_market_service()
    
    yields, y_stale = await service.get_sovereign_yields(force_refresh=True)
    policies, p_stale = await service.get_monetary_policy_rates(force_refresh=True)

    print("\n" + "=" * 95)
    print("STAGE 2D LIVE VERIFICATION TABLE — SOVEREIGN YIELDS")
    print("=" * 95)
    header = f"{'INSTRUMENT':<20} | {'PROVIDER':<25} | {'OBSERVATION DATE':<16} | {'LATEST':<8} | {'PREVIOUS':<8} | {'CHANGE BP':<10} | {'STALE?'}"
    print(header)
    print("-" * 95)

    for y in yields:
        chg = f"{y.change_basis_points:+.1f} bp"
        latest = f"{y.yield_percent:.2f}%" if y.yield_percent is not None else "N/A"
        prev = f"{y.previous_yield_percent:.2f}%" if y.previous_yield_percent is not None else "N/A"
        print(f"{y.display_name:<20} | {y.source:<25} | {y.market_date:<16} | {latest:<8} | {prev:<8} | {chg:<10} | {y.is_stale}")

    print("\n" + "=" * 115)
    print("STAGE 2D LIVE VERIFICATION TABLE — MONETARY POLICY RATES")
    print("=" * 115)
    p_header = f"{'CENTRAL BANK':<22} | {'POLICY INSTRUMENT':<35} | {'CURRENT RATE/RANGE':<20} | {'LAST ACTION':<12} | {'CHANGE BP':<10} | {'EFFECTIVE DATE':<14} | {'SOURCE'}"
    print(p_header)
    print("-" * 115)

    for p in policies:
        if p.lower_bound is not None and p.upper_bound is not None:
            rate_str = f"{p.lower_bound:.2f}–{p.upper_bound:.2f}%"
        elif p.rate is not None:
            rate_str = f"{p.rate:.2f}%"
        else:
            rate_str = "N/A"
        
        chg = f"{p.change_basis_points:+.1f} bp"
        print(f"{p.central_bank:<22} | {p.policy_rate_name:<35} | {rate_str:<20} | {p.action:<12} | {chg:<10} | {p.effective_date:<14} | {p.source}")

    print("\n" + "=" * 115)
    print("ARITHMETIC CHECKS:")
    for y in yields:
        if y.yield_percent is not None and y.previous_yield_percent is not None:
            calc_bp = round((y.yield_percent - y.previous_yield_percent) * 100, 1)
            assert calc_bp == pytest_approx_check(y.change_basis_points), f"Arithmetic mismatch for {y.display_name}"
            print(f"VERIFIED: {y.display_name} -> ({y.yield_percent}% - {y.previous_yield_percent}%) * 100 = {y.change_basis_points:+.1f} bp")

def pytest_approx_check(val):
    return val

if __name__ == "__main__":
    asyncio.run(run_live_verification())
