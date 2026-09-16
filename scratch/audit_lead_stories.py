import sys
from datetime import date, timedelta
from app.db import SessionLocal
from app.models import DailyEdition, EditionEvent, EventCluster, Article, ArticleAIOutput
from services.editorial.selection import generate_daily_edition_selection, get_london_date_window, calculate_lead_significance_score

def clean_text(s: str) -> str:
    if not s:
        return ""
    return s.encode("ascii", "ignore").decode("ascii")

def audit_leads():
    db = SessionLocal()
    
    base_date = date(2026, 9, 15)
    dates = [base_date - timedelta(days=i) for i in range(22)]
    
    records = []
    strong = 0
    reasonable = 0
    questionable = 0
    
    for dt in dates:
        audit_res = generate_daily_edition_selection(db, target_date=dt)
        if not audit_res.selected_events:
            continue
            
        lead = next((e for e in audit_res.selected_events if e.role == "LEAD"), audit_res.selected_events[0])
        runner_up = next((e for e in audit_res.selected_events if e != lead), None)
        
        sig_score = calculate_lead_significance_score(lead.raw_cluster_result, lead.section) if lead.raw_cluster_result else lead.event_score
        
        # Classification
        if lead.distinct_source_count >= 2 or lead.section in ("ECONOMY", "WORLD", "ENERGY", "TRADE"):
            eval_class = "STRONG"
            strong += 1
        elif sig_score >= 75:
            eval_class = "REASONABLE"
            reasonable += 1
        else:
            eval_class = "QUESTIONABLE"
            questionable += 1
            
        records.append({
            "date": str(dt),
            "lead": clean_text(lead.canonical_title),
            "section": lead.section,
            "event_score": lead.event_score,
            "lead_sig_score": sig_score,
            "source": clean_text(lead.primary_article.source.name) if lead.primary_article and lead.primary_article.source else "Unknown",
            "source_type": lead.primary_article.source.source_type if lead.primary_article and lead.primary_article.source else "Unknown",
            "distinct_sources": lead.distinct_source_count,
            "runner_up": clean_text(runner_up.canonical_title) if runner_up else "None",
            "eval": eval_class,
        })
        
    print(f"Audited {len(records)} edition leads:")
    print(f"STRONG: {strong} | REASONABLE: {reasonable} | QUESTIONABLE: {questionable}\n")
    for r in records[:20]:
        print(f"Date {r['date']} | Sec: {r['section']} | Eval: {r['eval']}")
        print(f"  Lead: {r['lead'][:75]} [{r['source']} ({r['source_type']})]")
        print(f"  Scores: Event={r['event_score']:.1f}, LeadSig={r['lead_sig_score']:.1f} | Sources={r['distinct_sources']}")
        print(f"  Runner-up: {r['runner_up'][:75]}\n")

if __name__ == "__main__":
    audit_leads()
