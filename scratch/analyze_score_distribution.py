"""
Script to analyze the Event Score distribution across the candidate dataset.
Reports P25, median, P75, P90 using standard python statistics.
"""
from app.db import SessionLocal
from services.editorial.selection import fetch_eligible_candidates, get_london_date_window
from services.editorial.clustering import cluster_articles
from datetime import date

def percentile(N, percent):
    if not N:
        return 0.0
    N = sorted(N)
    k = (len(N) - 1) * percent
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(N[int(k)])
    d0 = N[int(f)] * (c - k)
    d1 = N[int(c)] * (k - f)
    return float(d0 + d1)

import math

def analyze_distribution():
    db = SessionLocal()
    try:
        start_utc, end_utc = get_london_date_window(date(2026, 9, 15))
        # Extend window to 30 days to get full candidate score distribution
        start_utc_30d = end_utc - (end_utc - start_utc) * 15

        eligible_arts, ai_map = fetch_eligible_candidates(db, start_utc_30d, end_utc)
        clusters = cluster_articles(eligible_arts, ai_outputs_map=ai_map)
        scores = [c.cluster_score for c in clusters]

        if not scores:
            print("No candidate scores found.")
            return

        p25 = percentile(scores, 0.25)
        median = percentile(scores, 0.50)
        p75 = percentile(scores, 0.75)
        p90 = percentile(scores, 0.90)

        print(f"Candidate Events Total: {len(scores)}")
        print(f"P25:    {p25:.1f}")
        print(f"Median: {median:.1f}")
        print(f"P75:    {p75:.1f}")
        print(f"P90:    {p90:.1f}")
        print(f"Min:    {min(scores):.1f}")
        print(f"Max:    {max(scores):.1f}")

    finally:
        db.close()

if __name__ == "__main__":
    analyze_distribution()
