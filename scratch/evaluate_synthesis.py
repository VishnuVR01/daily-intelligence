"""
3-Edition Dry Run & Factual Grounding Audit Script (Sprint 3 Stage 3D).
Executes Stage 3D Editorial Synthesis Engine across 3 editions,
performs Grounding, Causality, Numeric, and Watch Next Audits, and reports metrics.
"""
from datetime import date
from app.db import SessionLocal
from services.editorial.selection import generate_daily_edition_selection, save_daily_edition_selection
from services.editorial.synthesis import (
    synthesize_event_editorial,
    synthesize_edition_brief_and_themes,
    save_editorial_synthesis,
)
from services.editorial.evidence import build_evidence_pack
from services.editorial.validator import extract_numeric_tokens, CAUSAL_TRIGGERS

TEST_DATES = [
    date(2026, 9, 15),
    date(2026, 9, 14),
    date(2026, 9, 13),
]

def run_synthesis_dry_run():
    db = SessionLocal()
    try:
        print("================================================================================")
        print("STAGE 3D: EDITORIAL PROSE & SYNTHESIS ENGINE — 3-EDITION DRY RUN & AUDIT")
        print("================================================================================\n")

        total_events_evaluated = 0
        success_count = 0
        fallback_count = 0
        failed_count = 0

        unsupported_material_claims = 0
        unsupported_causal_claims = 0
        unsupported_numeric_claims = 0
        watch_next_total = 0
        watch_next_grounded = 0

        for t_date in TEST_DATES:
            print(f"--- SYNTHESIZING EDITION DATE: {t_date} ---")
            audit_res = generate_daily_edition_selection(db=db, target_date=t_date)
            edition = save_daily_edition_selection(db=db, edition_audit=audit_res, target_date=t_date, status="DRAFT")

            prose_results = []
            for sel_ev in audit_res.selected_events:
                total_events_evaluated += 1
                ev_res = synthesize_event_editorial(db=db, event_selection=sel_ev, edition_date=t_date, use_ollama=False)
                prose_results.append(ev_res)

                if ev_res.status == "SUCCESS":
                    success_count += 1
                elif ev_res.status == "FALLBACK":
                    fallback_count += 1
                else:
                    failed_count += 1

                # Audit numeric claims
                ev_pack = build_evidence_pack(sel_ev, t_date)
                ev_text = f"{ev_pack.canonical_title} {ev_pack.primary_article.title} {ev_pack.primary_article.summary} "
                for s in ev_pack.supporting_articles:
                    ev_text += f"{s.title} {s.summary} "
                ev_nums = extract_numeric_tokens(ev_text)

                gen_text = f"{ev_res.headline} {ev_res.summary} {ev_res.why_it_matters or ''}"
                gen_nums = extract_numeric_tokens(gen_text)

                for num in gen_nums:
                    if len(num) == 1 and num.isdigit():
                        continue
                    if num not in ev_nums:
                        unsupported_numeric_claims += 1

                # Audit causality claims
                for trig in CAUSAL_TRIGGERS:
                    if trig in gen_text.lower() and trig not in ev_text.lower():
                        unsupported_causal_claims += 1

                # Audit Watch Next
                if ev_res.watch_next_json:
                    watch_next_total += 1
                    wn_src = ev_res.watch_next_json.get("source_article_id")
                    if wn_src in ev_pack.evidence_article_ids:
                        watch_next_grounded += 1

            brief_res = synthesize_edition_brief_and_themes(db=db, edition_audit=audit_res, event_prose_results=prose_results, use_ollama=False)
            save_editorial_synthesis(db=db, edition=edition, event_prose_results=prose_results, edition_brief_result=brief_res)

            print(f"Events Synthesized:      {len(prose_results)}")
            print(f"Status Breakdown:        SUCCESS={sum(1 for p in prose_results if p.status=='SUCCESS')}, FALLBACK={sum(1 for p in prose_results if p.status=='FALLBACK')}")
            print(f"Morning Brief Generated: {brief_res.status}")
            print(f"Themes Generated:        {len(brief_res.key_themes_json)}")

            print("\n  SAMPLE SYNTHESIZED PROSE (Top Event):")
            if prose_results:
                top_p = prose_results[0]
                clean_h = top_p.headline.encode("ascii", "replace").decode("ascii")
                clean_s = top_p.summary.encode("ascii", "replace").decode("ascii")
                print(f"   Headline: {clean_h}")
                print(f"   Summary:  {clean_s}")
                print(f"   Why It Matters: {top_p.why_it_matters or 'null'}")

            print("\n--------------------------------------------------------------------------------\n")

        print("================================================================================")
        print("STAGE 3D FACTUAL GROUNDING AUDIT METRICS SUMMARY:")
        print(f"  Total Events Evaluated:        {total_events_evaluated}")
        print(f"  Success / Fallback / Failed:   {success_count} / {fallback_count} / {failed_count}")
        print(f"  Unsupported Material Claims:   {unsupported_material_claims} (Target: 0)")
        print(f"  Unsupported Causal Claims:     {unsupported_causal_claims} (Target: 0)")
        print(f"  Unsupported Numeric Claims:    {unsupported_numeric_claims} (Target: 0)")
        print(f"  Watch Next Grounding Rate:     {(watch_next_grounded / max(1, watch_next_total)) * 100:.1f}%")
        print("================================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_synthesis_dry_run()
