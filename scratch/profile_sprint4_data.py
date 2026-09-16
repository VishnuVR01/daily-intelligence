import sys
import json
from collections import Counter
from app.db import SessionLocal
from app.models import Article, ArticleAIOutput, EventCluster, DailyEdition, Source

def profile_data():
    db = SessionLocal()
    
    art_count = db.query(Article).count()
    ai_count = db.query(ArticleAIOutput).count()
    rel_count = db.query(ArticleAIOutput).filter(ArticleAIOutput.is_relevant == True, ArticleAIOutput.status == "success").count()
    cluster_count = db.query(EventCluster).count()
    edition_count = db.query(DailyEdition).count()
    source_count = db.query(Source).count()
    
    print("=== CANONICAL DATASET PROFILE ===")
    print(f"Total Articles: {art_count}")
    print(f"Total AI Outputs: {ai_count}")
    print(f"Relevant AI Outputs: {rel_count}")
    print(f"Event Clusters: {cluster_count}")
    print(f"Daily Editions: {edition_count}")
    print(f"Active Sources: {source_count}\n")
    
    # Audit 200 relevant AI outputs
    rel_outputs = db.query(ArticleAIOutput).filter(ArticleAIOutput.is_relevant == True, ArticleAIOutput.status == "success").order_by(ArticleAIOutput.id.desc()).limit(200).all()
    
    entities_extracted = []
    topics_extracted = []
    categories_extracted = []
    countries_extracted = []
    
    entity_types_counter = Counter()
    entity_names_counter = Counter()
    
    for ai in rel_outputs:
        if ai.primary_category:
            categories_extracted.append(ai.primary_category)
        if isinstance(ai.output_json, dict):
            ents = ai.output_json.get("entities", [])
            for e in ents:
                if isinstance(e, dict):
                    name = e.get("name", "").strip()
                    etype = e.get("type", "UNKNOWN").strip()
                elif isinstance(e, str):
                    name = e.strip()
                    etype = "UNKNOWN"
                else:
                    continue
                if name:
                    entity_names_counter[name] += 1
                    entity_types_counter[etype] += 1
                    entities_extracted.append((name, etype))
                    
            top = ai.output_json.get("topics", [])
            if isinstance(top, list):
                topics_extracted.extend(top)
            cnts = ai.output_json.get("countries", [])
            if isinstance(cnts, list):
                countries_extracted.extend(cnts)

    print("=== ENTITY EXTRACTION AUDIT (200 Relevant Samples) ===")
    print(f"Total Raw Entity Mentions in JSON: {len(entities_extracted)}")
    print(f"Unique Entity Names (Raw): {len(entity_names_counter)}")
    print(f"Entity Types Breakdown: {dict(entity_types_counter)}")
    print(f"\nTop 20 Extracted Entities (Raw Surface Forms):")
    for name, cnt in entity_names_counter.most_common(20):
        print(f"  - {name}: {cnt}")
        
    # Check specific alias variations in corpus
    alias_tests = ["Federal Reserve", "Fed", "European Central Bank", "ECB", "United States", "US", "U.S.", "United Kingdom", "UK", "Britain", "OpenAI", "Microsoft", "NVIDIA", "Nvidia", "Brent", "Brent crude"]
    print("\nAlias Occurrence Counts in Raw Extracted Entities:")
    for alias in alias_tests:
        print(f"  '{alias}': {entity_names_counter.get(alias, 0)}")

if __name__ == "__main__":
    profile_data()
