import sys
from app.db import SessionLocal
from app.models import Article, EventCluster, EditionEvent, ArticleAIOutput

def trace_ayana_bio():
    db = SessionLocal()
    articles = db.query(Article).filter(Article.title.ilike("%Ayana Bio%")).all()
    print(f"Found {len(articles)} Ayana Bio articles:")
    for a in articles:
        print(f"ID: {a.id}")
        print(f"Title: {a.title}")
        print(f"Source ID: {a.source_id}")
        print(f"Raw Summary: {a.raw_summary}")
        
        # Check AI output
        ai_out = db.query(ArticleAIOutput).filter(ArticleAIOutput.article_id == a.id).first()
        if ai_out:
            print(f"AI Primary Category: {ai_out.primary_category}")
            print(f"AI Importance: {ai_out.importance_score}")
            print(f"AI Output JSON: {ai_out.output_json}")
            print(f"AI Summary: {ai_out.summary}")
        else:
            print("AI Output: None")
            
        # Check EventCluster
        clusters = db.query(EventCluster).filter(EventCluster.primary_article_id == a.id).all()
        for c in clusters:
            print(f"Cluster ID: {c.cluster_id}, Category: {c.category}")
            # Check EditionEvent
            ee_list = db.query(EditionEvent).filter(EditionEvent.event_cluster_id == c.cluster_id).all()
            for ee in ee_list:
                print(f"  EditionEvent ID: {ee.id}, Section: {ee.section}, SelectionReason: {ee.selection_reason_json}")

if __name__ == "__main__":
    trace_ayana_bio()
