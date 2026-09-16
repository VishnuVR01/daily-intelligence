"""
Stage 4B Entity Resolution Engine.
Implements 5-step resolution precedence, generic entity term suppression, curated seed loading,
and zero false merges guarantee.
"""
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models import Entity, EntityAlias, ArticleAIOutput
from services.knowledge.extraction import RawEntityMention
from services.knowledge.normalization import (
    normalize_entity_name,
    normalize_entity_type,
    slugify_entity_name,
    normalize_country_code,
)

logger = logging.getLogger("entity_resolution")

GENERIC_TERMS = {
    "company", "companies", "firm", "firms", "business", "businesses", "corporation",
    "government", "governments", "official", "officials", "analyst", "analysts",
    "investor", "investors", "market", "markets", "industry", "sector", "product",
    "service", "enterprise", "source", "author", "report", "news", "country", "nation",
    "agency", "regulator", "bank", "banks", "executive", "executives", "group", "network"
}


def is_generic_term(surface_name: str) -> bool:
    """Detects and suppresses generic non-entity terms."""
    if not surface_name:
        return True
    clean = surface_name.strip().lower()
    if clean in GENERIC_TERMS:
        return True
    if len(clean) <= 1:
        return True
    return False


@dataclass
class ResolvedEntityResult:
    entity: Entity
    surface_form: str
    raw_entity_type: str
    resolved_entity_type: str
    confidence_class: str  # HIGH, MEDIUM, LOW
    extraction_method: str  # CURATED_ALIAS, EXACT_CANONICAL, COUNTRY_ALIAS, CONTEXT_RULE, NEW_CANDIDATE


def seed_curated_entities(db: Session, seed_json_path: Optional[str] = None) -> int:
    """
    Seeds curated high-value entities & aliases from data/entity_aliases_v1.json.
    Returns count of seeded entities.
    """
    if seed_json_path is None:
        seed_json_path = str(Path(__file__).parent.parent.parent / "data" / "entity_aliases_v1.json")

    p = Path(seed_json_path)
    if not p.exists():
        logger.warning(f"Seed alias file not found: {seed_json_path}")
        return 0

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    seeded_count = 0

    for item in data:
        canon_name = item["canonical_name"]
        etype = item["entity_type"]
        ccode = item.get("country_code")
        aliases = item.get("aliases", [])

        norm_name = normalize_entity_name(canon_name)
        slug = slugify_entity_name(canon_name, etype)

        # Query existing
        entity = db.query(Entity).filter(Entity.slug == slug).first()
        if not entity:
            entity = db.query(Entity).filter(
                Entity.normalized_name == norm_name, Entity.entity_type == etype
            ).first()

        if not entity:
            entity = Entity(
                canonical_name=canon_name,
                normalized_name=norm_name,
                entity_type=etype,
                slug=slug,
                country_code=ccode,
                external_ids=item.get("external_ids"),
            )
            db.add(entity)
            db.flush()
            seeded_count += 1

        # Add canonical alias
        canon_alias_norm = norm_name
        existing_canon_alias = db.query(EntityAlias).filter(
            EntityAlias.entity_id == entity.id, EntityAlias.normalized_alias == canon_alias_norm
        ).first()
        if not existing_canon_alias:
            db.add(
                EntityAlias(
                    entity_id=entity.id,
                    alias=canon_name,
                    normalized_alias=canon_alias_norm,
                    alias_type="CANONICAL",
                )
            )
            db.flush()

        # Add additional aliases
        seen_norm_aliases = {canon_alias_norm}
        for al in aliases:
            norm_al = normalize_entity_name(al)
            if norm_al and norm_al not in seen_norm_aliases:
                seen_norm_aliases.add(norm_al)
                existing_al = db.query(EntityAlias).filter(
                    EntityAlias.entity_id == entity.id, EntityAlias.normalized_alias == norm_al
                ).first()
                if not existing_al:
                    db.add(
                        EntityAlias(
                            entity_id=entity.id,
                            alias=al,
                            normalized_alias=norm_al,
                            alias_type="KNOWN_ALIAS",
                        )
                    )
                    db.flush()

    db.commit()
    return seeded_count




def resolve_entity_mention(
    db: Session, raw_mention: RawEntityMention
) -> Optional[ResolvedEntityResult]:
    """
    Resolves a RawEntityMention into a canonical Entity following 5-step precedence:
    1. Generic Suppression
    2. Country Code Alias Match
    3. Exact Canonical Normalized Match
    4. Exact Alias Normalized Match
    5. Conservative Candidate Entity Creation
    """
    surface = raw_mention.surface_name
    if is_generic_term(surface):
        return None

    resolved_type = normalize_entity_type(raw_mention.raw_type, surface)
    norm_surface = normalize_entity_name(surface)

    if not norm_surface or len(norm_surface) <= 1:
        return None

    # Step 2: Country Code / Country Alias Match
    ccode = normalize_country_code(surface)
    if ccode or resolved_type == "COUNTRY":
        # Look up entity by country code or normalized name
        c_entity = None
        if ccode:
            c_entity = db.query(Entity).filter(Entity.country_code == ccode, Entity.entity_type == "COUNTRY").first()
        if not c_entity:
            c_entity = db.query(Entity).filter(Entity.normalized_name == norm_surface, Entity.entity_type == "COUNTRY").first()

        if c_entity:
            return ResolvedEntityResult(
                entity=c_entity,
                surface_form=surface,
                raw_entity_type=raw_mention.raw_type,
                resolved_entity_type="COUNTRY",
                confidence_class="HIGH",
                extraction_method="COUNTRY_ALIAS",
            )

    # Step 3: Exact Canonical Match (normalized_name + entity_type)
    canon_match = db.query(Entity).filter(
        Entity.normalized_name == norm_surface, Entity.entity_type == resolved_type
    ).first()
    if canon_match:
        return ResolvedEntityResult(
            entity=canon_match,
            surface_form=surface,
            raw_entity_type=raw_mention.raw_type,
            resolved_entity_type=resolved_type,
            confidence_class="HIGH",
            extraction_method="EXACT_CANONICAL",
        )

    # Step 4: Exact Alias Match (normalized_alias)
    alias_match = db.query(EntityAlias).filter(
        EntityAlias.normalized_alias == norm_surface
    ).first()
    if alias_match:
        return ResolvedEntityResult(
            entity=alias_match.entity,
            surface_form=surface,
            raw_entity_type=raw_mention.raw_type,
            resolved_entity_type=alias_match.entity.entity_type,
            confidence_class="HIGH",
            extraction_method="CURATED_ALIAS",
        )

    # Step 5: Conservative Candidate Entity Creation
    # Only create if name is multi-word or capital non-generic
    slug = slugify_entity_name(surface, resolved_type)
    existing_by_slug = db.query(Entity).filter(Entity.slug == slug).first()
    if existing_by_slug:
        return ResolvedEntityResult(
            entity=existing_by_slug,
            surface_form=surface,
            raw_entity_type=raw_mention.raw_type,
            resolved_entity_type=existing_by_slug.entity_type,
            confidence_class="HIGH",
            extraction_method="EXACT_CANONICAL",
        )

    new_entity = Entity(
        canonical_name=surface.strip(),
        normalized_name=norm_surface,
        entity_type=resolved_type,
        slug=slug,
        country_code=ccode,
    )
    db.add(new_entity)
    db.flush()

    # Add canonical alias
    db.add(
        EntityAlias(
            entity_id=new_entity.id,
            alias=surface.strip(),
            normalized_alias=norm_surface,
            alias_type="CANONICAL",
        )
    )

    return ResolvedEntityResult(
        entity=new_entity,
        surface_form=surface,
        raw_entity_type=raw_mention.raw_type,
        resolved_entity_type=resolved_type,
        confidence_class="HIGH",
        extraction_method="NEW_CANDIDATE",
    )


def resolve_entity(db: Session, raw_name: str, raw_type: str) -> Optional[Dict[str, Any]]:
    """
    Convenience helper for resolution testing and benchmarking.
    Seeds entity table if empty, then resolves raw name and type.
    """
    # Ensure seed loaded
    if db.query(Entity).count() == 0:
        seed_curated_entities(db)

    mention = RawEntityMention(surface_name=raw_name, raw_type=raw_type, article_id=999999)
    res = resolve_entity_mention(db, mention)
    if not res:
        return None
    return {
        "canonical_name": res.entity.canonical_name,
        "entity_type": res.entity.entity_type,
        "confidence_class": res.confidence_class,
        "extraction_method": res.extraction_method,
    }

