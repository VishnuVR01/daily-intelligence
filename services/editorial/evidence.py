"""
EvidencePack Builder for Stage 3D Editorial Synthesis.
Deterministically extracts evidence for a selected Event Cluster.
Enforces context bounding: strictly 1 Primary Article + up to 3 strongest Supporting Articles.
Formats normalized temporal labels and extracts evidence metadata.
"""
from dataclasses import dataclass, field
from datetime import datetime, date, timezone, timedelta
from typing import Any, Dict, List, Optional, Set

from app.models import Article, ArticleAIOutput
from services.editorial.clustering import extract_key_entities, EventClusterResult
from services.editorial.selection import EventSelectionResult


@dataclass
class ArticleEvidence:
    id: int
    title: str
    source_name: str
    source_type: str
    trust_tier: str
    published_at_str: str
    summary: str


@dataclass
class EvidencePack:
    event_cluster_id: str
    canonical_title: str
    edition_date: str
    role: str
    section: str
    event_score: float
    primary_article: ArticleEvidence
    supporting_articles: List[ArticleEvidence]
    normalized_temporal_label: str
    entities: List[str]
    countries: List[str]
    distinct_source_count: int
    evidence_article_ids: List[int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_cluster_id": self.event_cluster_id,
            "canonical_title": self.canonical_title,
            "edition_date": self.edition_date,
            "role": self.role,
            "section": self.section,
            "event_score": self.event_score,
            "primary_article": {
                "id": self.primary_article.id,
                "title": self.primary_article.title,
                "source_name": self.primary_article.source_name,
                "source_type": self.primary_article.source_type,
                "trust_tier": self.primary_article.trust_tier,
                "published_at": self.primary_article.published_at_str,
                "summary": self.primary_article.summary,
            },
            "supporting_articles": [
                {
                    "id": a.id,
                    "title": a.title,
                    "source_name": a.source_name,
                    "published_at": a.published_at_str,
                    "summary": a.summary,
                }
                for a in self.supporting_articles
            ],
            "normalized_temporal_label": self.normalized_temporal_label,
            "entities": self.entities,
            "countries": self.countries,
            "distinct_source_count": self.distinct_source_count,
            "evidence_article_ids": self.evidence_article_ids,
        }


def format_temporal_label(dt: Optional[datetime], edition_date: date) -> str:
    """Formats normalized temporal label (e.g., 'on 15 September 2026', 'overnight')."""
    if not dt:
        return f"on {edition_date.strftime('%d %B %Y')}"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    dt_date = dt.date()
    if dt_date == edition_date:
        if dt.hour < 6:
            return f"overnight on {edition_date.strftime('%d %B %Y')}"
        return f"on {edition_date.strftime('%d %B %Y')}"
    elif dt_date == edition_date - timedelta(days=1):
        return f"on {dt_date.strftime('%d %B %Y')}"
    else:
        return f"earlier this week on {dt_date.strftime('%d %B %Y')}"


def extract_best_summary(article: Article) -> str:
    """Extracts existing validated AI summary or clean raw summary fallback."""
    ai_outs = getattr(article, "ai_outputs", [])
    if ai_outs:
        for ai in ai_outs:
            if ai.status == "success" and ai.summary:
                return ai.summary.strip()
    if article.raw_summary:
        # Excerpt clean 250 chars
        clean = article.raw_summary.strip()
        return clean[:250] + ("..." if len(clean) > 250 else "")
    return article.title


def build_evidence_pack(
    event_selection: EventSelectionResult,
    edition_date: date,
    max_supporting: int = 3,
) -> EvidencePack:
    """
    Builds a bounded EvidencePack for Ollama synthesis.
    Context is strictly restricted to 1 Primary Article + up to max_supporting strongest Supporting Articles.
    """
    prim = event_selection.primary_article
    prim_src_name = prim.source.name if prim.source else "Unknown Source"
    prim_src_type = prim.source.source_type if prim.source else "NEWS_OUTLET"
    prim_trust = prim.source.trust_tier if prim.source else "useful"
    prim_date = prim.published_at or prim.collected_at
    prim_date_str = format_temporal_label(prim_date, edition_date)
    prim_summary = extract_best_summary(prim)

    prim_evidence = ArticleEvidence(
        id=prim.id,
        title=prim.title,
        source_name=prim_src_name,
        source_type=prim_src_type,
        trust_tier=prim_trust,
        published_at_str=prim_date_str,
        summary=prim_summary,
    )

    supporting_evidences: List[ArticleEvidence] = []
    # Rank supporting articles: prefer distinct sources & valid AI summaries
    supp_list = list(event_selection.supporting_articles)
    supp_list.sort(
        key=lambda a: (
            1 if (a.source_id and a.source_id != prim.source_id) else 0,
            1 if (getattr(a, "ai_outputs", None)) else 0,
            a.published_at.timestamp() if a.published_at else 0,
        ),
        reverse=True,
    )

    for supp in supp_list[:max_supporting]:
        supp_src_name = supp.source.name if supp.source else "Unknown Source"
        supp_src_type = supp.source.source_type if supp.source else "NEWS_OUTLET"
        supp_trust = supp.source.trust_tier if supp.source else "useful"
        supp_date = supp.published_at or supp.collected_at
        supp_date_str = format_temporal_label(supp_date, edition_date)
        supp_summary = extract_best_summary(supp)

        supp_evidence = ArticleEvidence(
            id=supp.id,
            title=supp.title,
            source_name=supp_src_name,
            source_type=supp_src_type,
            trust_tier=supp_trust,
            published_at_str=supp_date_str,
            summary=supp_summary,
        )
        supporting_evidences.append(supp_evidence)

    evidence_ids = [prim.id] + [s.id for s in supporting_evidences]

    # Extract proper noun entities
    entities_set = extract_key_entities(prim.title)
    for s in supporting_evidences:
        entities_set.update(extract_key_entities(s.title))

    countries = list(prim.source.country_code for prim in [prim] + supp_list[:max_supporting] if prim.source and prim.source.country_code)
    countries = list(set(countries))

    return EvidencePack(
        event_cluster_id=event_selection.cluster_id,
        canonical_title=event_selection.canonical_title,
        edition_date=str(edition_date),
        role=event_selection.role,
        section=event_selection.section,
        event_score=event_selection.event_score,
        primary_article=prim_evidence,
        supporting_articles=supporting_evidences,
        normalized_temporal_label=prim_date_str,
        entities=sorted(list(entities_set))[:8],
        countries=countries,
        distinct_source_count=event_selection.distinct_source_count,
        evidence_article_ids=evidence_ids,
    )
