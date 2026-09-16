"""
Stage 4C Event Participant Linking Engine.
Links trustworthy Stage 4B canonical entities to EventClusters.
Calculates evidence classes, role assignments, support counts, and provenance without new LLM calls.
"""
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session

from app.models import Article, ArticleAIOutput, Entity, EntityMention, EventCluster, EventClusterArticle, EventEntity
from services.knowledge.service import process_article_entities

logger = logging.getLogger("event_linking")

VALID_ROLES = {"ACTOR", "ISSUER", "SUBJECT", "LOCATION", "AFFECTED_ENTITY", "MENTIONED"}


def determine_entity_role(
    entity: Entity,
    raw_types: Set[str],
    is_title_hit: bool,
    is_primary_hit: bool,
    cluster_category: str,
) -> str:
    """
    Determines participant role for an entity in an event cluster using deterministic rules.
    Fallbacks safely to MENTIONED when ambiguous.
    """
    etype = entity.entity_type.upper()

    # 1. Central Banks issuing monetary/economic policy
    if etype == "CENTRAL_BANK":
        return "ISSUER"

    # 2. Countries & Regions as event location/scope
    if etype in ("COUNTRY", "REGION"):
        return "LOCATION"

    # 3. Commodities, Products, Technologies as event subject
    if etype in ("COMMODITY", "PRODUCT", "TECHNOLOGY"):
        return "SUBJECT"

    # 4. Government Bodies
    if etype == "GOVERNMENT_BODY":
        return "ISSUER" if is_primary_hit or is_title_hit else "MENTIONED"

    # 5. Companies & Persons
    if etype in ("COMPANY", "PERSON"):
        if is_title_hit or is_primary_hit:
            return "ACTOR"
        return "MENTIONED"

    return "MENTIONED"


def determine_evidence_class(
    is_title_hit: bool,
    is_primary_hit: bool,
    supporting_article_count: int,
    distinct_source_count: int,
) -> str:
    """
    Classifies entity evidence strength into deterministic classes:
    PRIMARY_EXPLICIT, MULTI_ARTICLE, SUPPORTING_ONLY, INCIDENTAL.
    """
    if is_title_hit or is_primary_hit:
        return "PRIMARY_EXPLICIT"
    if supporting_article_count >= 2 or distinct_source_count >= 2:
        return "MULTI_ARTICLE"
    if supporting_article_count == 1:
        return "INCIDENTAL"
    return "INCIDENTAL"



def determine_link_method(
    is_title_hit: bool,
    is_primary_hit: bool,
    supporting_article_count: int,
    extraction_methods: Set[str],
) -> str:
    """Assigns explainable link_method tag."""
    if is_title_hit:
        return "TITLE_MATCH"
    if is_primary_hit:
        return "PRIMARY_ARTICLE_EXPLICIT"
    if supporting_article_count >= 2:
        return "MULTI_ARTICLE_CORROBORATED"
    if "CURATED_ALIAS" in extraction_methods:
        return "MANUAL_ALIAS_RESOLVED"
    return "STRUCTURED_ROLE"


def link_event_entities(
    db: Session,
    event_cluster_id: str,
    reprocess: bool = False,
    dry_run: bool = False,
    auto_extract_missing: bool = True,
) -> Dict[str, Any]:
    """
    Links eligible entities to an EventCluster with support counts, role, and provenance.
    """
    metrics = {
        "event_cluster_id": event_cluster_id,
        "status": "SKIPPED",
        "member_articles": 0,
        "extracted_articles": 0,
        "raw_mentions": 0,
        "candidate_entities": 0,
        "links_created": 0,
        "links_updated": 0,
        "links_rejected": 0,
        "error": None,
    }

    try:
        cluster = db.query(EventCluster).filter(EventCluster.cluster_id == event_cluster_id).first()
        if not cluster:
            metrics["status"] = "CLUSTER_NOT_FOUND"
            return metrics

        # 1. Fetch Cluster Member Articles
        cluster_articles = (
            db.query(EventClusterArticle)
            .filter(EventClusterArticle.cluster_id == event_cluster_id)
            .all()
        )
        metrics["member_articles"] = len(cluster_articles)

        if not cluster_articles:
            metrics["status"] = "NO_ARTICLES"
            return metrics

        article_ids = [ca.article_id for ca in cluster_articles]
        primary_article_id = cluster.primary_article_id

        # 2. Check Entity Extraction Coverage & On-the-fly Extract if missing
        if auto_extract_missing:
            for aid in article_ids:
                existing_mentions_count = db.query(EntityMention).filter(EntityMention.article_id == aid).count()
                if existing_mentions_count == 0:
                    process_article_entities(db, article_id=aid)

        # 3. Collect Entity Mentions across all member articles
        mentions = (
            db.query(EntityMention, Article)
            .join(Article, EntityMention.article_id == Article.id)
            .filter(EntityMention.article_id.in_(article_ids))
            .all()
        )
        metrics["raw_mentions"] = len(mentions)

        if not mentions:
            metrics["status"] = "NO_MENTIONS"
            return metrics

        # 4. Group Mentions by Entity ID and Calculate Evidence
        entity_evidence: Dict[int, Dict[str, Any]] = {}

        for mention, article in mentions:
            eid = mention.entity_id
            if eid not in entity_evidence:
                entity_evidence[eid] = {
                    "entity": mention.entity,
                    "mention_ids": set(),
                    "article_ids": set(),
                    "source_ids": set(),
                    "raw_types": set(),
                    "extraction_methods": set(),
                    "is_primary_hit": False,
                    "is_title_hit": False,
                    "context_snippets": [],
                }

            ev = entity_evidence[eid]
            ev["mention_ids"].add(mention.id)
            ev["article_ids"].add(article.id)
            if article.source_id:
                ev["source_ids"].add(article.source_id)
            ev["raw_types"].add(mention.raw_entity_type)
            ev["extraction_methods"].add(mention.extraction_method)

            if mention.context_snippet:
                ev["context_snippets"].append(mention.context_snippet)

            if article.id == primary_article_id:
                ev["is_primary_hit"] = True

            # Title Hit Check (case-insensitive surface form match against cluster title or article title)
            sform = mention.surface_form.lower()
            if sform in cluster.canonical_title.lower() or (article.title and sform in article.title.lower()):
                ev["is_title_hit"] = True

        metrics["candidate_entities"] = len(entity_evidence)

        # 5. Filter & Create/Update EventEntity Links
        links_created = 0
        links_updated = 0
        links_rejected = 0

        for eid, ev in entity_evidence.items():
            entity = ev["entity"]
            sup_mentions = len(ev["mention_ids"])
            sup_articles = len(ev["article_ids"])
            sup_sources = len(ev["source_ids"]) if ev["source_ids"] else 1

            e_class = determine_evidence_class(
                is_title_hit=ev["is_title_hit"],
                is_primary_hit=ev["is_primary_hit"],
                supporting_article_count=sup_articles,
                distinct_source_count=sup_sources,
            )

            # Rejection Rule: Incidental single supporting mention without title/primary backing
            if e_class == "INCIDENTAL" and not ev["is_title_hit"] and not ev["is_primary_hit"] and sup_articles < 2:
                links_rejected += 1
                continue

            role = determine_entity_role(
                entity=entity,
                raw_types=ev["raw_types"],
                is_title_hit=ev["is_title_hit"],
                is_primary_hit=ev["is_primary_hit"],
                cluster_category=cluster.category,
            )

            link_method = determine_link_method(
                is_title_hit=ev["is_title_hit"],
                is_primary_hit=ev["is_primary_hit"],
                supporting_article_count=sup_articles,
                extraction_methods=ev["extraction_methods"],
            )

            provenance = {
                "mention_ids": sorted(list(ev["mention_ids"])),
                "article_ids": sorted(list(ev["article_ids"])),
                "source_ids": sorted(list(ev["source_ids"])),
                "is_primary_article_hit": ev["is_primary_hit"],
                "is_title_hit": ev["is_title_hit"],
                "context_snippets": ev["context_snippets"][:3],
            }

            # Upsert Check (unique constraint: event_cluster_id + entity_id + role)
            existing = (
                db.query(EventEntity)
                .filter(
                    EventEntity.event_cluster_id == event_cluster_id,
                    EventEntity.entity_id == eid,
                    EventEntity.role == role,
                )
                .first()
            )

            if existing:
                existing.supporting_mention_count = sup_mentions
                existing.supporting_article_count = sup_articles
                existing.distinct_source_count = sup_sources
                existing.evidence_class = e_class
                existing.link_method = link_method
                existing.provenance_json = provenance
                links_updated += 1
            else:
                event_entity = EventEntity(
                    event_cluster_id=event_cluster_id,
                    entity_id=eid,
                    role=role,
                    confidence_class="HIGH",
                    link_method=link_method,
                    supporting_mention_count=sup_mentions,
                    supporting_article_count=sup_articles,
                    distinct_source_count=sup_sources,
                    evidence_class=e_class,
                    provenance_json=provenance,
                )
                db.add(event_entity)
                links_created += 1

        if dry_run:
            db.rollback()
        else:
            db.commit()

        metrics["status"] = "SUCCESS"
        metrics["links_created"] = links_created
        metrics["links_updated"] = links_updated
        metrics["links_rejected"] = links_rejected
        return metrics

    except Exception as e:
        db.rollback()
        logger.error(f"Error linking entities for cluster {event_cluster_id}: {e}")
        metrics["status"] = "FAILED"
        metrics["error"] = str(e)
        return metrics


def link_events_batch(
    db: Session, limit: int = 10, offset: int = 0, reprocess: bool = False
) -> Dict[str, Any]:
    """Processes event-entity linking for a batch of EventClusters."""
    clusters = (
        db.query(EventCluster)
        .order_by(EventCluster.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    batch_metrics = {
        "clusters_processed": 0,
        "candidate_entities": 0,
        "links_created": 0,
        "links_updated": 0,
        "links_rejected": 0,
        "errors": 0,
        "details": [],
    }

    for c in clusters:
        res = link_event_entities(db, c.cluster_id, reprocess=reprocess)
        batch_metrics["clusters_processed"] += 1
        batch_metrics["candidate_entities"] += res.get("candidate_entities", 0)
        batch_metrics["links_created"] += res.get("links_created", 0)
        batch_metrics["links_updated"] += res.get("links_updated", 0)
        batch_metrics["links_rejected"] += res.get("links_rejected", 0)
        if res["status"] == "FAILED":
            batch_metrics["errors"] += 1
        batch_metrics["details"].append(res)

    return batch_metrics
