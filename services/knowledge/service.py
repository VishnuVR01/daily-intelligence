"""
Stage 4B Entity Processing Service.
Orchestrates entity extraction, resolution, mention persistence, idempotency,
and failure isolation per article.
"""
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models import Article, ArticleAIOutput, EntityMention
from services.knowledge.extraction import extract_raw_entity_mentions, RawEntityMention
from services.knowledge.resolution import resolve_entity_mention, seed_curated_entities, ResolvedEntityResult

logger = logging.getLogger("knowledge_service")
EXTRACTOR_VERSION = "entity_extractor_v1"


def process_article_entities(
    db: Session, article_id: int, reprocess: bool = False, dry_run: bool = False
) -> Dict[str, Any]:
    """
    Processes entity extraction and resolution for a single eligible article.
    Failure isolation: Catches exceptions per article so one failure does not break the batch.
    """
    metrics = {
        "article_id": article_id,
        "status": "SKIPPED",
        "skipped": False,
        "raw_mentions": 0,
        "entities_created": 0,
        "mentions_created": 0,
        "mentions_rejected": 0,
        "error": None,
    }

    try:
        # Check if already processed (unless reprocess=True)
        if not reprocess:
            existing_count = db.query(EntityMention).filter(EntityMention.article_id == article_id).count()
            if existing_count > 0:
                metrics["status"] = "ALREADY_PROCESSED"
                metrics["skipped"] = True
                return metrics

        # 1. Eligibility Check: Require status == "success" AND is_relevant == True
        ai_out = (
            db.query(ArticleAIOutput)
            .filter(
                ArticleAIOutput.article_id == article_id,
                ArticleAIOutput.status == "success",
                ArticleAIOutput.is_relevant == True,
            )
            .first()
        )

        if not ai_out:
            metrics["status"] = "ELIGIBILITY_SKIPPED"
            metrics["skipped"] = True
            return metrics

        # Ensure seed entities exist
        seed_curated_entities(db)

        # 2. Extract Raw Mentions
        raw_mentions = extract_raw_entity_mentions(ai_out)
        metrics["raw_mentions"] = len(raw_mentions)

        if not raw_mentions:
            metrics["status"] = "NO_MENTIONS"
            return metrics

        mentions_created = 0
        mentions_rejected = 0
        seen_entity_ids = set()

        for raw_m in raw_mentions:
            resolved_res = resolve_entity_mention(db, raw_m)
            if not resolved_res:
                mentions_rejected += 1
                continue

            entity = resolved_res.entity
            if entity.id in seen_entity_ids:
                continue
            seen_entity_ids.add(entity.id)

            # 3. Idempotency Check: Query existing EntityMention for (entity_id, article_id)
            existing_mention = (
                db.query(EntityMention)
                .filter(
                    EntityMention.entity_id == entity.id,
                    EntityMention.article_id == article_id,
                )
                .first()
            )

            if not existing_mention:
                mention = EntityMention(
                    entity_id=entity.id,
                    article_id=article_id,
                    surface_form=resolved_res.surface_form,
                    raw_entity_type=resolved_res.raw_entity_type,
                    resolved_entity_type=resolved_res.resolved_entity_type,
                    confidence_class=resolved_res.confidence_class,
                    extraction_method=resolved_res.extraction_method,
                    extractor_version=EXTRACTOR_VERSION,
                    context_snippet=raw_m.context_snippet,
                )
                db.add(mention)
                mentions_created += 1


        if dry_run:
            db.rollback()
        else:
            db.commit()

        metrics["status"] = "SUCCESS"
        metrics["mentions_created"] = mentions_created
        metrics["mentions_rejected"] = mentions_rejected
        return metrics

    except Exception as e:
        db.rollback()
        logger.error(f"Error processing entity extraction for article {article_id}: {e}")
        metrics["status"] = "FAILED"
        metrics["error"] = str(e)
        return metrics



def process_relevant_articles(
    db: Session, limit: int = 10, offset: int = 0, reprocess: bool = False
) -> Dict[str, Any]:
    """
    Processes entity extraction for a batch of relevant articles.
    Returns structured batch metrics.
    """
    # Query eligible relevant articles
    eligible_ai_outs = (
        db.query(ArticleAIOutput)
        .filter(
            ArticleAIOutput.status == "success", ArticleAIOutput.is_relevant == True
        )
        .order_by(ArticleAIOutput.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    batch_metrics = {
        "articles_processed": 0,
        "raw_mentions": 0,
        "mentions_created": 0,
        "mentions_rejected": 0,
        "errors": 0,
        "details": [],
    }

    for ai in eligible_ai_outs:
        res = process_article_entities(db, ai.article_id, reprocess=reprocess)
        batch_metrics["articles_processed"] += 1
        batch_metrics["raw_mentions"] += res["raw_mentions"]
        batch_metrics["mentions_created"] += res["mentions_created"]
        batch_metrics["mentions_rejected"] += res["mentions_rejected"]
        if res["status"] == "FAILED":
            batch_metrics["errors"] += 1
        batch_metrics["details"].append(res)

    return batch_metrics
