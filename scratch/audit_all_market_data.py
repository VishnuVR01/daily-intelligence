import sys
import os
sys.path.insert(0, os.path.abspath("."))
import asyncio
import json
from services.markets.service import get_market_service

async def audit_all_markets():
    service = get_market_service()

    equities, eq_stale = await service.get_global_markets(force_refresh=True)
    cross_assets, ca_stale = await service.get_macro_commodities(force_refresh=True)
    yields, y_stale = await service.get_sovereign_yields(force_refresh=True)
    policies, p_stale = await service.get_monetary_policy_rates(force_refresh=True)

    print("\n" + "=" * 110)
    print("1. EQUITY INDICES VERIFICATION")
    print("=" * 110)
    print(f"{'REGION':<15} | {'DISPLAY NAME':<18} | {'PROVIDER / SYMBOL':<25} | {'LATEST':<10} | {'PREVIOUS':<10} | {'CHANGE %':<10} | {'DATE':<10} | {'STALE'}")
    print("-" * 110)
    for e in equities:
        chg_pct = f"{e.change_percent:+.2f}%"
        prov = f"{e.source} ({e.symbol})"
        print(f"{e.region:<15} | {e.display_name:<18} | {prov:<25} | {e.latest_close:<10.2f} | {e.previous_close:<10.2f} | {chg_pct:<10} | {e.market_date:<10} | {e.is_stale}")

    print("\n" + "=" * 110)
    print("2. COMMODITY / METALS / REMX / FX VERIFICATION")
    print("=" * 110)
    print(f"{'CANONICAL ID':<22} | {'DISPLAY NAME':<18} | {'ASSET CLASS':<15} | {'LATEST':<10} | {'PREVIOUS':<10} | {'CHANGE %':<10} | {'UNIT'}")
    print("-" * 110)
    for ca in cross_assets:
        chg_pct = f"{ca.change_percent:+.2f}%"
        print(f"{ca.canonical_id:<22} | {ca.display_name:<18} | {ca.asset_class:<15} | {ca.latest_close:<10.2f} | {ca.previous_close:<10.2f} | {chg_pct:<10} | {ca.unit}")

    print("\n" + "=" * 110)
    print("3. SOVEREIGN YIELDS VERIFICATION")
    print("=" * 110)
    print(f"{'INSTRUMENT':<20} | {'PROVIDER':<25} | {'OBSERVATION DATE':<16} | {'LATEST':<8} | {'PREVIOUS':<8} | {'CHANGE BP':<10} | {'STALE?'}")
    print("-" * 110)
    for y in yields:
        chg_bp = f"{y.change_basis_points:+.1f} bp"
        latest = f"{y.yield_percent:.2f}%" if y.yield_percent is not None else "N/A"
        prev = f"{y.previous_yield_percent:.2f}%" if y.previous_yield_percent is not None else "N/A"
        print(f"{y.display_name:<20} | {y.source:<25} | {y.market_date:<16} | {latest:<8} | {prev:<8} | {chg_bp:<10} | {y.is_stale}")

    print("\n" + "=" * 120)
    print("4. CENTRAL BANK MONETARY POLICY VERIFICATION")
    print("=" * 120)
    print(f"{'CENTRAL BANK':<22} | {'POLICY INSTRUMENT':<35} | {'CURRENT RATE/RANGE':<18} | {'ACTION':<8} | {'CHANGE BP':<10} | {'EFFECTIVE DATE':<14} | {'DECISION DATE'}")
    print("-" * 120)
    for p in policies:
        if p.lower_bound is not None and p.upper_bound is not None:
            rate_str = f"{p.lower_bound:.2f}–{p.upper_bound:.2f}%"
        elif p.rate is not None:
            rate_str = f"{p.rate:.2f}%"
        else:
            rate_str = "N/A"
        
        chg_bp = f"{p.change_basis_points:+.1f} bp"
        dec_date = p.decision_date or "N/A"
        print(f"{p.central_bank:<22} | {p.policy_rate_name:<35} | {rate_str:<18} | {p.action:<8} | {chg_bp:<10} | {p.effective_date:<14} | {dec_date}")

if __name__ == "__main__":
    asyncio.run(audit_all_markets())
