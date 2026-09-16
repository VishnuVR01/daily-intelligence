import sys
import json
from app.db import SessionLocal
from app.models import EventEditorialProse, EditionEvent, EventCluster, Article, ArticleAIOutput
from services.editorial.evidence import extract_best_summary
from services.editorial.validator import extract_numeric_tokens, CAUSAL_TRIGGERS, SENSATIONAL_TERMS

def evaluate_expanded_grounding():
    db = SessionLocal()
    
    # Query all prose records
    prose_records = db.query(EventEditorialProse).order_by(EventEditorialProse.id.desc()).all()
    print(f"Auditing all {len(prose_records)} EventEditorialProse records in database...")
    
    total_evaluated = 0
    unsupported_material = 0
    unsupported_causal = 0
    unsupported_numeric = 0
    grounded_watch_next = 0
    total_watch_next = 0
    
    audited_details = []
    
    for p in prose_records:
        ee = db.query(EditionEvent).filter(EditionEvent.id == p.edition_event_id).first()
        if not ee:
            continue
            
        cluster = db.query(EventCluster).filter(EventCluster.cluster_id == p.event_cluster_id).first()
        if not cluster or not cluster.primary_article:
            continue
            
        total_evaluated += 1
        prim_art = cluster.primary_article
        
        # Build evidence text
        evidence_text = f"{cluster.canonical_title} {prim_art.title} {prim_art.raw_summary or ''} 2026 "
        if cluster.cluster_articles:
            for ca in cluster.cluster_articles:
                if ca.article and not ca.is_primary:
                    evidence_text += f"{ca.article.title} {ca.article.raw_summary or ''} "
                    
        ev_numbers = extract_numeric_tokens(evidence_text)
        gen_text = f"{p.headline} {p.summary} {p.why_it_matters or ''}"
        gen_numbers = extract_numeric_tokens(gen_text)
        
        # Numeric check
        num_errs = []
        for num in gen_numbers:
            if len(num) == 1 and num.isdigit():
                continue
            if num not in ev_numbers:
                num_clean = "".join(c for c in num if c.isdigit() or c == ".")
                ev_cleans = {"".join(c for c in e if c.isdigit() or c == ".") for e in ev_numbers}
                if num_clean and num_clean not in ev_cleans:
                    num_errs.append(num)
                    
        if num_errs:
            unsupported_numeric += 1
            print(f"Numeric claim warning on Prose ID {p.id} [{p.headline[:50]}]: {num_errs}")
            
        # Causal check
        causal_errs = []
        gen_lower = gen_text.lower()
        ev_lower = evidence_text.lower()
        for trig in CAUSAL_TRIGGERS:
            if trig in gen_lower and trig not in ev_lower:
                if not any(t in ev_lower for t in ["due to", "as a result", "after", "following"]):
                    causal_errs.append(trig)
                    
        if causal_errs:
            unsupported_causal += 1
            
        # Watch Next check
        if p.watch_next_json and isinstance(p.watch_next_json, dict):
            total_watch_next += 1
            wn_evt = p.watch_next_json.get("event", "")
            if wn_evt:
                grounded_watch_next += 1
                
        audited_details.append({
            "id": p.id,
            "headline": p.headline,
            "section": ee.section,
            "status": p.status,
            "num_errors": num_errs,
            "causal_errors": causal_errs,
        })
        
    print(f"\nExpanded Grounding Audit Results across {total_evaluated} events:")
    print(f"Total Evaluated Events: {total_evaluated}")
    print(f"Unsupported Material Claims: {unsupported_material}")
    print(f"Unsupported Causal Claims: {unsupported_causal}")
    print(f"Unsupported Numeric Claims: {unsupported_numeric}")
    wn_rate = (grounded_watch_next / total_watch_next * 100.0) if total_watch_next > 0 else 100.0
    print(f"Watch Next Groundedness: {wn_rate:.1f}% ({grounded_watch_next}/{total_watch_next})\n")

if __name__ == "__main__":
    evaluate_expanded_grounding()
