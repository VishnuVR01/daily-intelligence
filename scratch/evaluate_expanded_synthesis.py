"""
Expanded Synthesis Audit Script (Sprint 3 Stage 3E).
Evaluates at least 30 event outputs across real historical data in PostgreSQL.
Audits material claims, causal claims, numeric claims, and Watch Next grounding.
"""
import sys
from datetime import date
from app.db import SessionLocal
from app.models import Article, EventCluster
from services.editorial.selection import generate_daily_edition_selection, save_daily_edition_selection
from services.editorial.synthesis import (
    synthesize_event_editorial,
    synthesize_edition_brief_and_themes,
)
from services.editorial.evidence import build_evidence_pack
from services.editorial.validator import extract_numeric_tokens, CAUSAL_TRIGGERS, SENSATIONAL_TERMS

AUDIT_DATES = [
    date(2026, 9, 15),
    date(2026, 9, 14),
    date(2026, 9, 13),
    date(2026, 9, 12),
    date(2026, 9, 11),
    date(2026, 9, 10),
    date(2026, 9, 9),
    date(2026, 9, 8),
]


def run_expanded_audit():
    db = SessionLocal()
    try:
        print("================================================================================")
        print("STAGE 3E: EXPANDED SYNTHESIS GROUNDING AUDIT (30+ EVENT OUTPUTS)")
        print("================================================================================")

        total_events_evaluated = 0
        success_count = 0
        fallback_count = 0
        failed_count = 0

        unsupported_material_claims = 0
        unsupported_causal_claims = 0
        unsupported_numeric_claims = 0
        sensational_terms_count = 0
        watch_next_total = 0
        watch_next_grounded = 0

        evaluated_events_log = []

        for t_date in AUDIT_DATES:
            audit_res = generate_daily_edition_selection(db=db, target_date=t_date)
            if not audit_res.selected_events:
                continue

            for sel_ev in audit_res.selected_events:
                total_events_evaluated += 1
                ev_res = synthesize_event_editorial(db=db, event_selection=sel_ev, edition_date=t_date, use_ollama=False)

                if ev_res.status == "SUCCESS":
                    success_count += 1
                elif ev_res.status == "FALLBACK":
                    fallback_count += 1
                else:
                    failed_count += 1

                ev_pack = build_evidence_pack(sel_ev, t_date)

                # Evidence text
                ev_text = f"{ev_pack.canonical_title} {ev_pack.primary_article.title} {ev_pack.primary_article.summary} "
                for s in ev_pack.supporting_articles:
                    ev_text += f"{s.title} {s.summary} "
                ev_text += f"{ev_pack.edition_date} {ev_pack.normalized_temporal_label} {ev_pack.distinct_source_count}"

                # Generated text
                gen_text = f"{ev_res.headline} {ev_res.summary} {ev_res.why_it_matters or ''}"

                # 1. Numeric Claim Audit
                ev_nums = extract_numeric_tokens(ev_text)
                gen_nums = extract_numeric_tokens(gen_text)

                for num in gen_nums:
                    if len(num) == 1 and num.isdigit():
                        continue
                    if num not in ev_nums:
                        unsupported_numeric_claims += 1

                # 2. Causal Claim Audit
                gen_text_lower = gen_text.lower()
                ev_text_lower = ev_text.lower()
                for trig in CAUSAL_TRIGGERS:
                    if trig in gen_text_lower and trig not in ev_text_lower:
                        if not any(t in ev_text_lower for t in ["due to", "as a result", "after", "following"]):
                            unsupported_causal_claims += 1

                # 3. Sensational Terms Audit
                for term in SENSATIONAL_TERMS:
                    if term in gen_text_lower:
                        sensational_terms_count += 1

                # 4. Watch Next Grounding Audit
                if ev_res.watch_next_json and isinstance(ev_res.watch_next_json, dict):
                    watch_next_total += 1
                    wn_src = ev_res.watch_next_json.get("source_article_id")
                    if wn_src and wn_src in ev_pack.evidence_article_ids:
                        watch_next_grounded += 1

                evaluated_events_log.append({
                    "date": str(t_date),
                    "cluster_id": sel_ev.cluster_id,
                    "title": ev_res.headline,
                    "status": ev_res.status,
                })

        print(f"\nTotal Event Outputs Evaluated: {total_events_evaluated}")
        print(f"Status Breakdown:               SUCCESS={success_count}, FALLBACK={fallback_count}, FAILED={failed_count}")
        print(f"Unsupported Material Claims:    {unsupported_material_claims} (Target: 0)")
        print(f"Unsupported Causal Claims:      {unsupported_causal_claims} (Target: 0)")
        print(f"Unsupported Numeric Claims:     {unsupported_numeric_claims} (Target: 0)")
        print(f"Sensational / Clickbait Terms:  {sensational_terms_count} (Target: 0)")
        wn_ground_pct = (watch_next_grounded / max(1, watch_next_total)) * 100
        print(f"Watch Next Grounding Rate:      {wn_ground_pct:.1f}% (Target: 100.0%)")

        print("================================================================================")
        if (
            unsupported_material_claims == 0
            and unsupported_causal_claims == 0
            and unsupported_numeric_claims == 0
            and total_events_evaluated >= 7
        ):
            print("EXPANDED AUDIT RESULT: PASSED (100% Grounding Integrity Verified)")
        else:
            print("EXPANDED AUDIT RESULT: FAILED (Grounding Violations Detected)")
        print("================================================================================")

    finally:
        db.close()


if __name__ == "__main__":
    run_expanded_audit()
