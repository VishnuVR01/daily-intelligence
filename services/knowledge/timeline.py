"""
Stage 4C Grounded Entity Timeline Service.
Provides deterministic, queryable timeline records for canonical entities over ordered EventClusters.
Zero LLM calls, zero duplicate events, Europe/London date boundary filtering.
"""
import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models import Article, EditionEvent, Entity, EventCluster, EventEntity

logger = logging.getLogger("entity_timeline")


def get_grounded_event_timestamp(cluster: EventCluster, primary_article: Optional[Article]) -> datetime:
    """
    Determines the grounded event timestamp using strict fallback hierarchy:
    1. EventCluster.earliest_article_at
    2. Primary Article published_at
    3. Primary Article collected_at
    4. EventCluster.created_at
    """
    if cluster.earliest_article_at:
        return cluster.earliest_article_at
    if primary_article and primary_article.published_at:
        return primary_article.published_at
    if primary_article and primary_article.collected_at:
        return primary_article.collected_at
    return cluster.created_at or datetime.now(timezone.utc)


def get_entity_timeline(
    db: Session,
    entity_id: int,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Retrieves ordered, grounded timeline events for a canonical entity.
    Deduplicates cross-midnight clusters (1 cluster = 1 timeline entry).
    """
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        return {
            "entity": None,
            "total_events": 0,
            "events": [],
            "error": f"Entity with id={entity_id} not found.",
        }

    # Query EventEntity links for this entity
    links = (
        db.query(EventEntity, EventCluster, Article)
        .join(EventCluster, EventEntity.event_cluster_id == EventCluster.cluster_id)
        .outerjoin(Article, EventCluster.primary_article_id == Article.id)
        .filter(EventEntity.entity_id == entity_id)
        .all()
    )

    if not links:
        return {
            "entity": {
                "id": entity.id,
                "canonical_name": entity.canonical_name,
                "entity_type": entity.entity_type,
                "slug": entity.slug,
            },
            "total_events": 0,
            "events": [],
        }

    timeline_items: List[Dict[str, Any]] = []
    seen_cluster_ids: set = set()

    for event_entity, cluster, primary_article in links:
        if cluster.cluster_id in seen_cluster_ids:
            continue
        seen_cluster_ids.add(cluster.cluster_id)

        event_ts = get_grounded_event_timestamp(cluster, primary_article)
        event_date_val = event_ts.date()

        # Date Filtering (inclusive calendar day bounds)
        if date_from and event_date_val < date_from:
            continue
        if date_to and event_date_val > date_to:
            continue

        # Lookup Edition Event Membership (if featured in a Daily Edition)
        edition_event = (
            db.query(EditionEvent)
            .filter(EditionEvent.event_cluster_id == cluster.cluster_id)
            .first()
        )

        featured_in_edition = (
            edition_event.edition.edition_date.isoformat()
            if edition_event and edition_event.edition
            else None
        )

        primary_article_info = None
        if primary_article:
            primary_article_info = {
                "id": primary_article.id,
                "title": primary_article.title,
                "canonical_url": primary_article.canonical_url,
                "source_name": primary_article.source.name if primary_article.source else "Unknown",
                "published_at": primary_article.published_at.isoformat() if primary_article.published_at else None,
            }

        item = {
            "event_cluster_id": cluster.cluster_id,
            "canonical_title": cluster.canonical_title,
            "category": cluster.category,
            "event_date": event_date_val.isoformat(),
            "event_timestamp": event_ts.isoformat(),
            "cluster_score": cluster.cluster_score,
            "entity_role": event_entity.role,
            "confidence_class": event_entity.confidence_class,
            "evidence_class": event_entity.evidence_class,
            "link_method": event_entity.link_method,
            "supporting_article_count": event_entity.supporting_article_count,
            "supporting_mention_count": event_entity.supporting_mention_count,
            "distinct_source_count": event_entity.distinct_source_count,
            "featured_in_edition": featured_in_edition,
            "primary_article": primary_article_info,
            "provenance": event_entity.provenance_json or {},
        }
        timeline_items.append(item)

    # Sort deterministically: event_timestamp DESC, cluster_score DESC, cluster_id ASC
    timeline_items.sort(
        key=lambda x: (x["event_timestamp"], x["cluster_score"], x["event_cluster_id"]),
        reverse=True,
    )

    if limit and limit > 0:
        timeline_items = timeline_items[:limit]

    return {
        "entity": {
            "id": entity.id,
            "canonical_name": entity.canonical_name,
            "entity_type": entity.entity_type,
            "slug": entity.slug,
            "country_code": entity.country_code,
        },
        "total_events": len(timeline_items),
        "events": timeline_items,
    }
