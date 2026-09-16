"""
Read-only audit script for Stage 4D.1 Event Coverage Expansion.
Profiles eligible relevant articles, current cluster representation, date distribution, and coverage funnel.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal
from app.models import Article, ArticleAIOutput, Entity, EntityMention, EventCluster, EventClusterArticle, EventEntity


def main():
    db = SessionLocal()
    try:
        now_dt = datetime.now(timezone.utc)
        d7 = now_dt - timedelta(days=7)
        d14 = now_dt - timedelta(days=14)
        d30 = now_dt - timedelta(days=30)

        total_articles = db.query(Article).count()
        total_ai_outputs = db.query(ArticleAIOutput).count()

        eligible_ai_outputs = (
            db.query(ArticleAIOutput, Article)
            .join(Article, ArticleAIOutput.article_id == Article.id)
            .filter(
                ArticleAIOutput.status == "success",
                ArticleAIOutput.is_relevant == True,
                Article.title.isnot(None),
                Article.canonical_url.isnot(None),
            )
            .all()
        )

        eligible_count = len(eligible_ai_outputs)
        eligible_article_ids = {a.id for _, a in eligible_ai_outputs}

        # Clustered article IDs
        clustered_article_ids = {
            ca.article_id for ca in db.query(EventClusterArticle.article_id).all()
        }

        covered_eligible_ids = eligible_article_ids.intersection(clustered_article_ids)
        uncovered_eligible_ids = eligible_article_ids - clustered_article_ids

        total_clusters = db.query(EventCluster).count()
        clusters_with_entities = db.query(EventEntity.event_cluster_id).distinct().count()

        print(f"--- 1. OVERALL COVERAGE FUNNEL ---")
        print(f"Total Articles: {total_articles}")
        print(f"Total AI Outputs: {total_ai_outputs}")
        print(f"Eligible Relevant Articles: {eligible_count}")
        print(f"Clustered Eligible Articles: {len(covered_eligible_ids)}")
        print(f"Uncovered Eligible Articles: {len(uncovered_eligible_ids)}")
        print(f"Article Event Coverage: {(len(covered_eligible_ids) / max(1, eligible_count) * 100):.2f}%")
        print(f"Total EventClusters: {total_clusters}")
        print(f"Clusters with Participant Entities: {clusters_with_entities} ({(clusters_with_entities / max(1, total_clusters) * 100):.2f}%)")

        # Recency breakdown (7D, 14D, 30D)
        print(f"\n--- 2. RECENCY COVERAGE BREAKDOWN ---")
        for period_name, start_date in [("Last 7 Days (7D)", d7), ("Last 14 Days (14D)", d14), ("Last 30 Days (30D)", d30)]:
            period_eligible = [
                a for _, a in eligible_ai_outputs
                if (a.published_at or a.collected_at or now_dt) >= start_date
            ]
            period_eligible_ids = {a.id for a in period_eligible}
            period_covered = period_eligible_ids.intersection(clustered_article_ids)
            cov_pct = (len(period_covered) / max(1, len(period_eligible_ids))) * 100
            print(f"  {period_name}: {len(period_covered)} / {len(period_eligible_ids)} articles ({cov_pct:.2f}%)")

        # Entity Extraction Coverage for Clustered Articles
        clustered_articles_with_entities = db.query(EntityMention.article_id).filter(EntityMention.article_id.in_(list(covered_eligible_ids))).distinct().count()
        print(f"\n--- 3. KNOWLEDGE ENTITY COVERAGE ---")
        print(f"Clustered Articles with EntityMentions: {clustered_articles_with_entities} / {len(covered_eligible_ids)} ({(clustered_articles_with_entities / max(1, len(covered_eligible_ids)) * 100):.2f}%)")

    finally:
        db.close()


if __name__ == "__main__":
    main()
