import sys
from datetime import date, timedelta
from app.db import SessionLocal
from app.models import DailyEdition, EditionEvent
from services.editorial.selection import generate_daily_edition_selection, save_daily_edition_selection
from services.editorial.synthesis import synthesize_event_editorial, synthesize_edition_brief_and_themes, save_editorial_synthesis

def seed_synthesis():
    db = SessionLocal()
    
    dates = [date(2026, 9, 15) - timedelta(days=i) for i in range(20)]
    print(f"Generating and synthesizing editions across {len(dates)} dates...")
    
    total_events = 0
    for dt in dates:
        audit_res = generate_daily_edition_selection(db, target_date=dt)
        if not audit_res.selected_events:
            continue
            
        edition = save_daily_edition_selection(db, audit_res, target_date=dt, status="GENERATED")
        
        # Synthesize prose for each selected event using fallback mode (fast & 100% deterministic)
        prose_results = []
        for ev in audit_res.selected_events:
            p_res = synthesize_event_editorial(db, ev, edition_date=dt, use_ollama=False)
            prose_results.append(p_res)
            total_events += 1
            
        brief_res = synthesize_edition_brief_and_themes(db, audit_res, prose_results, use_ollama=False)
        save_editorial_synthesis(db, edition, prose_results, brief_res)
        print(f"  Date {dt}: Synthesized {len(prose_results)} events. Total cumulative = {total_events}")

if __name__ == "__main__":
    seed_synthesis()
