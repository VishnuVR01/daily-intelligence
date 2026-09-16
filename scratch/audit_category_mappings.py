import sys
from app.db import SessionLocal
from app.models import Article, ArticleAIOutput, EventCluster, EditionEvent
from services.editorial.selection import map_category_to_section, CATEGORY_TO_SECTION

def audit_category_mappings():
    db = SessionLocal()
    
    # Query 120 AI outputs
    ai_outputs = db.query(ArticleAIOutput).filter(ArticleAIOutput.status == "success", ArticleAIOutput.is_relevant == True).order_by(ArticleAIOutput.id.desc()).limit(120).all()
    
    print(f"Auditing {len(ai_outputs)} AI-reviewed articles...")
    
    correct = 0
    reasonable = 0
    questionable = 0
    incorrect = 0
    
    anomalies = []
    
    for ai in ai_outputs:
        art = db.query(Article).filter(Article.id == ai.article_id).first()
        if not art:
            continue
            
        ai_cat = ai.primary_category or ""
        source_cat = art.source.category if art.source else ""
        
        # Determine current effective category and section
        eff_cat = ai_cat or source_cat
        section = map_category_to_section(eff_cat)
        
        # Simple heuristic classification for audit
        title_lower = art.title.lower()
        
        # Check for obvious mismatches
        is_inc = False
        reason = ""
        
        if "energy" not in title_lower and "oil" not in title_lower and "gas" not in title_lower and "power" not in title_lower and section == "ENERGY" and "commodities" in eff_cat.lower():
            is_inc = True
            reason = f"Non-energy commodity (e.g. food/ag/metals) mapped to ENERGY because eff_cat='{eff_cat}'"
        elif ("ai" in title_lower or "software" in title_lower or "tech" in title_lower) and section == "WORLD":
            reason = f"Tech story in WORLD due to category='{eff_cat}'"
            questionable += 1
        elif ("fed" in title_lower or "ecb" in title_lower or "inflation" in title_lower or "rate" in title_lower) and section not in ("ECONOMY", "WORLD"):
            is_inc = True
            reason = f"Macro/Policy story mapped to {section} instead of ECONOMY"
        elif is_inc:
            incorrect += 1
            anomalies.append((art.id, art.title, ai_cat, source_cat, section, reason))
        else:
            correct += 1

        if is_inc:
            incorrect += 1
            anomalies.append((art.id, art.title, ai_cat, source_cat, section, reason))

    print(f"\nAudit Results across {len(ai_outputs)} samples:")
    print(f"CORRECT: {correct}")
    print(f"REASONABLE: {reasonable}")
    print(f"QUESTIONABLE: {questionable}")
    print(f"INCORRECT: {incorrect}")
    
    if anomalies:
        print("\nSample Anomalies:")
        for a in anomalies[:10]:
            print(f"ID {a[0]} | Title: {a[1][:70]} | AI Cat: {a[2]} | Source Cat: {a[3]} -> Section: {a[4]} | Reason: {a[5]}")

if __name__ == "__main__":
    audit_category_mappings()
