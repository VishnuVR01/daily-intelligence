"""
Read-only feasibility audit for Stage 4D Signal Detection Engine.
Profiles canonical PostgreSQL EventClusters, date windows, entity links, source diversity, and coverage.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal
from app.models import Article, ArticleAIOutput, Entity, EventCluster, EventClusterArticle, EventEntity


def main():
    db = SessionLocal()
    try:
        total_articles = db.query(Article).count()
        total_ai_outputs = db.query(ArticleAIOutput).count()
        relevant_ai_outputs = db.query(ArticleAIOutput).filter(ArticleAIOutput.is_relevant == True).count()
        
        clusters = db.query(EventCluster).all()
        total_clusters = len(clusters)

        event_entities = db.query(EventEntity).all()
        total_event_entities = len(event_entities)

        # Clustered article count
        clustered_articles_count = db.query(EventClusterArticle.article_id).distinct().count()

        print(f"--- DATASET PROFILE ---")
        print(f"Total Articles: {total_articles}")
        print(f"Total AI Outputs: {total_ai_outputs}")
        print(f"Relevant AI Outputs: {relevant_ai_outputs}")
        print(f"Clustered Relevant Articles: {clustered_articles_count}")
        print(f"Event Coverage %: {(clustered_articles_count / relevant_ai_outputs * 100):.2f}%" if relevant_ai_outputs else "0%")
        print(f"Total EventClusters: {total_clusters}")
        print(f"Total EventEntity Links: {total_event_entities}")

        if not clusters:
            print("No EventClusters found.")
            return

        # Dates analysis
        cluster_dates = []
        for c in clusters:
            dt = c.earliest_article_at or c.created_at
            if dt:
                cluster_dates.append(dt)

        if cluster_dates:
            min_date = min(cluster_dates)
            max_date = max(cluster_dates)
            days_span = max(1, (max_date - min_date).days + 1)
            print(f"\n--- TEMPORAL DISTRIBUTION ---")
            print(f"Earliest Event Date: {min_date.isoformat()}")
            print(f"Latest Event Date: {max_date.isoformat()}")
            print(f"Time Span: {days_span} days")
            print(f"Average Event Density: {(total_clusters / days_span):.2f} events/day")

        # Categories analysis
        categories = Counter([c.category for c in clusters])
        print(f"\n--- EVENT CATEGORIES ---")
        for cat, cnt in categories.most_common():
            print(f"  {cat}: {cnt} events")

        # Sources per cluster
        sources_counts = [c.distinct_source_count for c in clusters]
        avg_sources = sum(sources_counts) / max(1, len(sources_counts))
        print(f"\n--- SOURCE DIVERSITY ---")
        print(f"Average Distinct Sources per Event: {avg_sources:.2f}")

        # Linked entities analysis
        entity_roles = Counter([ee.role for ee in event_entities])
        print(f"\n--- ENTITY ROLES IN EVENTS ---")
        for role, cnt in entity_roles.most_common():
            print(f"  {role}: {cnt} links")

        entity_ids_in_events = Counter([ee.entity_id for ee in event_entities])
        print(f"\n--- TOP ENTITIES BY EVENT FREQUENCY ---")
        top_eids = entity_ids_in_events.most_common(10)
        for eid, cnt in top_eids:
            ent = db.query(Entity).filter(Entity.id == eid).first()
            name = ent.canonical_name if ent else f"Entity #{eid}"
            etype = ent.entity_type if ent else "UNKNOWN"
            print(f"  {name} ({etype}): {cnt} events")

    finally:
        db.close()


if __name__ == "__main__":
    main()
